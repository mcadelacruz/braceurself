from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib import messages
from .models import SellerProfile, Product, Order
from django import forms
from django.forms import ModelForm
from django.contrib.auth.models import User

def home(request):
    return render(request, 'shop/home.html')

class ProductForm(ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'price', 'image', 'stock']

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['quantity', 'payment_type']

def catalog(request):
    products = Product.objects.all()
    return render(request, 'shop/catalog.html', {'products': products})

def order_list(request):
    if not request.user.is_authenticated or hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    orders = Order.objects.filter(customer=request.user).order_by('-created_at')
    return render(request, 'shop/order_list.html', {'orders': orders})

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
    seller_profile = request.user.sellerprofile
    products = Product.objects.filter(created_by=seller_profile)
    orders = Order.objects.filter(product__created_by=seller_profile).order_by('-created_at')
    if request.method == 'POST':
        if 'update_stock' in request.POST:
            product_id = request.POST.get('product_id')
            new_stock = request.POST.get('new_stock')
            try:
                product = Product.objects.get(id=product_id, created_by=seller_profile)
                product.stock = int(new_stock)
                product.save()
                messages.success(request, f"Stock updated for {product.name}!")
            except Exception:
                messages.error(request, "Failed to update stock.")
            return redirect('seller_dashboard')
        else:
            form = ProductForm(request.POST, request.FILES)
            if form.is_valid():
                product = form.save(commit=False)
                product.created_by = seller_profile
                product.save()
                messages.success(request, "Product added!")
                return redirect('seller_dashboard')
    else:
        form = ProductForm()
    return render(request, 'shop/seller_dashboard.html', {
        'form': form,
        'products': products,
        'orders': orders,
    })

def product_order(request, product_id):
    if not request.user.is_authenticated or hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    product = Product.objects.get(id=product_id)
    error = None
    if product.stock <= 0:
        error = "This product is out of stock."
    if request.method == 'POST' and not error:
        form = OrderForm(request.POST)
        if form.is_valid():
            quantity = form.cleaned_data['quantity']
            if quantity > product.stock:
                error = "Not enough stock available."
            else:
                order = form.save(commit=False)
                order.customer = request.user
                order.product = product
                order.status = 'pending'
                order.save()
                product.stock -= quantity
                product.save()
                messages.success(request, "Order placed!")
                return redirect('order_list')
    else:
        form = OrderForm()
    return render(request, 'shop/product_order.html', {'product': product, 'form': form, 'error': error})

def manage_order(request, order_id):
    if not request.user.is_authenticated or not hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    order = Order.objects.get(id=order_id)
    error = None
    if request.method == 'POST':
        status = request.POST.get('status')
        mark_done = request.POST.get('mark_done')
        cancel_order = request.POST.get('cancel_order')
        cancel_reason = request.POST.get('cancel_reason')
        updated = False
        if status and status in dict(Order.STATUS_CHOICES):
            order.status = status
            updated = True
        if mark_done == 'on' and order.status == 'delivered' and not order.cancelled:
            order.done = True
            updated = True
        if cancel_order == 'on' and not order.cancelled:
            if cancel_reason and cancel_reason.strip():
                order.cancelled = True
                order.cancel_reason = cancel_reason.strip()
                # Restore stock
                order.product.stock += order.quantity
                order.product.save()
                updated = True
            else:
                error = "Please provide a reason for cancellation."
        if updated and not error:
            order.save()
            messages.success(request, "Order updated.")
            return redirect('seller_dashboard')
    return render(request, 'shop/manage_order.html', {
        'order': order,
        'status_choices': Order.STATUS_CHOICES,
        'error': error,
    })

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
