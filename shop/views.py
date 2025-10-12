from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib import messages
from .models import SellerProfile
from django.contrib.auth.models import User
from django import forms

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

class SellerUpdateForm(forms.ModelForm):
    password1 = forms.CharField(label='New password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm password', widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ['username']

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            self.add_error('password2', "Passwords do not match.")
        return cleaned_data

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    seller_exists = SellerProfile.objects.exists()
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        is_seller = request.POST.get('is_seller') == 'on'
        if form.is_valid():
            if is_seller and not seller_exists:
                user = form.save()
                user.is_superuser = True
                user.is_staff = True
                user.save()
                SellerProfile.objects.create(user=user)
                login(request, user)
                return redirect('seller_dashboard')
            elif is_seller and seller_exists:
                messages.error(request, "Seller account already exists.")
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

def update_seller_view(request):
    seller_profile = SellerProfile.objects.first()
    if not seller_profile:
        return redirect('register')
    seller_user = seller_profile.user
    if request.method == 'POST':
        form = SellerUpdateForm(request.POST, instance=seller_user)
        if form.is_valid():
            seller_user.username = form.cleaned_data['username']
            seller_user.set_password(form.cleaned_data['password1'])
            seller_user.is_superuser = True
            seller_user.is_staff = True
            seller_user.save()
            messages.success(request, "Seller credentials updated successfully.")
            return redirect('login')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SellerUpdateForm(instance=seller_user)
    return render(request, 'shop/update_seller.html', {'form': form})

def customize_bracelet(request):
    if not request.user.is_authenticated or hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    return render(request, 'shop/customize_bracelet.html')
