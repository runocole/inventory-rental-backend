from django.db import models
from rest_framework import generics, permissions, status
from django.contrib.auth import get_user_model
from .models import Tool, Payment, Sale, Customer, EquipmentType, Supplier, SaleItem
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
from django.db.models import Sum, Count, Max
from django.core.mail import send_mail, BadHeaderError
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
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

        # Filter by category and equipment type if provided
        category = self.request.query_params.get('category')
        equipment_type = self.request.query_params.get('equipment_type')
        
        if category:
            queryset = queryset.filter(category=category)
            
        if equipment_type:
            # For Receiver category, filter by description/box_type based on equipment_type
            if category == "Receiver":
                if equipment_type == "Base Only":
                    queryset = queryset.filter(description__icontains="base").exclude(description__icontains="rover")
                elif equipment_type == "Rover Only":
                    queryset = queryset.filter(description__icontains="rover").exclude(description__icontains="base")
                elif equipment_type == "Base & Rover Combo":
                    queryset = queryset.filter(description__icontains="base").filter(description__icontains="rover")
                elif equipment_type == "Accessories":
                    queryset = queryset.filter(description__icontains="accessory")

        if getattr(user, "role", None) == "customer":
            queryset = queryset.filter(stock__gt=0, is_enabled=True)

        return queryset

    def perform_create(self, serializer):
        user = self.request.user
        if getattr(user, "role", None) == "customer":
            raise permissions.PermissionDenied("Customers cannot add tools.")
        
        # Initialize available_serials with serials if not provided
        tool_data = serializer.validated_data
        if 'available_serials' not in tool_data or not tool_data['available_serials']:
            if 'serials' in tool_data and tool_data['serials']:
                tool_data['available_serials'] = tool_data['serials'].copy()
                
        serializer.save()

# NEW: Get tools grouped by name for frontend display
class ToolGroupedListView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        user = self.request.user
        category = request.query_params.get('category')
        equipment_type = request.query_params.get('equipment_type')
        
        # Start with base queryset
        queryset = Tool.objects.filter(stock__gt=0, is_enabled=True)
        
        if category:
            queryset = queryset.filter(category=category)
            
        if equipment_type and category == "Receiver":
            # Apply equipment type filtering for Receiver category
            if equipment_type == "Base Only":
                queryset = queryset.filter(description__icontains="base").exclude(description__icontains="rover")
            elif equipment_type == "Rover Only":
                queryset = queryset.filter(description__icontains="rover").exclude(description__icontains="base")
            elif equipment_type == "Base & Rover Combo":
                queryset = queryset.filter(description__icontains="base").filter(description__icontains="rover")
            elif equipment_type == "Accessories":
                queryset = queryset.filter(description__icontains="accessory")
        
        # Group tools by name and calculate total stock
        from django.db.models import Sum, Count
        grouped_tools = queryset.values('name', 'category', 'cost').annotate(
            total_stock=Sum('stock'),
            tool_count=Count('id'),
            available_serials_count=Sum('stock')  # Assuming each stock item has one serial
        ).order_by('name')
        
        # Convert to list and add additional info
        result = []
        for tool_group in grouped_tools:
            # Get one sample tool for additional fields
            sample_tool = queryset.filter(name=tool_group['name']).first()
            if sample_tool:
                result.append({
                    'name': tool_group['name'],
                    'category': tool_group['category'],
                    'cost': tool_group['cost'],
                    'total_stock': tool_group['total_stock'],
                    'tool_count': tool_group['tool_count'],
                    'description': sample_tool.description,
                    'supplier_name': sample_tool.supplier.name if sample_tool.supplier else None,
                    'group_id': f"group_{tool_group['name'].replace(' ', '_').lower()}"
                })
        
        return Response(result)

