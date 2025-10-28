from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.conf import settings
from django.dispatch import receiver
from django.db.models.signals import post_save
import uuid, random, string
from datetime import date
from django.contrib.auth import get_user_model
from django.utils import timezone
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
#  TOOLS MODEL
# ----------------------------


class Tool(models.Model):
    CATEGORY_CHOICES = (
        ("Receiver", "Receiver"),
        ("Accessory", "Accessory"),
        ("Total Station", "Total Station"),
        ("Level", "Level"),
        ("Drones", "Drones"),
        ("EcoSounder", "EcoSounder"),
        ("Laser Scanner", "Laser Scanner"),
        ("Other", "Other"),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    description = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=1)

    # 🔹 Dynamic ForeignKey to Supplier (instead of hardcoded choices)
    supplier = models.ForeignKey(
        "Supplier",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tools",
    )

    # 🔹 UPDATED: Change from ReceiverType to EquipmentType
    equipment_type = models.ForeignKey(
        "EquipmentType",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tools",
        verbose_name="Equipment Type"
    )

    is_enabled = models.BooleanField(default=True)
    invoice_number = models.CharField(max_length=50, blank=True, null=True)
    date_added = models.DateTimeField(auto_now_add=True)
    
    # NEW: Expiry date field
    expiry_date = models.DateField(null=True, blank=True, verbose_name="Expiry Date")

    # Optional: to store multiple serials if needed
    serials = models.JSONField(default=list, blank=True)
    
    # NEW: Serial number tracking fields
    available_serials = models.JSONField(default=list, blank=True)  # Available serial numbers
    sold_serials = models.JSONField(default=list, blank=True)       # Sold serial numbers with sale info

    def __str__(self):
        return f"{self.name} ({self.code})"

    # --- Utility Methods ---
    def decrease_stock(self):
        """Reduce stock by 1 and save."""
        if self.stock > 0:
            self.stock -= 1
            self.save(update_fields=["stock"])

    def increase_stock(self):
        """Increase stock by 1 and save."""
        self.stock += 1
        self.save(update_fields=["stock"])
        
    def get_random_serial(self):
        """Get a random serial number from available_serials"""
        if not self.available_serials or len(self.available_serials) == 0:
            return None
            
        import random
        random_serial = random.choice(self.available_serials) 
        
        # Remove from available and add to sold
        self.available_serials.remove(random_serial)
        
        # Initialize sold_serials if None
        if self.sold_serials is None:
            self.sold_serials = []
            
        # Add to sold serials with basic info
        self.sold_serials.append({
            'serial': random_serial,
            'date_sold': timezone.now().isoformat()
        })
        
        self.save(update_fields=["available_serials", "sold_serials"])
        return random_serial
        
    def add_sold_serial_info(self, serial, sale_id, customer_name, invoice_number=None):
        """Add sale information to a sold serial"""
        if not self.sold_serials:
            self.sold_serials = []
            
        # Find the serial and add sale info
        for i, sold_serial in enumerate(self.sold_serials):
            if isinstance(sold_serial, dict) and sold_serial.get('serial') == serial:
                self.sold_serials[i]['sale_id'] = sale_id
                self.sold_serials[i]['customer_name'] = customer_name
                self.sold_serials[i]['date_sold'] = date.today().isoformat()
                self.sold_serials[i]['invoice_number'] = invoice_number
                break
            elif sold_serial == serial:
                # Convert string to dict with sale info
                self.sold_serials[i] = {
                    'serial': serial,
                    'sale_id': sale_id,
                    'customer_name': customer_name,
                    'date_sold': date.today().isoformat(),
                    'invoice_number': invoice_number
                }
                break
        else:
            # Serial not found in sold_serials, add new entry
            self.sold_serials.append({
                'serial': serial,
                'sale_id': sale_id,
                'customer_name': customer_name,
                'date_sold': date.today().isoformat(),
                'invoice_number': invoice_number
            })
            
        self.save(update_fields=["sold_serials"])

    @property
    def display_equipment_type(self):
        """Display equipment type if available"""
        if self.equipment_type:
            return self.equipment_type.name
        return "N/A"

    @property
    def is_expired(self):
        """Check if the tool is expired"""
        if self.expiry_date:
            from django.utils import timezone
            return self.expiry_date < timezone.now().date()
        return False

    @property
    def expires_soon(self):
        """Check if the tool expires within 30 days"""
        if self.expiry_date:
            from django.utils import timezone
            from datetime import timedelta
            thirty_days_from_now = timezone.now().date() + timedelta(days=30)
            return timezone.now().date() < self.expiry_date <= thirty_days_from_now
        return False

