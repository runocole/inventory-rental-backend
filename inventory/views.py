from rest_framework import generics, permissions, status
from django.contrib.auth import get_user_model
from .models import Tool, Rental, Payment,  Sale, Customer
from .serializers import UserSerializer, ToolSerializer, RentalSerializer, PaymentSerializer,  SaleSerializer, CustomerSerializer
from .permissions import IsAdminOrStaff, IsCustomer, IsOwnerOrAdmin
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response
import random, string
from django.core.mail import send_mail
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

# ---- Auth ----
import secrets

User = get_user_model()


class RegisterView(generics.ListCreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only admins can see all users, customers see only themselves
        user = self.request.user
        if user.role in ["admin", "staff"]:
            return User.objects.all()
        return User.objects.filter(id=user.id)

    def post(self, request, *args, **kwargs):
        email = request.data.get("email")
        role = request.data.get("role", "customer")

        if not email:
            return Response({"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({"error": "A user with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)

        random_password = secrets.token_urlsafe(10)
        user = User.objects.create_user(email=email, password=random_password, role=role)

        try:
            send_mail(
                subject="Your Inventory Rental Account Password",
                message=f"Hello, your account has been created.\n\nEmail: {email}\nPassword: {random_password}\n\nPlease log in and change your password.",
                from_email="noreply@inventoryrental.com",
                recipient_list=[email],
                fail_silently=True,
            )
        except Exception as e:
            print("Email send failed:", e)

        return Response(
            {"message": "Customer created successfully.", "email": email, "password": random_password},
            status=status.HTTP_201_CREATED
        )


class EmailLoginView(generics.GenericAPIView):
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')
        
        user = User.objects.filter(email=email).first()
        
        if user and user.check_password(password):
            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data
            })
        return Response(
            {'error': 'Invalid credentials'}, 
            status=status.HTTP_400_BAD_REQUEST
        )

@api_view(['POST'])
def activate_customer(request, pk):
    try:
        customer = Customer.objects.get(pk=pk)
        if customer.is_activated:
            return Response({"detail": "Customer already activated."}, status=status.HTTP_400_BAD_REQUEST)

        # Generate random password
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

        # Update user password
        user = customer.user
        user.set_password(password)
        user.save()

        # Mark activated
        customer.is_activated = True
        customer.save()

        # Send email
        send_mail(
            "Your Account Has Been Activated",
            f"Hello {customer.name},\n\nYour account has been activated.\nEmail: {customer.email}\nPassword: {password}\n\nYou can now log in to your dashboard.",
            "no-reply@yourapp.com",
            [customer.email],
            fail_silently=False,
        )

        return Response({"detail": "Customer activated and email sent."}, status=status.HTTP_200_OK)
    except Customer.DoesNotExist:
        return Response({"detail": "Customer not found."}, status=status.HTTP_404_NOT_FOUND)

# ---- Tools ----
from rest_framework.permissions import AllowAny
class ToolListCreateView(generics.ListCreateAPIView):
    queryset = Tool.objects.all()
    serializer_class = ToolSerializer
    permission_classes = [permissions.AllowAny]  # <-- open access

# Retrieve, update, delete a single tool
class ToolDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Tool.objects.all()
    serializer_class = ToolSerializer
    permission_classes = [permissions.AllowAny]  # <-- open access for dev


#  ---- Rentals ----
class RentalListCreateView(generics.ListCreateAPIView):
    queryset = Rental.objects.all()
    serializer_class = RentalSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsCustomer()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        # Automatically link rental to logged-in customer
        serializer.save(customer=self.request.user)

class RentalDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Rental.objects.all()
    serializer_class = RentalSerializer
    permission_classes = [IsOwnerOrAdmin]

# ---- Payments ----
class PaymentListCreateView(generics.ListCreateAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsCustomer()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        # Customer can only pay for their own rentals
        rental = serializer.validated_data["rental"]
        if rental.customer != self.request.user and self.request.user.role == "customer":
            raise permissions.PermissionDenied("You can only pay for your own rentals.")
        serializer.save()

class PaymentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsOwnerOrAdmin]

class SaleListCreateView(generics.ListCreateAPIView):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.role in ["admin", "staff"]:
            return Sale.objects.all()
        return Sale.objects.filter(customer=user)

    def perform_create(self, serializer):
        user = self.request.user
        if user.role == "customer":
            serializer.save(customer=user)
        else:
            # Admin/staff can manually assign a customer
            serializer.save()


class CustomerListCreateView(generics.ListCreateAPIView):
    queryset = Customer.objects.all()
    serializer_class = CustomerSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        customer = serializer.save()

        # If customer isn't linked to a user, create and link automatically
        if not customer.user:
            user = User.objects.create_user(
                email=customer.email,
                password=secrets.token_urlsafe(10),  # random secure password
                role='customer',
                is_active=False  # not active until activation
            )
            customer.user = user
            customer.save()

class ActivateCustomerView(APIView):
    def post(self, request, pk):
        customer = get_object_or_404(Customer, pk=pk)

        if customer.is_activated:
            return Response({"detail": "Customer already activated."}, status=400)

        try:
            user = customer.user
            if not user:
                return Response({"detail": "No linked user found for this customer."}, status=400)

            # Generate random password
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=10))

            # Activate user
            user.set_password(password)
            user.is_active = True
            user.save()

            # Activate customer
            customer.is_activated = True
            customer.save()

            # Send email using Gmail SMTP
            send_mail(
                subject="Your Account Has Been Activated",
                message=f"Hello {customer.name},\n\nYour account has been activated.\n\nEmail: {customer.email}\nPassword: {password}\n\nYou can now log in to your dashboard.",
                from_email="runocole@gmail.com",
                recipient_list=[customer.email],
                fail_silently=False,
            )

            return Response({"detail": "Customer activated and email sent."}, status=200)

        except Exception as e:
            print("Activation failed:", e)
            return Response({"detail": f"Activation failed: {str(e)}"}, status=500)
