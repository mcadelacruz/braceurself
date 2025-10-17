# standard library imports
import datetime
import json
from decimal import Decimal

# django imports
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.forms import ModelForm
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django import forms


# local application imports
from .models import (CustomBraceletDesign, Order, OrderMessage, Product,
                     SellerProfile)


# handles the home page
def home(request):
    return render(request, 'shop/home.html')


# form for creating and updating products
class ProductForm(ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'price', 'image', 'stock']


# form for placing an order
class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['quantity', 'payment_type']


# form for sending messages on an order
class OrderMessageForm(forms.ModelForm):
    class Meta:
        model = OrderMessage
        fields = ['text', 'image']


# displays the product catalog
def catalog(request):
    products = Product.objects.all()
    return render(request, 'shop/catalog.html', {'products': products})


# handles the customer's list of orders
def order_list(request):
    # authentication check
    if not request.user.is_authenticated or hasattr(request.user, 'sellerprofile'):
        return redirect('login')

    # handles sending a message on an order
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        try:
            order = Order.objects.get(id=order_id, customer=request.user)
        except Order.DoesNotExist:
            messages.error(request, "Order not found.")
            qs = request.META.get('QUERY_STRING', '')
            return redirect(request.path + (f"?{qs}" if qs else ""))
        msg_form = OrderMessageForm(request.POST, request.FILES)
        if msg_form.is_valid():
            msg = msg_form.save(commit=False)
            msg.order = order
            msg.sender = request.user
            msg.save()
            messages.success(request, "Message sent.")
        else:
            messages.error(request, "Failed to send message.")
        qs = request.META.get('QUERY_STRING', '')
        return redirect(request.path + (f"?{qs}" if qs else ""))

    # handles filtering, searching, and sorting for the order list
    qs = Order.objects.filter(customer=request.user)

    status = request.GET.get('status', '')
    cancelled = request.GET.get('cancelled', '')  # 'yes' / 'no' / ''
    sort_by = request.GET.get('sort_by', 'created_at')
    sort_dir = request.GET.get('sort_dir', 'desc')
    search = request.GET.get('search', '').strip()

    if status:
        qs = qs.filter(status=status)
    if cancelled == 'yes':
        qs = qs.filter(cancelled=True)
    elif cancelled == 'no':
        qs = qs.filter(cancelled=False)

    if search:
        qs = qs.filter(product__name__icontains=search)

    allowed_order_fields = {'created_at', 'delivered_at'}
    if sort_by not in allowed_order_fields:
        sort_by = 'created_at'
    order_field = sort_by if sort_dir == 'asc' else f"-{sort_by}"
    qs = qs.order_by(order_field)

    # handles pagination
    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # prepare empty message forms for visible orders
    msg_forms = {order.id: OrderMessageForm() for order in page_obj.object_list}

    return render(request, 'shop/order_list.html', {
        'page_obj': page_obj,
        'msg_forms': msg_forms,
        'filters': {
            'status': status,
            'cancelled': cancelled,
            'sort_by': sort_by,
            'sort_dir': sort_dir,
            'search': search,
        },
        'status_choices': Order.STATUS_CHOICES,
    })


# page to choose between login and register
def login_register(request):
    return render(request, 'shop/login_register.html')


# handles user login
def login_view(request):
    if request.user.is_authenticated:
        # Redirect seller to dashboard, customer to home
        if hasattr(request.user, 'sellerprofile'):
            return redirect('seller_dashboard')
        return redirect('home')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            # If this user has a SellerProfile, treat them as seller
            if hasattr(user, 'sellerprofile'):
                login(request, user)
                return redirect('seller_dashboard')
            # Otherwise treat as regular customer
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()
    return render(request, 'shop/login.html', {'form': form})


# form for updating seller credentials
class SellerUpdateForm(forms.ModelForm):
    password1 = forms.CharField(
        label='New password', widget=forms.PasswordInput)
    password2 = forms.CharField(
        label='Confirm password', widget=forms.PasswordInput)

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


