from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib import messages
from .models import SellerProfile, Product, Order, OrderMessage
from django import forms
from django.forms import ModelForm
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from decimal import Decimal
import datetime

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

class OrderMessageForm(forms.ModelForm):
    class Meta:
        model = OrderMessage
        fields = ['text', 'image']

def catalog(request):
    products = Product.objects.all()
    return render(request, 'shop/catalog.html', {'products': products})

def order_list(request):
    if not request.user.is_authenticated or hasattr(request.user, 'sellerprofile'):
        return redirect('login')

    # handle message POST (keep same behavior, preserve querystring on redirect)
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

    # GET: filters / search / sort / paginate
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
        # NOTE: checkbox removed from logic — auto-detect seller by credentials
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
    products_qs = Product.objects.filter(created_by=seller_profile).order_by('-created_at')
    orders_qs = Order.objects.filter(product__created_by=seller_profile).order_by('-created_at')

    # analytics counts
    now = timezone.now()
    today = now.date()
    orders_today = orders_qs.filter(created_at__date=today).count()
    orders_last_7 = orders_qs.filter(created_at__gte=now - datetime.timedelta(days=7)).count()
    orders_last_30 = orders_qs.filter(created_at__gte=now - datetime.timedelta(days=30)).count()

    # totals
    total_products = products_qs.count()
    total_orders = orders_qs.count()

    # new analytics
    completed_qs = orders_qs.filter(done=True, cancelled=False)
    total_completed = completed_qs.count()
    total_cancelled = orders_qs.filter(cancelled=True).count()

    # Earnings per period
    earnings_today = completed_qs.filter(created_at__date=today).aggregate(
        total=Sum(
            ExpressionWrapper(F('product__price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    ).get('total') or Decimal('0.00')
    earnings_last_7 = completed_qs.filter(created_at__gte=now - datetime.timedelta(days=7)).aggregate(
        total=Sum(
            ExpressionWrapper(F('product__price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    ).get('total') or Decimal('0.00')
    earnings_last_30 = completed_qs.filter(created_at__gte=now - datetime.timedelta(days=30)).aggregate(
        total=Sum(
            ExpressionWrapper(F('product__price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    ).get('total') or Decimal('0.00')

    # Completed and Cancelled orders per period
    completed_today = completed_qs.filter(created_at__date=today).count()
    completed_last_7 = completed_qs.filter(created_at__gte=now - datetime.timedelta(days=7)).count()
    completed_last_30 = completed_qs.filter(created_at__gte=now - datetime.timedelta(days=30)).count()

    cancelled_today = orders_qs.filter(cancelled=True, created_at__date=today).count()
    cancelled_last_7 = orders_qs.filter(cancelled=True, created_at__gte=now - datetime.timedelta(days=7)).count()
    cancelled_last_30 = orders_qs.filter(cancelled=True, created_at__gte=now - datetime.timedelta(days=30)).count()

    earnings_agg = completed_qs.aggregate(
        total=Sum(
            ExpressionWrapper(F('product__price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    )
    total_earnings = earnings_agg.get('total') or Decimal('0.00')

    avg_order_value = (total_earnings / total_completed) if total_completed else Decimal('0.00')

    top_products = list(
        orders_qs.values('product__id', 'product__name')
        .annotate(total_qty=Sum('quantity'))
        .order_by('-total_qty')[:3]
    )

    products = products_qs[:5]
    orders = orders_qs[:5]

    # Helper for date ranges
    def daterange(start, end):
        for n in range((end - start).days + 1):
            yield start + datetime.timedelta(n)

    # Prepare time series for today (hourly), last 7 days (daily), last 30 days (daily), all time (daily)
    # Orders placed
    orders_placed_today = []
    for hour in range(24):
        start = datetime.datetime.combine(today, datetime.time(hour, 0, 0, tzinfo=now.tzinfo))
        end = start + datetime.timedelta(hours=1)
        count = orders_qs.filter(created_at__gte=start, created_at__lt=end).count()
        orders_placed_today.append({'label': f"{hour}:00", 'value': count})

    orders_placed_7 = []
    for d in daterange(today - datetime.timedelta(days=6), today):
        count = orders_qs.filter(created_at__date=d).count()
        orders_placed_7.append({'label': d.strftime("%b %d"), 'value': count})

    orders_placed_30 = []
    for d in daterange(today - datetime.timedelta(days=29), today):
        count = orders_qs.filter(created_at__date=d).count()
        orders_placed_30.append({'label': d.strftime("%b %d"), 'value': count})

    orders_placed_all = []
    if orders_qs.exists():
        first_date = orders_qs.order_by('created_at').first().created_at.date()
        for d in daterange(first_date, today):
            count = orders_qs.filter(created_at__date=d).count()
            orders_placed_all.append({'label': d.strftime("%b %d"), 'value': count})

    # Earnings (completed only)
    def earnings_for_qs(qs, start, end, by='hour'):
        result = []
        if by == 'hour':
            for hour in range(24):
                s = datetime.datetime.combine(start, datetime.time(hour, 0, 0, tzinfo=now.tzinfo))
                e = s + datetime.timedelta(hours=1)
                total = qs.filter(created_at__gte=s, created_at__lt=e).aggregate(
                    total=Sum(ExpressionWrapper(F('product__price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=2)))
                )['total'] or Decimal('0.00')
                result.append({'label': f"{hour}:00", 'value': float(total)})
        else:
            for d in daterange(start, end):
                total = qs.filter(created_at__date=d).aggregate(
                    total=Sum(ExpressionWrapper(F('product__price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=2)))
                )['total'] or Decimal('0.00')
                result.append({'label': d.strftime("%b %d"), 'value': float(total)})
        return result

    earnings_today_series = earnings_for_qs(completed_qs, today, today, by='hour')
    earnings_7_series = earnings_for_qs(completed_qs, today - datetime.timedelta(days=6), today, by='day')
    earnings_30_series = earnings_for_qs(completed_qs, today - datetime.timedelta(days=29), today, by='day')
    earnings_all_series = []
    if completed_qs.exists():
        first_date = completed_qs.order_by('created_at').first().created_at.date()
        earnings_all_series = earnings_for_qs(completed_qs, first_date, today, by='day')

    # Completed and Cancelled orders per period
    def status_series(qs_completed, qs_cancelled, start, end, by='hour'):
        completed, cancelled = [], []
        if by == 'hour':
            for hour in range(24):
                s = datetime.datetime.combine(start, datetime.time(hour, 0, 0, tzinfo=now.tzinfo))
                e = s + datetime.timedelta(hours=1)
                completed.append({'label': f"{hour}:00", 'value': qs_completed.filter(created_at__gte=s, created_at__lt=e).count()})
                cancelled.append({'label': f"{hour}:00", 'value': qs_cancelled.filter(created_at__gte=s, created_at__lt=e).count()})
        else:
            for d in daterange(start, end):
                completed.append({'label': d.strftime("%b %d"), 'value': qs_completed.filter(created_at__date=d).count()})
                cancelled.append({'label': d.strftime("%b %d"), 'value': qs_cancelled.filter(created_at__date=d).count()})
        return completed, cancelled

    cancelled_qs = orders_qs.filter(cancelled=True)
    completed_today_series, cancelled_today_series = status_series(completed_qs, cancelled_qs, today, today, by='hour')
    completed_7_series, cancelled_7_series = status_series(completed_qs, cancelled_qs, today - datetime.timedelta(days=6), today, by='day')
    completed_30_series, cancelled_30_series = status_series(completed_qs, cancelled_qs, today - datetime.timedelta(days=29), today, by='day')
    completed_all_series, cancelled_all_series = [], []
    if orders_qs.exists():
        first_date = orders_qs.order_by('created_at').first().created_at.date()
        completed_all_series, cancelled_all_series = status_series(completed_qs, cancelled_qs, first_date, today, by='day')

    # Earnings per period
    earnings_today = completed_qs.filter(created_at__date=today).aggregate(
        total=Sum(
            ExpressionWrapper(F('product__price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    ).get('total') or Decimal('0.00')
    earnings_last_7 = completed_qs.filter(created_at__gte=now - datetime.timedelta(days=7)).aggregate(
        total=Sum(
            ExpressionWrapper(F('product__price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    ).get('total') or Decimal('0.00')
    earnings_last_30 = completed_qs.filter(created_at__gte=now - datetime.timedelta(days=30)).aggregate(
        total=Sum(
            ExpressionWrapper(F('product__price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    ).get('total') or Decimal('0.00')

    # Completed and Cancelled orders per period
    completed_today = completed_qs.filter(created_at__date=today).count()
    completed_last_7 = completed_qs.filter(created_at__gte=now - datetime.timedelta(days=7)).count()
    completed_last_30 = completed_qs.filter(created_at__gte=now - datetime.timedelta(days=30)).count()

    cancelled_today = orders_qs.filter(cancelled=True, created_at__date=today).count()
    cancelled_last_7 = orders_qs.filter(cancelled=True, created_at__gte=now - datetime.timedelta(days=7)).count()
    cancelled_last_30 = orders_qs.filter(cancelled=True, created_at__gte=now - datetime.timedelta(days=30)).count()

    earnings_agg = completed_qs.aggregate(
        total=Sum(
            ExpressionWrapper(F('product__price') * F('quantity'), output_field=DecimalField(max_digits=12, decimal_places=2))
        )
    )
    total_earnings = earnings_agg.get('total') or Decimal('0.00')

    avg_order_value = (total_earnings / total_completed) if total_completed else Decimal('0.00')

    top_products = list(
        orders_qs.values('product__id', 'product__name')
        .annotate(total_qty=Sum('quantity'))
        .order_by('-total_qty')[:3]
    )

    products = products_qs[:5]
    orders = orders_qs[:5]

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

    # Add time series for graphs
    return render(request, 'shop/seller_dashboard.html', {
        'form': form,
        'products': products,
        'orders': orders,
        'orders_today': orders_today,
        'orders_last_7': orders_last_7,
        'orders_last_30': orders_last_30,
        'total_products': total_products,
        'total_orders': total_orders,
        'total_earnings': total_earnings,
        'total_completed': total_completed,
        'total_cancelled': total_cancelled,
        'avg_order_value': avg_order_value,
        'top_products': top_products,
        # New context for analytics graphs
        'orders_placed_today': orders_placed_today,
        'orders_placed_7': orders_placed_7,
        'orders_placed_30': orders_placed_30,
        'orders_placed_all': orders_placed_all,
        'earnings_today_series': earnings_today_series,
        'earnings_7_series': earnings_7_series,
        'earnings_30_series': earnings_30_series,
        'earnings_all_series': earnings_all_series,
        'completed_today_series': completed_today_series,
        'completed_7_series': completed_7_series,
        'completed_30_series': completed_30_series,
        'completed_all_series': completed_all_series,
        'cancelled_today_series': cancelled_today_series,
        'cancelled_7_series': cancelled_7_series,
        'cancelled_30_series': cancelled_30_series,
        'cancelled_all_series': cancelled_all_series,
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
                order.status = 'waiting'  # set default status
                order.save()
                product.stock -= quantity
                product.save()
                messages.success(request, "Order placed!")
                return redirect('order_list')
    else:
        form = OrderForm()
    return render(request, 'shop/product_order.html', {'product': product, 'form': form, 'error': error})

# New: customer order detail/manage page (separate page instead of inline collapse)
def customer_manage_order(request, order_id):
    if not request.user.is_authenticated or hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    order = get_object_or_404(Order, id=order_id, customer=request.user)
    error = None
    if request.method == 'POST':
        # Cancellation takes precedence when cancel_order button is present
        if 'cancel_order' in request.POST:
            if order.cancelled:
                messages.error(request, "Order is already cancelled.")
            elif order.done:
                messages.error(request, "Completed orders cannot be cancelled.")
            else:
                cancel_reason = request.POST.get('cancel_reason', '').strip()
                if not cancel_reason:
                    messages.error(request, "Please provide a reason for cancellation.")
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
                        messages.warning(request, "Order cancelled but failed to restore stock automatically.")
                    order.save()
                    messages.success(request, "Order cancelled.")
                    return redirect('order_list')
        else:
            # Handle sending a message
            msg_form = OrderMessageForm(request.POST, request.FILES)
            if msg_form.is_valid():
                msg = msg_form.save(commit=False)
                msg.order = order
                msg.sender = request.user
                msg.save()
                messages.success(request, "Message sent.")
                return redirect('customer_manage_order', order_id=order.id)
            else:
                messages.error(request, "Failed to send message. Please correct errors below.")
    else:
        msg_form = OrderMessageForm()
    return render(request, 'shop/customer_manage_order.html', {
        'order': order,
        'msg_form': msg_form,
        'error': error,
    })

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
    })

def manage_orders_list(request):
    """Seller: list orders (10/page) with simple filters: status, cancelled, sort_by, sort_dir."""
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

    # NOTE: advanced date filters removed

    # safe ordering: only allow specific fields (simplified)
    allowed_order_fields = {'created_at', 'delivered_at'}
    if sort_by not in allowed_order_fields:
        sort_by = 'created_at'
    order_field = sort_by if sort_dir == 'asc' else f"-{sort_by}"
    qs = qs.order_by(order_field)

    # paginate
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

def manage_products_list(request):
    """Seller: list products (10/page) with search and simple sorting."""
    if not request.user.is_authenticated or not hasattr(request.user, 'sellerprofile'):
        return redirect('login')
    seller_profile = request.user.sellerprofile

    # handle stock update POST
    if request.method == 'POST' and 'update_stock' in request.POST:
        product_id = request.POST.get('product_id')
        new_stock = request.POST.get('new_stock')
        try:
            product = Product.objects.get(id=product_id, created_by=seller_profile)
            product.stock = max(0, int(new_stock))
            product.save()
            messages.success(request, f"Stock updated for {product.name}!")
        except Exception:
            messages.error(request, "Failed to update stock.")
        qs = request.META.get('QUERY_STRING', '')
        return redirect(request.path + (f"?{qs}" if qs else ""))

    qs = Product.objects.filter(created_by=seller_profile)

    # simple sorting controls
    sort_by = request.GET.get('sort_by', 'created_at')  # price, stock, created_at
    sort_dir = request.GET.get('sort_dir', 'desc')  # asc or desc

    # search for specific products
    search = request.GET.get('search', '').strip()
    if search:
        qs = qs.filter(name__icontains=search)

    # NOTE: advanced min/max/date filters removed

    # safe ordering for products
    allowed_order_fields = {'price', 'stock', 'created_at'}
    if sort_by not in allowed_order_fields:
        sort_by = 'created_at'
    order_field = sort_by if sort_dir == 'asc' else f"-{sort_by}"
    qs = qs.order_by(order_field)

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
