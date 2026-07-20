import uuid
from decimal import Decimal
from django.conf import settings
from django.db.models import Q
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import Category, Product, Cart, CartItem, Order, OrderItem, Wishlist
from .constants import FREE_SHIPPING_THRESHOLD, SHIPPING_COST
from .payments import create_razorpay_order, verify_razorpay_signature
from .serializers import (
    CategorySerializer, ProductSerializer, ProductListSerializer,
    CartSerializer, CartItemSerializer, OrderSerializer, CheckoutSerializer,
    RegisterSerializer, UserSerializer, WishlistSerializer,
    RazorpayVerifySerializer,
)


def get_or_create_cart(request):
    session_key = request.headers.get('X-Session-Key')
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        if session_key:
            guest_cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()
            if guest_cart and guest_cart.items.exists():
                for item in guest_cart.items.all():
                    existing = cart.items.filter(product=item.product).first()
                    if existing:
                        existing.quantity += item.quantity
                        existing.save()
                    else:
                        item.cart = cart
                        item.save()
                guest_cart.items.all().delete()
                guest_cart.delete()
        return cart
    if session_key:
        cart, _ = Cart.objects.get_or_create(session_key=session_key, user__isnull=True)
        return cart
    return None


def calculate_order_total(cart):
    subtotal = cart.subtotal
    shipping = Decimal('0') if subtotal >= FREE_SHIPPING_THRESHOLD else Decimal(str(SHIPPING_COST))
    return subtotal + shipping, shipping


def finalize_order(cart, user, shipping_data, payment_method='cod', payment_status='pending',
                   razorpay_order_id='', razorpay_payment_id=''):
    total, _ = calculate_order_total(cart)
    order = Order.objects.create(
        user=user if user and user.is_authenticated else None,
        total=total,
        payment_method=payment_method,
        payment_status=payment_status,
        razorpay_order_id=razorpay_order_id,
        razorpay_payment_id=razorpay_payment_id,
        **shipping_data,
    )
    for item in cart.items.all():
        OrderItem.objects.create(
            order=order,
            product=item.product,
            product_name=item.product.name,
            quantity=item.quantity,
            price=item.product.price,
        )
        item.product.stock -= item.quantity
        item.product.save()
    cart.items.all().delete()
    return order


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    lookup_field = 'slug'


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.select_related('category').all()
    lookup_field = 'slug'

    def get_serializer_class(self):
        if self.action == 'list':
            return ProductListSerializer
        return ProductSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        category = self.request.query_params.get('category')
        search = self.request.query_params.get('search')
        featured = self.request.query_params.get('featured')
        is_new = self.request.query_params.get('new')
        sort = self.request.query_params.get('sort', '-created_at')

        if category:
            qs = qs.filter(category__slug=category)
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        if featured == 'true':
            qs = qs.filter(is_featured=True)
        if is_new == 'true':
            qs = qs.filter(is_new=True)

        allowed_sorts = ['price', '-price', 'rating', '-rating', '-created_at', 'name']
        if sort in allowed_sorts:
            qs = qs.order_by(sort)
        return qs

    @action(detail=False, methods=['get'])
    def featured(self, request):
        products = self.get_queryset().filter(is_featured=True)[:8]
        serializer = ProductListSerializer(products, many=True)
        return Response(serializer.data)


class CartViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def list(self, request):
        cart = get_or_create_cart(request)
        if not cart:
            return Response({'id': None, 'items': [], 'total_items': 0, 'subtotal': 0})
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def add(self, request):
        cart = get_or_create_cart(request)
        if not cart:
            session_key = str(uuid.uuid4())
            cart = Cart.objects.create(session_key=session_key)
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
        if quantity > product.stock:
            return Response({'error': 'Not enough stock'}, status=status.HTTP_400_BAD_REQUEST)
        item, created = CartItem.objects.get_or_create(cart=cart, product=product, defaults={'quantity': quantity})
        if not created:
            item.quantity += quantity
            if item.quantity > product.stock:
                return Response({'error': 'Not enough stock'}, status=status.HTTP_400_BAD_REQUEST)
            item.save()
        serializer = CartSerializer(cart)
        data = serializer.data
        if not request.user.is_authenticated and cart.session_key:
            data['session_key'] = cart.session_key
        return Response(data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'])
    def update_item(self, request):
        cart = get_or_create_cart(request)
        if not cart:
            return Response({'error': 'Cart not found'}, status=status.HTTP_404_NOT_FOUND)
        item_id = request.data.get('item_id')
        quantity = int(request.data.get('quantity', 1))
        try:
            item = CartItem.objects.get(id=item_id, cart=cart)
        except CartItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)
        if quantity <= 0:
            item.delete()
        else:
            if quantity > item.product.stock:
                return Response({'error': 'Not enough stock'}, status=status.HTTP_400_BAD_REQUEST)
            item.quantity = quantity
            item.save()
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def remove(self, request):
        cart = get_or_create_cart(request)
        if not cart:
            return Response({'error': 'Cart not found'}, status=status.HTTP_404_NOT_FOUND)
        item_id = request.data.get('item_id')
        try:
            item = CartItem.objects.get(id=item_id, cart=cart)
            item.delete()
        except CartItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def clear(self, request):
        cart = get_or_create_cart(request)
        if cart:
            cart.items.all().delete()
        return Response({'message': 'Cart cleared'})


class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).prefetch_related('items')

    @action(detail=False, methods=['post'], permission_classes=[AllowAny])
    def checkout(self, request):
        cart = get_or_create_cart(request)
        if not cart or not cart.items.exists():
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = finalize_order(
            cart,
            request.user,
            serializer.validated_data,
            payment_method='cod',
            payment_status='pending',
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['post'], url_path='razorpay/create-order', permission_classes=[AllowAny])
    def razorpay_create_order(self, request):
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            return Response({'error': 'Razorpay is not configured'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        cart = get_or_create_cart(request)
        if not cart or not cart.items.exists():
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        total, _ = calculate_order_total(cart)
        amount_paise = int(total * 100)
        if amount_paise < 100:
            return Response({'error': 'Order total must be at least Rs. 1'}, status=status.HTTP_400_BAD_REQUEST)

        receipt = f"rcpt_{uuid.uuid4().hex[:12]}"
        try:
            razorpay_order = create_razorpay_order(amount_paise, receipt)
        except Exception as exc:
            return Response({'error': f'Failed to create payment order: {exc}'}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({
            'razorpay_order_id': razorpay_order['id'],
            'amount': amount_paise,
            'currency': 'INR',
            'key_id': settings.RAZORPAY_KEY_ID,
            'total': total,
        })

    @action(detail=False, methods=['post'], url_path='razorpay/verify', permission_classes=[AllowAny])
    def razorpay_verify(self, request):
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            return Response({'error': 'Razorpay is not configured'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        cart = get_or_create_cart(request)
        if not cart or not cart.items.exists():
            return Response({'error': 'Cart is empty'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = RazorpayVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            verify_razorpay_signature(
                data['razorpay_order_id'],
                data['razorpay_payment_id'],
                data['razorpay_signature'],
            )
        except Exception:
            return Response({'error': 'Payment verification failed'}, status=status.HTTP_400_BAD_REQUEST)

        shipping_data = {
            'shipping_name': data['shipping_name'],
            'shipping_email': data['shipping_email'],
            'shipping_phone': data['shipping_phone'],
            'shipping_address': data['shipping_address'],
            'shipping_city': data['shipping_city'],
            'shipping_zip': data['shipping_zip'],
            'notes': data.get('notes', ''),
        }
        order = finalize_order(
            cart,
            request.user,
            shipping_data,
            payment_method='razorpay',
            payment_status='paid',
            razorpay_order_id=data['razorpay_order_id'],
            razorpay_payment_id=data['razorpay_payment_id'],
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class RegisterView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def profile(request):
    return Response(UserSerializer(request.user).data)


class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Wishlist.objects.filter(user=self.request.user).select_related('product')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @action(detail=False, methods=['post'])
    def toggle(self, request):
        product_id = request.data.get('product_id')
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
        wishlist_item = Wishlist.objects.filter(user=request.user, product=product).first()
        if wishlist_item:
            wishlist_item.delete()
            return Response({'wishlisted': False})
        Wishlist.objects.create(user=request.user, product=product)
        return Response({'wishlisted': True}, status=status.HTTP_201_CREATED)
