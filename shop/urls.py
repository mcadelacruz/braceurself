from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('catalog/', views.catalog, name='catalog'),
    path('orders/', views.order_list, name='order_list'),
    path('login/', views.login_register, name='login_register'),
]