# handles new user registration
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
            messages.error(
                request, "Registration failed. Please correct the errors below.")
    else:
        form = UserCreationForm()
    return render(request, 'shop/register.html', {'form': form, 'seller_exists': seller_exists})


# handles user logout
def logout_view(request):
    logout(request)
    return redirect('home')


# handles the seller dashboard page
def seller_dashboard(request):
    # authentication check
    if not request.user.is_authenticated or not hasattr(request.user, 'sellerprofile'):
        return redirect('login')

    seller_profile = request.user.sellerprofile
    products_qs = Product.objects.filter(
        created_by=seller_profile).order_by('-created_at')
    orders_qs = Order.objects.filter(
        product__created_by=seller_profile).order_by('-created_at')

    # handles product creation and stock updates
    if request.method == 'POST':
        if 'update_stock' in request.POST:
            product_id = request.POST.get('product_id')
            new_stock = request.POST.get('new_stock')
            try:
                product = Product.objects.get(
                    id=product_id, created_by=seller_profile)
                product.stock = int(new_stock)
                product.save()
                messages.success(
                    request, f"Stock updated for {product.name}!")
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

    # analytics for the page
    now = timezone.now()
    today = now.date()
    completed_qs = orders_qs.filter(done=True, cancelled=False)
    cancelled_qs = orders_qs.filter(cancelled=True)

    # totals
    total_products = products_qs.count()
    total_orders = orders_qs.count()
    total_completed = completed_qs.count()
    total_cancelled = cancelled_qs.count()

    # earnings calculation
    total_earnings = completed_qs.aggregate(
        total=Sum(
            ExpressionWrapper(F('product__price') * F('quantity'),
                              output_field=DecimalField(max_digits=12, decimal_places=2)))
    ).get('total') or Decimal('0.00')

    avg_order_value = (
        total_earnings / total_completed) if total_completed else Decimal('0.00')

    # top products
    top_products = list(
        orders_qs.values('product__id', 'product__name')
        .annotate(total_qty=Sum('quantity'))
        .order_by('-total_qty')[:3]
    )

    # recent products and orders for display
    products = products_qs[:5]
    orders = orders_qs[:5]

    # helper for date ranges
    def daterange(start, end):
        for n in range((end - start).days + 1):
            yield start + datetime.timedelta(n)

    # data for graphs
    def get_series_by_period(qs, start, end, by='hour', field=None):
        series = []
        if by == 'hour':
            for hour in range(24):
                s = datetime.datetime.combine(
                    start, datetime.time(hour, 0, 0, tzinfo=now.tzinfo))
                e = s + datetime.timedelta(hours=1)
                qs_in_period = qs.filter(created_at__gte=s, created_at__lt=e)
                if field == 'earnings':
                    total = qs_in_period.aggregate(
                        total=Sum(ExpressionWrapper(F('product__price') * F('quantity'),
                                                    output_field=DecimalField(max_digits=12, decimal_places=2)))
                    )['total'] or Decimal('0.00')
                    series.append({'label': f"{hour}:00", 'value': float(total)})
                else:
                    series.append(
                        {'label': f"{hour}:00", 'value': qs_in_period.count()})
        else:  # by day
            for d in daterange(start, end):
                qs_in_period = qs.filter(created_at__date=d)
                if field == 'earnings':
                    total = qs_in_period.aggregate(
                        total=Sum(ExpressionWrapper(F('product__price') * F('quantity'),
                                                    output_field=DecimalField(max_digits=12, decimal_places=2)))
                    )['total'] or Decimal('0.00')
                    series.append(
                        {'label': d.strftime("%b %d"), 'value': float(total)})
                else:
                    series.append(
                        {'label': d.strftime("%b %d"), 'value': qs_in_period.count()})
        return series

    # time series data
    first_order_date = orders_qs.order_by(
        'created_at').first().created_at.date() if orders_qs.exists() else today
    first_completed_date = completed_qs.order_by(
        'created_at').first().created_at.date() if completed_qs.exists() else today

    context = {
        'form': form,
        'products': products,
        'orders': orders,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_earnings': total_earnings,
        'total_completed': total_completed,
        'total_cancelled': total_cancelled,
        'avg_order_value': avg_order_value,
        'top_products': top_products,

        # analytics graphs data
        'orders_placed_today': get_series_by_period(orders_qs, today, today, by='hour'),
        'orders_placed_7': get_series_by_period(orders_qs, today - datetime.timedelta(days=6), today, by='day'),
        'orders_placed_30': get_series_by_period(orders_qs, today - datetime.timedelta(days=29), today, by='day'),
        'orders_placed_all': get_series_by_period(orders_qs, first_order_date, today, by='day'),

        'earnings_today_series': get_series_by_period(completed_qs, today, today, by='hour', field='earnings'),
        'earnings_7_series': get_series_by_period(completed_qs, today - datetime.timedelta(days=6), today, by='day', field='earnings'),
        'earnings_30_series': get_series_by_period(completed_qs, today - datetime.timedelta(days=29), today, by='day', field='earnings'),
        'earnings_all_series': get_series_by_period(completed_qs, first_completed_date, today, by='day', field='earnings'),

        'completed_today_series': get_series_by_period(completed_qs, today, today, by='hour'),
        'completed_7_series': get_series_by_period(completed_qs, today - datetime.timedelta(days=6), today, by='day'),
        'completed_30_series': get_series_by_period(completed_qs, today - datetime.timedelta(days=29), today, by='day'),
        'completed_all_series': get_series_by_period(completed_qs, first_completed_date, today, by='day'),

        'cancelled_today_series': get_series_by_period(cancelled_qs, today, today, by='hour'),
        'cancelled_7_series': get_series_by_period(cancelled_qs, today - datetime.timedelta(days=6), today, by='day'),
        'cancelled_30_series': get_series_by_period(cancelled_qs, today - datetime.timedelta(days=29), today, by='day'),
        'cancelled_all_series': get_series_by_period(cancelled_qs, first_order_date, today, by='day'),
    }

    return render(request, 'shop/seller_dashboard.html', context)


