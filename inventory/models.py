from django.contrib.auth.models import AbstractUser
from django.db import models
import uuid

class User(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('staff', 'Staff'),
        ('customer', 'Customer'),
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')

class Tool(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('rented', 'Rented'),
        ('maintenance', 'Maintenance'),
        ('disabled', 'Disabled'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    code = models.CharField(max_length=100, unique=True)
    price_per_day = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    is_enabled = models.BooleanField(default=True)

class Rental(models.Model):
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('overdue', 'Overdue'),
    )
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'customer'})
    start_date = models.DateField()
    end_date = models.DateField()
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    settled = models.BooleanField(default=False)

class Payment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    rental = models.ForeignKey(Rental, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    raw_payload = models.JSONField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)