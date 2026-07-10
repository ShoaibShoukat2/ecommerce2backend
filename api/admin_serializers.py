from django.contrib.auth.models import User
from django.utils.text import slugify
from rest_framework import serializers
from .models import Category, Product, Order, OrderItem


class AdminUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined']
        read_only_fields = fields


class AdminCategorySerializer(serializers.ModelSerializer):
    product_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'image_url', 'product_count', 'created_at']
        read_only_fields = ['created_at']

    def get_product_count(self, obj):
        return obj.products.count()

    def create(self, validated_data):
        if not validated_data.get('slug'):
            validated_data['slug'] = slugify(validated_data['name'])
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'name' in validated_data and 'slug' not in validated_data:
            validated_data['slug'] = slugify(validated_data['name'])
        return super().update(instance, validated_data)


class AdminProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    discount_percent = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'description', 'price', 'compare_price',
            'image_url', 'stock', 'rating', 'review_count', 'is_featured',
            'is_new', 'category', 'category_name', 'discount_percent',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def create(self, validated_data):
        if not validated_data.get('slug'):
            validated_data['slug'] = slugify(validated_data['name'])
        base_slug = validated_data['slug']
        counter = 1
        while Product.objects.filter(slug=validated_data['slug']).exists():
            validated_data['slug'] = f'{base_slug}-{counter}'
            counter += 1
        return super().create(validated_data)


class AdminOrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ['id', 'product_name', 'quantity', 'price']


class AdminOrderSerializer(serializers.ModelSerializer):
    items = AdminOrderItemSerializer(many=True, read_only=True)
    customer = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'status', 'total', 'customer',
            'shipping_name', 'shipping_email', 'shipping_phone',
            'shipping_address', 'shipping_city', 'shipping_zip',
            'notes', 'items', 'created_at', 'updated_at',
        ]
        read_only_fields = ['order_number', 'total', 'created_at', 'updated_at']

    def get_customer(self, obj):
        if obj.user:
            return obj.user.username
        return 'Guest'


class AdminOrderStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ['status']
