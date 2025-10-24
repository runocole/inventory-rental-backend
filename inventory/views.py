from django.db import models
from rest_framework import generics, permissions, status
from django.contrib.auth import get_user_model
from .models import Tool, Payment, Sale, Customer, EquipmentType, Supplier
from .serializers import (
    UserSerializer, ToolSerializer, EquipmentTypeSerializer,
    PaymentSerializer, SaleSerializer, CustomerSerializer, SupplierSerializer
)
from .permissions import IsAdminOrStaff, IsOwnerOrAdmin
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count
from django.core.mail import send_mail, BadHeaderError
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from django.conf import settings
from rest_framework.decorators import api_view
import secrets, uuid, traceback


User = get_user_model()


# ----------------------------
# STAFF MANAGEMENT
# ----------------------------
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
                subject="Your Staff Account Details",
                message=f"Hello {name or 'Staff'},\n\nYour account has been created.\n\nEmail: {email}\nPassword: {password}",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "runocole@gmail.com"),
                recipient_list=[email],
                fail_silently=False,
            )
        except Exception:
            traceback.print_exc()

        return Response(
            {
                "id": user.id,
                "email": email,
                "name": user.name,
                "phone": user.phone,
                "detail": "Staff created successfully",
            },
            status=status.HTTP_201_CREATED,
        )


class StaffListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsAdminOrStaff]

    def get_queryset(self):
        return User.objects.filter(role="staff")


# ----------------------------
# AUTHENTICATION
# ----------------------------
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

        # Auto-activate customer on first login
        if user.role == "customer":
            try:
                customer = Customer.objects.get(user=user)
                if not customer.is_activated:
                    customer.is_activated = True
                    customer.save()
            except Customer.DoesNotExist:
                pass

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )


# ----------------------------
# CUSTOMERS
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

        Customer.objects.create(
            user=user, name=name, phone=phone, state=state, email=email
        )

        try:
            send_mail(
                subject="Your Customer Account Details",
                message=f"Hello {name or 'Customer'},\n\nAn account has been created for you.\nEmail: {email}\nPassword: {password}",
                from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "runocole@gmail.com"),
                recipient_list=[email],
                fail_silently=True,
            )
        except Exception as e:
            print("Failed to send email:", e)

        return Response(
            {"id": user.id, "email": email, "name": name, "phone": phone, "state": state},
            status=status.HTTP_201_CREATED,
        )


class CustomerListView(generics.ListAPIView):
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "admin":
            return Customer.objects.all().order_by("-id")
        return Customer.objects.all().order_by("-id")


# ----------------------------
# TOOLS
# ----------------------------
class ToolListCreateView(generics.ListCreateAPIView):
    serializer_class = ToolSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        queryset = Tool.objects.select_related("supplier").order_by("-date_added")

        if getattr(user, "role", None) == "customer":
            queryset = queryset.filter(stock__gt=0, is_enabled=True)

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, "role", None) == "customer":
            raise permissions.PermissionDenied("Customers cannot add tools.")
        serializer.save()



class ToolDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Tool.objects.all()
    serializer_class = ToolSerializer
    permission_classes = [permissions.IsAuthenticated]


# ----------------------------
# WQUIPMENT TYPE
# ----------------------------

class EquipmentTypeListView(generics.ListCreateAPIView):
    queryset = EquipmentType.objects.all().order_by("category", "name")  # Updated model
    serializer_class = EquipmentTypeSerializer  # Updated serializer
    permission_classes = [permissions.AllowAny]

class EquipmentTypeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = EquipmentType.objects.all()  # Updated model
    serializer_class = EquipmentTypeSerializer  # Updated serializer
    permission_classes = [permissions.AllowAny]


#-------------------
# SUPPLIERS
#--------------------
class SupplierListView(generics.ListCreateAPIView):
    queryset = Supplier.objects.all().order_by("name")
    serializer_class = SupplierSerializer
    permission_classes = [permissions.AllowAny]

class SupplierDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.AllowAny]

# ----------------------------
# SALES
# ----------------------------
class SaleListCreateView(generics.ListCreateAPIView):
    serializer_class = SaleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role == "staff":
            return Sale.objects.filter(staff=user).order_by("-date_sold")
        elif user.role == "admin":
            return Sale.objects.all().order_by("-date_sold")
        return Sale.objects.none()


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
        if user.role == "staff" and instance.staff != user:
            raise PermissionDenied("You can only edit your own sales.")
        return super().perform_update(serializer)


# ----------------------------
# EMAIL API
# ----------------------------
@api_view(["POST"])
def send_sale_email(request):
    data = request.data
    send_mail(
        data.get("subject"),
        data.get("message"),
        "runocole@gmail.com",
        [data.get("to_email")],
        fail_silently=False,
    )
    return Response({"message": "Email sent!"})

# ----------------------------
# DASHBOARD SUMMARY
# ----------------------------
class DashboardSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        total_sales = Sale.objects.count()
        total_revenue = Sale.objects.aggregate(total=Sum("cost_sold"))["total"] or 0
        tools_count = Tool.objects.count()
        staff_count = User.objects.filter(role="staff").count()
        active_customers = Customer.objects.filter(is_activated=True).count()

        today = timezone.now()
        month_start = today.replace(day=1)
        mtd_revenue = (
            Sale.objects.filter(date_sold__gte=month_start)
            .aggregate(total=Sum("cost_sold"))
            .get("total")
            or 0
        )

        # FIXED: Show receiver tools by their actual names
        inventory_breakdown = []
        
        # Get all tools that are receivers and group by their names
        receiver_tools_breakdown = (
            Tool.objects
            .filter(category="Receiver")  # Only tools with Receiver category
            .values("name")  # Group by the tool name (T20, T30, etc.)
            .annotate(count=Count("id"))
            .order_by("name")
        )
        
        for item in receiver_tools_breakdown:
            inventory_breakdown.append({
                "receiver_type": item["name"],  # This will be "T20", "T30", etc.
                "count": item["count"]
            })

        # If no receiver tools found
        if not inventory_breakdown:
            inventory_breakdown.append({
                "receiver_type": "No receiver tools",
                "count": 0
            })

        low_stock_items = list(
            Tool.objects.filter(stock__lte=5).values("id", "name", "code", "category", "stock")[:5]
        )

        top_selling_tools = (
            Sale.objects.values("tool__name")
            .annotate(total_sold=Count("id"))
            .order_by("-total_sold")[:5]
        )

        # Get recent sales
        recent_sales = Sale.objects.select_related('customer', 'tool').order_by('-date_sold')[:10].values(
            'invoice_number', 'customer__name', 'tool__name', 'cost_sold', 'payment_status'
        )

        return Response(
            {
                "totalTools": tools_count,
                "totalStaff": staff_count,
                "activeCustomers": active_customers,
                "mtdRevenue": mtd_revenue,
                "inventoryBreakdown": inventory_breakdown,
                "lowStockItems": low_stock_items,
                "topSellingTools": list(top_selling_tools),
                "recentSales": list(recent_sales),
            }
        )
    
# ----------------------------
# PAYMENTS
# ----------------------------
class PaymentListCreateView(generics.ListCreateAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]


class PaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsOwnerOrAdmin]
