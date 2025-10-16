from django.db import models
from django.contrib.auth.models import User

class SellerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    def __str__(self):
        return f"Seller: {self.user.username}"

class Product(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='product_images/')
    created_by = models.ForeignKey(SellerProfile, on_delete=models.CASCADE)
    stock = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def __str__(self):
        return self.name

class Order(models.Model):
    STATUS_CHOICES = [
        ('waiting', 'Waiting for Payment'),
        ('pending', 'Pending Creation'),
        ('created', 'Finished Creating the Bracelet'),
        ('delivering', 'Bracelet is Being Delivered'),
        ('delivered', 'Bracelet Delivered'),
    ]
    PAYMENT_CHOICES = [
        ('gcash', 'GCash'),
        ('maya', 'Maya'),
    ]
    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    payment_type = models.CharField(max_length=20, choices=PAYMENT_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(blank=True, null=True)
    done = models.BooleanField(default=False)
    cancelled = models.BooleanField(default=False)
    cancel_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Order #{self.id} - {self.product.name} ({self.customer.username})"

class OrderMessage(models.Model):
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(blank=True)
    image = models.ImageField(upload_to='order_messages/', blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Message for Order #{self.order.id} by {self.sender.username}"

class CustomBraceletDesign(models.Model):
    name = models.CharField(max_length=100)
    beads = models.JSONField()  # List of dicts: [{shape, color, size}, ...]
    created_at = models.DateTimeField(auto_now_add=True)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bracelet_designs')

    def __str__(self):
        return f"{self.name} ({self.customer.username})"

    def text_form(self):
        # Returns a list of bead descriptions for vertical dropdown display
        bead_names = {
            'circle': 'Circle',
            'square': 'Square',
            'triangle': 'Triangle',
        }
        color_names = {
            '#ff0000': 'Red',
            '#0000ff': 'Blue',
            '#00ff00': 'Green',
            '#ffff00': 'Yellow',
            '#ff00ff': 'Magenta',
            '#00ffff': 'Cyan',
            '#ffffff': 'White',
            '#000000': 'Black',
        }
        size_names = {
            'small': 'Small',
            'medium': 'Medium',
            'large': 'Large',
        }
        parts = []
        for idx, b in enumerate(self.beads, 1):
            color = color_names.get(b.get('color'), b.get('color', 'Unknown'))
            size = size_names.get(b.get('size'), b.get('size', 'Unknown'))
            shape = bead_names.get(b.get('shape'), b.get('shape', 'Unknown'))
            parts.append(f"{idx}. {color} {size} {shape}")
        return parts
