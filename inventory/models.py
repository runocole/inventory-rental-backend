from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_save
import uuid, random, string
from datetime import date

# ----------------------------
#  USER
# ----------------------------
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
        ("customer", "Customer"),
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
#  CUSTOMERS
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
            is_active=False,
        )
        instance.user = user
        instance.save()


# ----------------------------
#  TOOLS
# ----------------------------
class Tool(models.Model):
    STATUS_CHOICES = (
        ("available", "Available"),
        ("rented", "Rented"),
        ("maintenance", "Maintenance"),
        ("disabled", "Disabled"),
        ("sold", "Sold"),
    )

    CATEGORY_CHOICES = (
        ("Receiver", "Receiver"),
        ("Base", "Base"),
        ("Rover", "Rover"),
        ("Accessory", "Accessory"),
        ("Power Tool", "Power Tool"),
        ("Measuring", "Measuring"),
        ("Safety Gear", "Safety Gear"),
        ("Other", "Other"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    code = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=1)
    supplier = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="available")
    is_enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def decrease_stock(self):
        if self.stock > 0:
            self.stock -= 1
            if self.stock == 0:
                self.status = "sold"
            self.save()

    def increase_stock(self):
        self.stock += 1
        if self.status == "sold":
            self.status = "available"
        self.save()


# ----------------------------
#  RENTALS
# ----------------------------
class Rental(models.Model):
    STATUS_CHOICES = (
        ("active", "Active"),
        ("completed", "Completed"),
        ("overdue", "Overdue"),
    )

    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    customer = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={"role": "customer"})
    start_date = models.DateField()
    end_date = models.DateField()
    amount_due = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    settled = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.tool.name} rented by {self.customer.email}"

    def save(self, *args, **kwargs):
        if not self.pk:
            if self.tool.stock > 0:
                self.tool.stock -= 1
                if self.tool.stock == 0:
                    self.tool.status = "rented"
                self.tool.save()
        else:
            old = Rental.objects.get(pk=self.pk)
            if old.status != self.status and self.status == "completed":
                self.tool.stock += 1
                if self.tool.status == "rented":
                    self.tool.status = "available"
                self.tool.save()

        super().save(*args, **kwargs)

# ----------------------------
#  SALES (Internal CRM)
# ----------------------------
from django.db import models
from django.utils import timezone
import random, string
from datetime import date
from django.contrib.auth import get_user_model

User = get_user_model()


class Sale(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("installment", "Installment"),
        ("failed", "Failed"),
    )

    # 🔹 Who made the sale (staff)
    staff = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sales_made",
        limit_choices_to={"role": "staff"}
    )

    # 🔹 Which customer the sale is for
    customer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="purchases",
        limit_choices_to={"role": "customer"}
    )

    # 🔹 Which tool was sold
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)

    # 🔹 Sale details
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    state = models.CharField(max_length=100)
    equipment = models.CharField(max_length=255)
    cost_sold = models.DecimalField(max_digits=10, decimal_places=2)
    date_sold = models.DateField(default=date.today)
    invoice_number = models.CharField(max_length=100, unique=True, blank=True)
    payment_plan = models.CharField(max_length=100, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending"
    )

    def __str__(self):
        return f"{self.name} - {self.equipment}"

    def save(self, *args, **kwargs):
        # Auto-generate invoice number
        if not self.invoice_number:
            self.invoice_number = f"INV-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"

        # Deduct stock only on creation
        if not self.pk:
            if self.tool.stock > 0:
                self.tool.stock -= 1
                if self.tool.stock == 0:
                    self.tool.status = "sold"
                self.tool.save()
        super().save(*args, **kwargs)



# ----------------------------
#  PAYMENTS
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
