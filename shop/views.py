from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib import messages
from .models import SellerProfile
from django.contrib.auth.models import User

def home(request):
    return render(request, 'shop/home.html')

def catalog(request):
    return render(request, 'shop/catalog.html')

def order_list(request):
    return render(request, 'shop/order_list.html')

def login_register(request):
    return render(request, 'shop/login_register.html')

def login_view(request):
    if request.user.is_authenticated:
        # Redirect seller to dashboard, customer to home
        if hasattr(request.user, 'sellerprofile'):
            return redirect('seller_dashboard')
        return redirect('home')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        is_seller = request.POST.get('is_seller') == 'on'
        if form.is_valid():
            user = form.get_user()
            if is_seller:
                if hasattr(user, 'sellerprofile'):
                    login(request, user)
                    return redirect('seller_dashboard')
                else:
                    messages.error(request, "No seller account found for these credentials.")
            else:
                if hasattr(user, 'sellerprofile'):
                    messages.error(request, "This account is a seller. Please login as seller.")
                else:
                    login(request, user)
                    return redirect('home')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'shop/login.html', {'form': form})

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    seller_exists = SellerProfile.objects.exists()
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        is_seller = request.POST.get('is_seller') == 'on'
        if form.is_valid():
            if is_seller:
                if seller_exists:
                    # Update existing seller credentials
                    seller_profile = SellerProfile.objects.first()
                    seller_user = seller_profile.user
                    seller_user.username = form.cleaned_data['username']
                    seller_user.set_password(form.cleaned_data['password1'])
                    seller_user.save()
                    login(request, seller_user)
                else:
                    user = form.save()
                    SellerProfile.objects.create(user=user)
                    login(request, user)
                    return redirect('seller_dashboard')
            else:
                user = form.save()
                login(request, user)
                return redirect('home')
        else:
            messages.error(request, "Registration failed. Please correct the errors below.")
    else:
        form = UserCreationForm()
    return render(request, 'shop/register.html', {'form': form, 'seller_exists': seller_exists})

def logout_view(request):
    logout(request)
    return redirect('home')

def seller_dashboard(request):
    if not request.user.is_authenticated or not hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    return render(request, 'shop/seller_dashboard.html')