# ----------------------------
#  EQUIPMENT TYPES
# ----------------------------        
class EquipmentType(models.Model):  
    CATEGORY_CHOICES = [
        ("Receiver", "Receiver"),
        ("Accessory", "Accessory"), 
        ("Total Station", "Total Station"),
        ("Level", "Level"),
        ("Drones", "Drones"),
        ("EcoSounder", "EcoSounder"),
        ("Laser Scanner", "Laser Scanner"),
        ("Other", "Other"),
    ]
    
    name = models.CharField(max_length=100)
    default_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="Receiver")
    description = models.TextField(blank=True, null=True)
    invoice_number = models.CharField(max_length=100, blank=True, null=True)  # NEW FIELD
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.category} - {self.name}"

    class Meta:
        indexes = [
            models.Index(fields=['invoice_number']),
            models.Index(fields=['category']),
        ]
    
#----------------------------
# SUPPLIERS 
#----------------------------

class Supplier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=50, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
    
#----------------------------
# SALES 
#----------------------------

class Sale(models.Model):
    PAYMENT_STATUS_CHOICES = (
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("installment", "Installment"),
        ("failed", "Failed"),
    )

    # 🔹 Who made the sale (staff)
    staff = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="sales_made",
        limit_choices_to={"role": "staff"},
        null=True,
        blank=True,
    )

    # 🔹 Customer information (stored directly in Sale)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    state = models.CharField(max_length=100)
    total_cost = models.DecimalField(max_digits=10, decimal_places=2)
    date_sold = models.DateField(default=date.today)
    invoice_number = models.CharField(max_length=100, unique=True, blank=True)
    payment_plan = models.CharField(max_length=100, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    payment_status = models.CharField(
        max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending"
    )

    def __str__(self):
        return f"{self.name} - {self.invoice_number}"

    def save(self, *args, **kwargs):
        """Auto-generate invoice number on creation."""
        if not self.invoice_number:
            self.invoice_number = f"INV-{''.join(random.choices(string.ascii_uppercase + string.digits, k=6))}"
        super().save(*args, **kwargs)


class SaleItem(models.Model):
    """Individual items within a sale"""
    sale = models.ForeignKey(Sale, related_name="items", on_delete=models.CASCADE)
    tool = models.ForeignKey(Tool, on_delete=models.CASCADE)
    equipment = models.CharField(max_length=255)
    cost = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.CharField(max_length=100, blank=True, null=True)
    serial_number = models.CharField(max_length=100, blank=True, null=True)  # NEW: Track which serial was sold

    def __str__(self):
        return f"{self.equipment} - ₦{self.cost}"

    def save(self, *args, **kwargs):
        """Deduct stock on first save only"""
        if not self.pk and self.tool.stock > 0:
            self.tool.decrease_stock()
            
            # If serial number is provided, mark it as sold in the tool
            if self.serial_number and self.sale_id:
                self.tool.add_sold_serial_info(
                    serial=self.serial_number,
                    sale_id=self.sale_id,
                    customer_name=self.sale.name,
                    invoice_number=self.sale.invoice_number
                )
                
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
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default="paystack")
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    def __str__(self):
        return f"Payment {self.id} - {self.customer.email}"