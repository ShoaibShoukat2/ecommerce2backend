from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from . import views, admin_views

router = DefaultRouter()
router.register('categories', views.CategoryViewSet)
router.register('products', views.ProductViewSet)
router.register('cart', views.CartViewSet, basename='cart')
router.register('orders', views.OrderViewSet, basename='orders')
router.register('wishlist', views.WishlistViewSet, basename='wishlist')

admin_router = DefaultRouter()
admin_router.register('categories', admin_views.AdminCategoryViewSet, basename='admin-categories')
admin_router.register('products', admin_views.AdminProductViewSet, basename='admin-products')
admin_router.register('orders', admin_views.AdminOrderViewSet, basename='admin-orders')
admin_router.register('users', admin_views.AdminUserViewSet, basename='admin-users')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/profile/', views.profile, name='profile'),
    path('payments/create-order/', views.create_razorpay_payment_order, name='payments-create-order'),
    path('payments/verify/', views.verify_razorpay_payment, name='payments-verify'),
    path('admin/dashboard/', admin_views.admin_dashboard, name='admin-dashboard'),
    path('admin/', include(admin_router.urls)),
]
