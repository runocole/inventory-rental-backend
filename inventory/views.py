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
from django.conf import settings
from django.db.models import Sum, Count



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
            send_mail(
                subject="Your staff account credentials",
                message=f"Hello {name or 'Staff'},\n\nYour staff account has been created.\n\nEmail: {email}\nPassword: {password}\n\nPlease log in and change your password.",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "runocole@gmail.com"),
                recipient_list=[email],
                fail_silently=True,
            )
        except Exception as e:
            print("Failed to send staff creation email:", e)
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

        refresh = RefreshToken.for_user(user)
        user_data = UserSerializer(user).data

        if user_data.get("role") == "customer":
            user_data["role"] = "staff"

        return Response({
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user_data
        }, status=status.HTTP_200_OK)

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
# SALES
# ---------------------------------------------------

class SaleListCreateView(generics.ListCreateAPIView):
    serializer_class = SaleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "customer":
            return Sale.objects.filter(customer=user)
        return Sale.objects.all()

    def perform_create(self, serializer):
        user = self.request.user
        sale = serializer.save(customer=user)

        # Auto-deduct stock (using method on Tool)
        tool = sale.tool
        if tool.stock <= 0:
            raise permissions.PermissionDenied("This tool is out of stock.")
        tool.decrease_stock()

        # Generate Paystack test reference
        paystack_ref = generate_paystack_reference()

        # Auto-create a Payment record
        payment = Payment.objects.create(
            customer=user,
            sale=sale,
            amount=sale.cost_sold,
            payment_method="paystack",
            payment_reference=paystack_ref,
            status="pending"
        )

        # Simulate Paystack test mode success (mock)
        payment.status = "completed"
        payment.save()

        # Update sale payment status
        sale.payment_status = "completed"
        sale.save()


class SaleDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [IsOwnerOrAdmin]


# ----------------------------
# CONFIRM PAYMENT VIEW (Mock/Test Mode)
# ----------------------------
from rest_framework.decorators import api_view, permission_classes

@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def confirm_payment(request, pk):
    """
    Mock Paystack payment confirmation (Test Mode).
    Simulates successful payment and automatically reduces tool stock.
    """
    try:
        sale = get_object_or_404(Sale, pk=pk)
        if sale.payment_status == "completed":
            return Response({"detail": "Payment already confirmed."}, status=400)

        # --- Simulate successful payment ---
        sale.payment_status = "completed"
        sale.date_sold = timezone.now().date()
        sale.save()

        # Automatically reduce tool stock (if not already)
        tool = getattr(sale, "tool", None)
        if tool and tool.stock > 0:
            tool.stock -= 1
            if tool.stock == 0:
                tool.status = "sold"
            tool.save()

        return Response({
            "detail": "Payment confirmed successfully (Test Mode).",
            "sale_id": sale.id,
            "status": sale.payment_status
        }, status=200)

    except Exception as e:
        print("Payment confirmation failed:", e)
        return Response({"detail": str(e)}, status=500)

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

        # Inventory Breakdown (category pie chart)
        inventory_breakdown = (
            Tool.objects.values("category")
            .annotate(count=models.Count("id"))
            .order_by("category")
        )

        # ✅ Low Stock Items (table)
        low_stock_items = list(
            Tool.objects.filter(stock__lte=5)  # customize threshold here
            .values("id", "name", "code", "category", "stock", "status")[:5]
        )

        # ✅ Top Selling Tools
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


# -------------------------------
# Customer list/create
# -------------------------------
class CustomerListCreateView(generics.ListCreateAPIView):
    """
    NOTE: Permission changed to IsAuthenticated so your frontend can POST /api/customers/
    If you want to restrict creation to only staff/admin later, switch to IsAdminOrStaff.
    """
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]   # <-- allow authenticated users to list/create

    def get_queryset(self):
        # Admin/Staff see all customers; customers should not have this view in UI
        user = self.request.user
        if hasattr(user, "role") and user.role in ["admin", "staff"]:
            return Customer.objects.all()
        # For safety: if a customer somehow hits this endpoint, return only their record (if linked)
        return Customer.objects.filter(user=user)

    def perform_create(self, serializer):
        # create Customer record using data from frontend
        # if you want to auto-create linked User, that's handled by the post_save signal in models.py
        serializer.save()


class PaymentListCreateView(generics.ListCreateAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]

class PaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsOwnerOrAdmin]
