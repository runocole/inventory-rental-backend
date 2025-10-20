from django.db import models
from rest_framework import generics, permissions, status
from django.contrib.auth import get_user_model
from .models import Tool, Rental, Payment, Sale, Customer
from .serializers import (
    UserSerializer, ToolSerializer, RentalSerializer,
    PaymentSerializer, SaleSerializer, CustomerSerializer
)
from .permissions import IsAdminOrStaff, IsOwnerOrAdmin
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Sum
from django.core.mail import send_mail
from django.utils import timezone
import random, string, secrets
import uuid 
from django.core.mail import BadHeaderError
import traceback
from django.conf import settings
from django.db.models import Sum, Count
from rest_framework.exceptions import PermissionDenied


User = get_user_model()


class AddStaffView(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrStaff]

    def post(self, request, *args, **kwargs):
        email = request.data.get("email")
        name = request.data.get("name")
        phone = request.data.get("phone")

        if not email:
            return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({"detail": "User with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)

        password = secrets.token_urlsafe(10)

        user = User.objects.create_user(
            email=email,
            password=password,
            name=name or "",
            phone=phone or "",
            role="staff",
            is_active=True,
        )
        try:
            sent = send_mail(
                subject="Your Customer Account Details",
                message=f"Hello {name or 'Customer'},\n\nAn account has been created for you.\n\nEmail: {email}\nPassword: {password}\n\nPlease log in and change your password.",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "runocole@gmail.com"),
                recipient_list=[email],
                fail_silently=False,  # 🚨 don't hide issues anymore
            )
            if sent:
                print(f"✅ Email successfully sent to {email}")
            else:
                print(f"⚠️ send_mail returned False for {email}")
        except BadHeaderError:
            print("❌ Invalid header detected when sending email.")
        except Exception as e:
            print("❌ Failed to send customer creation email:")
            traceback.print_exc()

        return Response(
    {
        "id": user.id,
        "email": email,
        "name": user.name,
        "phone": user.phone,
        "detail": "Staff created successfully"
    },
    status=status.HTTP_201_CREATED
)


class StaffListView(generics.ListAPIView):
    """List all staff (admin or staff can view)."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrStaff]

    def get_queryset(self):
        return User.objects.filter(role="staff")
class EmailLoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request, *args, **kwargs):
        email = request.data.get("email")
        password = request.data.get("password")

        if not email or not password:
            return Response({"detail": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email=email).first()
        if not user or not user.check_password(password):
            return Response({"detail": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST)

        if not user.is_active:
            return Response({"detail": "User account is disabled."}, status=status.HTTP_403_FORBIDDEN)

        # ✅ Activate customer automatically on first login
        if user.role == "customer":
            try:
                customer = Customer.objects.get(user=user)
                if not customer.is_activated:
                    customer.is_activated = True
                    customer.save()
            except Customer.DoesNotExist:
                # in case there's no linked Customer record, skip silently
                pass

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user).data

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user_data
        }, status=status.HTTP_200_OK)
# ----------------------------
# AddCustomerView
# ----------------------------
class AddCustomerView(generics.CreateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]  

    def post(self, request, *args, **kwargs):
        email = request.data.get("email")
        name = request.data.get("name")
        phone = request.data.get("phone")
        state = request.data.get("state")

        if not email:
            return Response({"detail": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({"detail": "User with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)

        password = secrets.token_urlsafe(10)
        user = User.objects.create_user(
            email=email,
            password=password,
            name=name or "",
            phone=phone or "",
            role="customer",
            is_active=True,
        )

        # Optional: Create a linked CustomerProfile if your model has it
        try:
            Customer.objects.create(user=user, name=name, phone=phone, state=state)
        except Exception as e:
            print("Failed to create customer profile:", e)

        # Send login email
        try:
            send_mail(
                subject="Your Customer Account Details",
                message=f"Hello {name or 'Customer'},\n\nAn account has been created for you.\n\nEmail: {email}\nPassword: {password}\n\nPlease log in and change your password.",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "runocole@gmail.com"),
                recipient_list=[email],
                fail_silently=True,
            )
        except Exception as e:
            print("Failed to send customer creation email:", e)

        return Response(
            {
                "id": user.id,
                "email": email,
                "name": user.name,
                "phone": user.phone,
                "state": state,
                "detail": "Customer created successfully and login email sent."
            },
            status=status.HTTP_201_CREATED,
        )

# ----------------------------
# Customer List View
# ----------------------------
class CustomerListView(generics.ListAPIView):
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Admin sees all; staff sees customers they created (optional)
        user = self.request.user
        if user.role == "admin":
            return Customer.objects.all().order_by("-id")
        else:
            return Customer.objects.all().order_by("-id")


# ---------------------------------------------------
# TOOLS
# ---------------------------------------------------

class ToolListCreateView(generics.ListCreateAPIView):
    queryset = Tool.objects.all()
    serializer_class = ToolSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if hasattr(user, "role") and user.role == "customer":
            return Tool.objects.filter(stock__gt=0)
        return Tool.objects.all()

    def perform_create(self, serializer):
        if hasattr(self.request.user, "role") and self.request.user.role == "customer":
            raise permissions.PermissionDenied("Customers cannot add tools.")
        serializer.save()

class ToolDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Tool.objects.all()
    serializer_class = ToolSerializer
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)
    
# ---------------------------------------------------
# RENTALS
# ---------------------------------------------------

class RentalListCreateView(generics.ListCreateAPIView):
    serializer_class = RentalSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "customer":
            return Rental.objects.filter(customer=user)
        return Rental.objects.all()

    def perform_create(self, serializer):
        # Auto-link customer to logged-in user
        serializer.save(customer=self.request.user)


class RentalDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Rental.objects.all()
    serializer_class = RentalSerializer
    permission_classes = [IsOwnerOrAdmin]


# ---------------------------------------------------
# SALES (Internal - Staff Managed)
# ---------------------------------------------------


class SaleListCreateView(generics.ListCreateAPIView):
    serializer_class = SaleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        # Staff → only their own sales
        if user.role == "staff":
            return Sale.objects.filter(staff=user).order_by("-date_sold")
        # Admin → all sales
        elif user.role == "admin":
            return Sale.objects.all().order_by("-date_sold")
        # Customers → no access
        return Sale.objects.none()

    def perform_create(self, serializer):
        user = self.request.user

        # --- Only staff and admin can create sales ---
        if user.role not in ["staff", "admin"]:
            raise PermissionDenied("Only staff or admin can record sales.")

        sale = serializer.save(staff=user)  # assign logged-in staff

        # --- Check tool availability ---
        tool = sale.tool
        if tool.stock <= 0:
            raise PermissionDenied("This tool is out of stock.")

        # --- Auto-deduct stock ---
        tool.stock -= 1
        if tool.stock == 0:
            tool.status = "sold"
        tool.save()

        # --- Generate Paystack reference ---
        paystack_ref = generate_paystack_reference()

        # --- Auto-create payment record ---
        Payment.objects.create(
            customer=sale.customer,
            sale=sale,
            amount=sale.cost_sold,
            payment_method="paystack",
            payment_reference=paystack_ref,
            status="pending",
        )

        # --- Handle payment plan logic ---
        if sale.payment_plan and sale.payment_plan.lower() in ["full", "full payment"]:
            sale.payment_status = "completed"
            sale.date_sold = timezone.now().date()
            sale.save()

            payment = Payment.objects.filter(sale=sale).first()
            if payment:
                payment.status = "completed"
                payment.save()

        elif sale.payment_plan and "installment" in sale.payment_plan.lower():
            sale.expiry_date = timezone.now().date() + timezone.timedelta(days=30)
            sale.payment_status = "installment"
            sale.save()

        return sale


class SaleDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = SaleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "staff":
            return Sale.objects.filter(staff=user)
        elif user.role == "admin":
            return Sale.objects.all()
        return Sale.objects.none()

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()

        # Staff can only update their own sales
        if user.role == "staff" and instance.staff != user:
            raise PermissionDenied("You can only edit your own sales.")

        return super().perform_update(serializer)

# ----------------------------
# CONFIRM PAYMENT VIEW (Mock/Test Mode)
# ----------------------------
from rest_framework.decorators import api_view, permission_classes
@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def confirm_payment(request, pk):
    """
    Mock Paystack payment confirmation (Internal/Test Mode).
    Staff or Admin can mark payment as confirmed.
    """
    sale = get_object_or_404(Sale, pk=pk)

    if sale.payment_status == "completed":
        return Response({"detail": "Payment already confirmed."}, status=400)

    sale.payment_status = "completed"
    sale.date_sold = timezone.now().date()
    sale.save()

    # Update related Payment
    payment = Payment.objects.filter(sale=sale).first()
    if payment:
        payment.status = "completed"
        payment.save()

    return Response({
        "detail": "Payment confirmed successfully (Test Mode).",
        "sale_id": sale.id,
        "status": sale.payment_status
    }, status=200)

# ----------------------------
# DASHBOARD SUMMARY VIEW
# ----------------------------

class DashboardSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        # Basic summaries
        if user.role == "customer":
            total_sales = Sale.objects.filter(customer=user).count()
            total_rented = Rental.objects.filter(customer=user, status="active").count()
            total_revenue = (
                Sale.objects.filter(customer=user).aggregate(total=Sum("cost_sold"))["total"] or 0
            )
        else:
            total_sales = Sale.objects.count()
            total_rented = Rental.objects.filter(status="active").count()
            total_revenue = Sale.objects.aggregate(total=Sum("cost_sold"))["total"] or 0

        tools_count = Tool.objects.count()
        staff_count = User.objects.filter(role="staff").count()
        active_customers = Customer.objects.filter(is_activated=True).count()

        # Month-to-date revenue
        today = timezone.now()
        month_start = today.replace(day=1)
        mtd_revenue = (
            Sale.objects.filter(date_sold__gte=month_start)
            .aggregate(total=Sum("cost_sold"))
            .get("total")
            or 0
        )

        # Tool status counts
        tool_status_counts = {
            "available": Tool.objects.filter(status="available").count(),
            "rented": Tool.objects.filter(status="rented").count(),
            "maintenance": Tool.objects.filter(status="maintenance").count(),
            "disabled": Tool.objects.filter(status="disabled").count(),
            "sold": Tool.objects.filter(status="sold").count(),
        }

        # Inventory Breakdown 
        inventory_breakdown = (
            Tool.objects.values("category")
            .annotate(count=models.Count("id"))
            .order_by("category")
        )

        # Low Stock Items 
        low_stock_items = list(
            Tool.objects.filter(stock__lte=5)  # customize threshold here
            .values("id", "name", "code", "category", "stock", "status")[:5]
        )

        # Top Selling Tools
        top_selling_tools = (
            Sale.objects.values("tool__name")
            .annotate(total_sold=models.Count("id"))
            .order_by("-total_sold")[:5]
        )

        return Response(
            {
                "totalTools": tools_count,
                "totalStaff": staff_count,
                "activeCustomers": active_customers,
                "mtdRevenue": mtd_revenue,
                "toolStatusCounts": tool_status_counts,
                "inventoryBreakdown": list(inventory_breakdown),
                "lowStockItems": low_stock_items,
                "topSellingTools": list(top_selling_tools),
            }
        )

# -------------------------------
# HELPER: Generate Paystack Reference
# -------------------------------
def generate_paystack_reference():
    """Generate unique Paystack-like reference for test mode"""
    return f"TEST_REF_{uuid.uuid4().hex[:10].upper()}"


class PaymentListCreateView(generics.ListCreateAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

class PaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsOwnerOrAdmin]