# handles placing an order for a product
def product_order(request, product_id):
    if not request.user.is_authenticated or hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    product = get_object_or_404(Product, id=product_id)
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
                order.status = 'waiting'  # set default status
                order.save()
                product.stock -= quantity
                product.save()
                messages.success(request, "Order placed!")
                return redirect('order_list')
    else:
        form = OrderForm()
    return render(request, 'shop/product_order.html', {'product': product, 'form': form, 'error': error})


# handles the customer's view for managing a single order
def customer_manage_order(request, order_id):
    if not request.user.is_authenticated or hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    # Try to get custom design if this is a custom bracelet order
    custom_design = None
    if order.product and order.product.name.startswith("Custom:"):
        custom_design = CustomBraceletDesign.objects.filter(
            name=order.product.name.replace("Custom: ", ""),
            customer=request.user
        ).first()
    error = None
    if request.method == 'POST':
        # handles order cancellation
        if 'cancel_order' in request.POST:
            if order.cancelled:
                messages.error(request, "Order is already cancelled.")
            elif order.done:
                messages.error(
                    request, "Completed orders cannot be cancelled.")
            else:
                cancel_reason = request.POST.get('cancel_reason', '').strip()
                if not cancel_reason:
                    messages.error(
                        request, "Please provide a reason for cancellation.")
                else:
                    # mark cancelled and restore stock
                    order.cancelled = True
                    order.cancel_reason = cancel_reason
                    try:
                        product = order.product
                        product.stock += order.quantity
                        product.save()
                    except Exception:
                        # continue even if stock restore fails, but log message for user
                        messages.warning(
                            request, "Order cancelled but failed to restore stock automatically.")
                    order.save()
                    messages.success(request, "Order cancelled.")
                    return redirect('order_list')
        else:
            # handles sending a message
            msg_form = OrderMessageForm(request.POST, request.FILES)
            if msg_form.is_valid():
                msg = msg_form.save(commit=False)
                msg.order = order
                msg.sender = request.user
                msg.save()
                messages.success(request, "Message sent.")
                return redirect('customer_manage_order', order_id=order.id)
            else:
                messages.error(
                    request, "Failed to send message. Please correct errors below.")
    else:
        msg_form = OrderMessageForm()
    return render(request, 'shop/customer_manage_order.html', {
        'order': order,
        'msg_form': msg_form,
        'error': error,
        'custom_design': custom_design,
    })


