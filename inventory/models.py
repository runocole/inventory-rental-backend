from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_save
import uuid
import random
import string
from datetime import date


from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")
        if not password:
            raise ValueError("Superuser must have a password")
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (
        ("admin", "Admin"),
        ("staff", "Staff"),
    )

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=255, blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="staff")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


# ----------------------------
#  Customers
# ----------------------------
class Customer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    is_activated = models.BooleanField(default=False)

    def __str__(self):
        return self.name or "Unnamed Customer"


@receiver(post_save, sender=Customer)
def create_user_for_customer(sender, instance, created, **kwargs):
    if created and not instance.user:
        user = User.objects.create_user(
            email=instance.email or f"{instance.phone}@example.com",
            password="defaultpass123",
            role="customer",
            is_active=False
        )
        instance.user = user
        instance.save()

# ----------------------------
#  Tools
# ----------------------------
class Tool(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('rented', 'Rented'),
        ('maintenance', 'Maintenance'),
        ('disabled', 'Disabled'),
        ('sold', 'Sold'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    code = models.CharField(max_length=100, unique=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='available')
    is_enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def decrease_stock(self):
        """Decrease stock when a sale or rental occurs"""
        if self.stock > 0:
            self.stock -= 1
            if self.stock == 0:
                self.status = "sold"
            self.save()

    def increase_stock(self):
        """Increase stock when rental is completed"""
        self.stock += 1
        if self.status == "sold":
            self.status = "available"
        self.save()


# ----------------------------
#  Rentals
# ----------------------------
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

    def __str__(self):
        return f"{self.tool.name} rented by {self.customer.email}"

    def save(self, *args, **kwargs):
        # On creation → reduce stock
        if not self.pk:
            if self.tool.stock > 0:
                self.tool.stock -= 1
                if self.tool.stock == 0:
                    self.tool.status = "rented"
                self.tool.save()
        else:
            # On update → if status changes to completed, restore stock
            old = Rental.objects.get(pk=self.pk)
            if old.status != self.status and self.status == "completed":
                self.tool.stock += 1
                if self.tool.status == "rented":
                    self.tool.status = "available"
                self.tool.save()

        super().save(*args, **kwargs)


# ----------------------------
#  Sales
# ----------------------------
class Sale(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )

    customer = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'customer'})
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    state = models.CharField(max_length=100)
    equipment = models.CharField(max_length=255)
    cost_sold = models.DecimalField(max_digits=10, decimal_places=2)
    date_sold = models.DateField(default=date.today)
    invoice_number = models.CharField(max_length=100, unique=True, blank=True)
    payment_plan = models.CharField(max_length=100, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')

    def __str__(self):
        return f"{self.name} - {self.equipment}"

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = f"INV-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"

        # Only reduce stock when Sale is first created
        if not self.pk:
            if self.tool.stock > 0:
                self.tool.stock -= 1
                if self.tool.stock == 0:
                    self.tool.status = "sold"
                self.tool.save()

        super().save(*args, **kwargs)


# ----------------------------
#  Payments
# ----------------------------
class Payment(models.Model):
    PAYMENT_METHODS = [
        ("cash", "Cash"),
        ("transfer", "Bank Transfer"),
        ("paystack", "Paystack"),
    ]
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    customer = models.ForeignKey(User, on_delete=models.CASCADE)
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True)
    rental = models.ForeignKey(Rental, on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default="paystack")
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    def __str__(self):
        return f"Payment {self.id} - {self.customer.email}"


# ----------------------------
#  Customers
# ----------------------------
class Customer(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="customer",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    is_activated = models.BooleanField(default=False)

    def __str__(self):
        return self.name or "Unnamed Customer"


@receiver(post_save, sender=Customer)
def create_user_for_customer(sender, instance, created, **kwargs):
    if created and not instance.user:
        user = User.objects.create_user(
            email=instance.email or f"{instance.phone}@example.com",
            password="defaultpass123",
            role="customer",
            is_active=False
        )
        instance.user = user
        instance.save()
