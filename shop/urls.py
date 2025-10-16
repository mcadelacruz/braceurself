from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('catalog/', views.catalog, name='catalog'),
    path('catalog/<int:product_id>/order/', views.product_order, name='product_order'),
    path('orders/', views.order_list, name='order_list'),
    path('orders/<int:order_id>/', views.customer_manage_order, name='customer_manage_order'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('seller/dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('seller/manage-orders/', views.manage_orders_list, name='manage_orders_list'),
    path('seller/manage-products/', views.manage_products_list, name='manage_products_list'),
    path('seller/order/<int:order_id>/manage/', views.manage_order, name='manage_order'),
    path('seller/update/', views.update_seller_view, name='update_seller'),
    path('customize/', views.customize_bracelet, name='customize_bracelet'),
    path('customize/new/', views.bracelet_designer, name='bracelet_designer'),
    path('customize/<int:design_id>/', views.bracelet_design_detail, name='bracelet_design_detail'),
    path('customize/<int:design_id>/order/', views.order_custom_bracelet, name='order_custom_bracelet'),
]