# handles the seller's view for managing a single order
def manage_order(request, order_id):
    if not request.user.is_authenticated or not hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    order = get_object_or_404(Order, id=order_id)
    # Try to get custom design if this is a custom bracelet order
    custom_design = None
    if order.product and order.product.name.startswith("Custom:"):
        custom_design = CustomBraceletDesign.objects.filter(
            name=order.product.name.replace("Custom: ", ""),
            customer=order.customer
        ).first()
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
            order.delivered_at = timezone.now()  # set delivered timestamp
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
        if 'send_message' in request.POST:
            msg_form = OrderMessageForm(request.POST, request.FILES)
            if msg_form.is_valid():
                msg = msg_form.save(commit=False)
                msg.order = order
                msg.sender = request.user
                msg.save()
                messages.success(request, "Message sent.")
                return redirect('manage_order', order_id=order.id)
        if updated and not error:
            order.save()
            messages.success(request, "Order updated.")
            # stay on the same manage_order page to show updated state
            return redirect('manage_order', order_id=order.id)
    else:
        msg_form = OrderMessageForm()
    return render(request, 'shop/manage_order.html', {
        'order': order,
        'status_choices': Order.STATUS_CHOICES,
        'error': error,
        'msg_form': msg_form,
        'custom_design': custom_design,
    })


# handles the seller's list of all orders
def manage_orders_list(request):
    if not request.user.is_authenticated or not hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    seller_profile = request.user.sellerprofile
    qs = Order.objects.filter(product__created_by=seller_profile)

    # filters from GET
    status = request.GET.get('status')
    cancelled = request.GET.get('cancelled')  # 'yes' or 'no' or ''

    # Sorting controls
    sort_by = request.GET.get('sort_by', 'created_at')
    sort_dir = request.GET.get('sort_dir', 'desc')  # 'asc' or 'desc'

    # apply simple filters
    if status:
        qs = qs.filter(status=status)
    if cancelled == 'yes':
        qs = qs.filter(cancelled=True)
    elif cancelled == 'no':
        qs = qs.filter(cancelled=False)

    # safe ordering: only allow specific fields
    allowed_order_fields = {'created_at', 'delivered_at'}
    if sort_by not in allowed_order_fields:
        sort_by = 'created_at'
    order_field = sort_by if sort_dir == 'asc' else f"-{sort_by}"
    qs = qs.order_by(order_field)

    # handles pagination
    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'shop/manage_orders.html', {
        'page_obj': page_obj,
        'filters': {
            'status': status or '',
            'cancelled': cancelled or '',
            'sort_by': sort_by,
            'sort_dir': sort_dir,
        },
        'status_choices': Order.STATUS_CHOICES,
    })


# handles the seller's list of all products
def manage_products_list(request):
    if not request.user.is_authenticated or not hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    seller_profile = request.user.sellerprofile

    # handles stock update POST
    if request.method == 'POST' and 'update_stock' in request.POST:
        product_id = request.POST.get('product_id')
        new_stock = request.POST.get('new_stock')
        try:
            product = Product.objects.get(
                id=product_id, created_by=seller_profile)
            product.stock = max(0, int(new_stock))
            product.save()
            messages.success(request, f"Stock updated for {product.name}!")
        except Exception:
            messages.error(request, "Failed to update stock.")
        qs = request.META.get('QUERY_STRING', '')
        return redirect(request.path + (f"?{qs}" if qs else ""))

    qs = Product.objects.filter(created_by=seller_profile)

    # simple sorting controls
    sort_by = request.GET.get('sort_by', 'created_at')
    sort_dir = request.GET.get('sort_dir', 'desc')

    # search for specific products
    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(name__icontains=search)

    # safe ordering for products
    allowed_order_fields = {'price', 'stock', 'created_at'}
    if sort_by not in allowed_order_fields:
        sort_by = 'created_at'
    order_field = sort_by if sort_dir == 'asc' else f"-{sort_by}"
    qs = qs.order_by(order_field)

    # handles pagination
    paginator = Paginator(qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'shop/manage_products.html', {
        'page_obj': page_obj,
        'filters': {
            'search': search or '',
            'sort_by': sort_by,
            'sort_dir': sort_dir,
        },
    })


