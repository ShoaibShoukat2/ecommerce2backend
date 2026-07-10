from django.contrib.auth.models import User
from django.db.models import Sum, Q
from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from .models import Category, Product, Order
from .permissions import IsAdminUser
from .admin_serializers import (
    AdminCategorySerializer, AdminProductSerializer,
    AdminOrderSerializer, AdminOrderStatusSerializer, AdminUserSerializer,
)


@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_dashboard(request):
    orders = Order.objects.all()
    products = Product.objects.all()
    return Response({
        'total_products': products.count(),
        'total_categories': Category.objects.count(),
        'total_orders': orders.count(),
        'total_revenue': orders.exclude(status='cancelled').aggregate(t=Sum('total'))['t'] or 0,
        'pending_orders': orders.filter(status='pending').count(),
        'low_stock_products': products.filter(stock__lte=10).count(),
        'out_of_stock': products.filter(stock=0).count(),
        'total_users': User.objects.count(),
        'recent_orders': AdminOrderSerializer(
            orders.select_related('user').prefetch_related('items')[:5], many=True
        ).data,
        'low_stock_list': AdminProductSerializer(
            products.filter(stock__lte=10).select_related('category')[:10], many=True
        ).data,
    })


class AdminCategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = AdminCategorySerializer
    permission_classes = [IsAdminUser]


class AdminProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.select_related('category').all()
    serializer_class = AdminProductSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        qs = super().get_queryset()
        search = self.request.query_params.get('search')
        category = self.request.query_params.get('category')
        low_stock = self.request.query_params.get('low_stock')
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(description__icontains=search))
        if category:
            qs = qs.filter(category_id=category)
        if low_stock == 'true':
            qs = qs.filter(stock__lte=10)
        return qs.order_by('-created_at')

    @action(detail=True, methods=['patch'])
    def stock(self, request, pk=None):
        product = self.get_object()
        stock = request.data.get('stock')
        if stock is None:
            return Response({'error': 'stock is required'}, status=status.HTTP_400_BAD_REQUEST)
        product.stock = max(0, int(stock))
        product.save()
        return Response(AdminProductSerializer(product).data)


class AdminOrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.select_related('user').prefetch_related('items').all()
    permission_classes = [IsAdminUser]
    http_method_names = ['get', 'patch', 'head', 'options']

    def get_serializer_class(self):
        if self.action in ('partial_update', 'update'):
            return AdminOrderStatusSerializer
        return AdminOrderSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        status_filter = self.request.query_params.get('status')
        search = self.request.query_params.get('search')
        if status_filter:
            qs = qs.filter(status=status_filter)
        if search:
            qs = qs.filter(
                Q(order_number__icontains=search) |
                Q(shipping_name__icontains=search) |
                Q(shipping_email__icontains=search)
            )
        return qs.order_by('-created_at')


class AdminUserViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = AdminUserSerializer
    permission_classes = [IsAdminUser]
