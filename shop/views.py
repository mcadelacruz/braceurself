from django.shortcuts import render

def home(request):
    return render(request, 'shop/home.html')

def catalog(request):
    return render(request, 'shop/catalog.html')

def order_list(request):
    return render(request, 'shop/order_list.html')

def login_register(request):
    return render(request, 'shop/login_register.html')