# handles updating the seller's credentials
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
            messages.success(
                request, "Seller credentials updated successfully.")
            return redirect('login')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = SellerUpdateForm(instance=seller_user)
    return render(request, 'shop/update_seller.html', {'form': form})


# page for customers to view their custom designs
def customize_bracelet(request):
    if not request.user.is_authenticated or hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    # handles deleting a design
    if request.method == 'POST' and 'delete_design_id' in request.POST:
        design_id = request.POST.get('delete_design_id')
        design = CustomBraceletDesign.objects.filter(
            id=design_id, customer=request.user).first()
        if design:
            design.delete()
            messages.success(request, "Custom bracelet design deleted.")
        else:
            messages.error(request, "Design not found or not yours.")
        return redirect('customize_bracelet')
    designs = CustomBraceletDesign.objects.filter(
        customer=request.user).order_by('-created_at')
    return render(request, 'shop/customize_bracelet.html', {
        'designs': designs,
    })


# page for creating a new custom bracelet design
def bracelet_designer(request):
    if not request.user.is_authenticated or hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        beads = request.POST.get('beads', '[]')
        try:
            beads_list = json.loads(beads)
        except Exception:
            beads_list = []
        if not name or not (15 <= len(beads_list) <= 25):
            messages.error(
                request, "Name required and design must have 15-25 beads.")
            return render(request, 'shop/bracelet_designer.html', {
                'name': name,
                'beads': beads,
            })
        design = CustomBraceletDesign.objects.create(
            name=name,
            beads=beads_list,
            customer=request.user
        )
        messages.success(request, "Design saved!")
        return redirect('bracelet_design_detail', design_id=design.id)
    return render(request, 'shop/bracelet_designer.html')


# displays the details of a single custom bracelet design
def bracelet_design_detail(request, design_id):
    design = get_object_or_404(CustomBraceletDesign, id=design_id)
    return render(request, 'shop/bracelet_design_detail.html', {
        'design': design,
    })


# handles placing an order for a custom bracelet design
def order_custom_bracelet(request, design_id):
    if not request.user.is_authenticated or hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    design = get_object_or_404(CustomBraceletDesign, id=design_id)
    if request.method == 'POST':
        # Find seller (assume only one seller profile)
        seller_profile = SellerProfile.objects.first()
        # Create a Product for this custom design if needed
        product = Product.objects.create(
            name=f"Custom: {design.name}",
            price=Decimal('0.00'),
            image=None,
            created_by=seller_profile,
            stock=0
        )
        # Create an Order for this design
        Order.objects.create(
            customer=request.user,
            product=product,
            quantity=1,
            payment_type=request.POST.get('payment_type', 'gcash'),
            status='waiting',
        )
        messages.success(request, "Custom bracelet order placed!")
        return redirect('order_list')
    return render(request, 'shop/order_custom_bracelet.html', {
        'design': design,
    })


# displays a list of public custom designs made by other users
def public_custom_designs(request):
    if not request.user.is_authenticated:
        return redirect('login')
    # Show all designs except own if customer, or all if seller
    if hasattr(request.user, 'sellerprofile'):
        designs = CustomBraceletDesign.objects.all().order_by('-created_at')
        can_order = False
    else:
        designs = CustomBraceletDesign.objects.exclude(
            customer=request.user).order_by('-created_at')
        can_order = True
    return render(request, 'shop/public_custom_designs.html', {
        'designs': designs,
        'can_order': can_order,
    })