class ToolAssignRandomFromGroupView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        tool_name = request.data.get('tool_name')
        category = request.data.get('category')
        
        if not tool_name:
            return Response({"error": "Tool name is required."}, status=status.HTTP_400_BAD_REQUEST)
        
        # Find all available tools with this name and category that have serials
        available_tools = Tool.objects.filter(
            name=tool_name, 
            category=category,
            stock__gt=0,
            is_enabled=True
        )
        
        # Filter tools that actually have available serials
        tools_with_serials = []
        for tool in available_tools:
            if tool.available_serials and len(tool.available_serials) > 0:
                tools_with_serials.append(tool)
        
        if not tools_with_serials:
            return Response(
                {"error": f"No {tool_name} tools with available serial numbers in stock."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Select a random tool from available ones with serials
        import random
        selected_tool = random.choice(tools_with_serials)
        
        # Get a random serial number
        serial_number = selected_tool.get_random_serial()
        
        if not serial_number:
            return Response(
                {"error": "Failed to get random serial number from selected tool."},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Update the stock count
        selected_tool.decrease_stock()
        
        return Response({
            "assigned_tool_id": selected_tool.id,
            "tool_name": selected_tool.name,
            "serial_number": serial_number,
            "cost": str(selected_tool.cost),
            "description": selected_tool.description,
            "remaining_stock": selected_tool.stock
        })

# NEW: Get random serial number for a tool
class ToolGetRandomSerialView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, pk):
        try:
            tool = get_object_or_404(Tool, pk=pk)
            
            if not tool.available_serials:
                return Response(
                    {"error": "No available serial numbers for this tool."},
                    status=status.HTTP_404_NOT_FOUND
                )
                
            random_serial = tool.get_random_serial()
            
            if not random_serial:
                return Response(
                    {"error": "Failed to get random serial number."},
                    status=status.HTTP_404_NOT_FOUND
                )
                
            return Response({
                "serial_number": random_serial,
                "tool_name": tool.name,
                "remaining_serials": len(tool.available_serials)
            })
            
        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
class ToolDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Tool.objects.all()
    serializer_class = ToolSerializer
    permission_classes = [permissions.IsAuthenticated]


class ToolSoldSerialsView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, pk):
        tool = get_object_or_404(Tool, pk=pk)
        
        sold_serials = []
        for serial_info in tool.sold_serials or []:
            if isinstance(serial_info, dict):
                sold_serials.append({
                    'serial': serial_info.get('serial', 'Unknown'),
                    'sale_id': serial_info.get('sale_id'),
                    'customer_name': serial_info.get('customer_name', 'Unknown'),
                    'date_sold': serial_info.get('date_sold'),
                    'invoice_number': serial_info.get('invoice_number')
                })
            else:
                # Handle case where serial_info is just a string
                sold_serials.append({
                    'serial': serial_info,
                    'sale_id': None,
                    'customer_name': 'Unknown',
                    'date_sold': None,
                    'invoice_number': None
                })
                
        return Response(sold_serials)

# ----------------------------
# EQUIPMENT TYPE
# ----------------------------

class EquipmentTypeListView(generics.ListCreateAPIView):
    serializer_class = EquipmentTypeSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        queryset = EquipmentType.objects.all().order_by("category", "name")
        
        # Filter by invoice_number if provided
        invoice_number = self.request.query_params.get('invoice_number')
        if invoice_number:
            queryset = queryset.filter(invoice_number=invoice_number)
        
        # Filter by category if provided
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(category=category)
            
        return queryset

class EquipmentTypeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = EquipmentType.objects.all()
    serializer_class = EquipmentTypeSerializer
    permission_classes = [permissions.AllowAny]

# NEW VIEW: Get equipment grouped by invoice
@api_view(['GET'])
def equipment_by_invoice(request):
    """
    Get equipment types grouped by invoice number with counts and totals
    """
    from django.db.models import F, FloatField
    from django.db.models.functions import Cast
    
    invoices = EquipmentType.objects.exclude(invoice_number__isnull=True)\
        .exclude(invoice_number__exact='')\
        .values('invoice_number')\
        .annotate(
            equipment_count=Count('id'),
            total_value=Sum('default_cost'),
            last_updated=Max('created_at')
        )\
        .order_by('-last_updated')
    
    return Response(list(invoices))

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

    def perform_create(self, serializer):
        serializer.save(staff=self.request.user)


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
@permission_classes([AllowAny])  
def send_sale_email(request):
    try:
        data = request.data
        send_mail(
            subject=data.get("subject", "Your Payment Link"),
            message=data.get("message", "Hello, your payment link will be available soon."),
            from_email="runocole@gmail.com",  
            recipient_list=[data.get("to_email")],
            fail_silently=False,
        )
        return Response({"message": "Email sent successfully!"})
    except Exception as e:
        return Response({"error": str(e)}, status=500)

# ----------------------------
# DASHBOARD SUMMARY
# ----------------------------
class DashboardSummaryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user

        total_sales = Sale.objects.count()
        total_revenue = Sale.objects.aggregate(total=Sum("total_cost"))["total"] or 0  # Changed from cost_sold to total_cost
        tools_count = Tool.objects.count()
        staff_count = User.objects.filter(role="staff").count()
        active_customers = Customer.objects.filter(is_activated=True).count()

        today = timezone.now()
        month_start = today.replace(day=1)
        mtd_revenue = (
            Sale.objects.filter(date_sold__gte=month_start)
            .aggregate(total=Sum("total_cost"))  # Changed from cost_sold to total_cost
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

        # FIXED: Top selling tools - now through SaleItem
        top_selling_tools = (
            SaleItem.objects.values("tool__name")
            .annotate(total_sold=Count("id"))
            .order_by("-total_sold")[:5]
        )

        # FIXED: Get recent sales with items
        recent_sales = Sale.objects.prefetch_related('items').order_by('-date_sold')[:10]
        recent_sales_data = []
        for sale in recent_sales:
            # Get the first item's equipment name for display
            first_item = sale.items.first()
            tool_name = first_item.equipment if first_item else "No equipment"
            
            recent_sales_data.append({
                'invoice_number': sale.invoice_number,
                'customer_name': sale.name,
                'tool_name': tool_name,
                'cost_sold': sale.total_cost,  # Changed from cost_sold to total_cost
                'payment_status': sale.payment_status,
                'date_sold': sale.date_sold,
            })

        return Response(
            {
                "totalTools": tools_count,
                "totalStaff": staff_count,
                "activeCustomers": active_customers,
                "mtdRevenue": mtd_revenue,
                "inventoryBreakdown": inventory_breakdown,
                "lowStockItems": low_stock_items,
                "topSellingTools": list(top_selling_tools),
                "recentSales": recent_sales_data,
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