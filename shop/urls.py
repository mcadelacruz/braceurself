from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('catalog/', views.catalog, name='catalog'),
    path('orders/', views.order_list, name='order_list'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('seller/dashboard/', views.seller_dashboard, name='seller_dashboard'),
    path('seller/update/', views.update_seller_view, name='update_seller'),
]
