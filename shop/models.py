# defines the database tables for the application
from django.db import models
from django.contrib.auth.models import User

# model for the seller's profile
class SellerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    # string representation of the seller profile
    def __str__(self):
        return f"Seller: {self.user.username}"

# model for the products
class Product(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='product_images/')
    created_by = models.ForeignKey(SellerProfile, on_delete=models.CASCADE)
    stock = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    # string representation of the product
    def __str__(self):
        return self.name

# model for the orders
class Order(models.Model):
    # choices for order status
    STATUS_CHOICES = [
        ('waiting', 'Waiting for Payment'),
        ('pending', 'Pending Creation'),
        ('created', 'Finished Creating the Bracelet'),
        ('delivering', 'Bracelet is Being Delivered'),
        ('delivered', 'Bracelet Delivered'),
    ]
    # choices for payment type
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

    # string representation of the order
    def __str__(self):
        return f"Order #{self.id} - {self.product.name} ({self.customer.username})"

# model for order messages
class OrderMessage(models.Model):
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField(blank=True)
    image = models.ImageField(upload_to='order_messages/', blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    # string representation of the order message
    def __str__(self):
        return f"Message for Order #{self.order.id} by {self.sender.username}"

# model for custom bracelet designs
class CustomBraceletDesign(models.Model):
    name = models.CharField(max_length=100)
    beads = models.JSONField()  # list of dicts: [{shape, color, size}, ...]
    created_at = models.DateTimeField(auto_now_add=True)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bracelet_designs')

    # string representation of the custom design
    def __str__(self):
        return f"{self.name} ({self.customer.username})"

    # function to get a text representation of the bead design
    def text_form(self):
        # mapping for bead shapes
        bead_names = {
            'circle': 'Circle',
            'square': 'Square',
            'triangle': 'Triangle',
            'star': 'Star',
            'heart': 'Heart',
            'hexagon': 'Hexagon',
            'diamond': 'Diamond',
        }
        # mapping for bead colors
        color_names = {
            '#ff0000': 'Red',
            '#0000ff': 'Blue',
            '#00ff00': 'Green',
            '#ffff00': 'Yellow',
            '#ff00ff': 'Magenta',
            '#00ffff': 'Cyan',
            '#ffffff': 'White',
            '#000000': 'Black',
            '#ffa500': 'Orange',
            '#964b00': 'Brown',
            '#808080': 'Gray',
            '#ffc0cb': 'Pink',
            '#8b00ff': 'Violet',
            '#ffd700': 'Gold',
            '#228b22': 'Forest Green',
            '#b22222': 'Firebrick',
        }
        # mapping for bead sizes
        size_names = {
            'small': 'Small',
            'medium': 'Medium',
            'large': 'Large',
        }
        parts = []
        # loop to build the text description
        for idx, b in enumerate(self.beads, 1):
            color = color_names.get(b.get('color', '').lower(), b.get('color', 'Unknown'))
            size = size_names.get(b.get('size'), b.get('size', 'Unknown'))
            shape = bead_names.get(b.get('shape'), b.get('shape', 'Unknown'))
            letter = b.get('letter', '')
            if letter:
                parts.append(f"{idx}. {color} {size} {shape} '{letter}'")
            else:
                parts.append(f"{idx}. {color} {size} {shape}")
        return parts