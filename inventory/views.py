from rest_framework import generics, permissions, status
from django.contrib.auth import get_user_model
from .models import Tool, Rental, Payment
from .serializers import UserSerializer, ToolSerializer, RentalSerializer, PaymentSerializer
from .permissions import IsAdminOrStaff, IsCustomer, IsOwnerOrAdmin
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.response import Response



User = get_user_model()

# ---- Auth ----
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.AllowAny]

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

# ---- Tools ----
class ToolListCreateView(generics.ListCreateAPIView):
    queryset = Tool.objects.all()
    serializer_class = ToolSerializer

    def get_permissions(self):
        if self.request.method in ["POST", "PUT", "PATCH", "DELETE"]:
            return [IsAdminOrStaff()]
        return [permissions.IsAuthenticated()]

class ToolDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Tool.objects.all()
    serializer_class = ToolSerializer

    def get_permissions(self):
        if self.request.method in ["PUT", "PATCH", "DELETE"]:
            return [IsAdminOrStaff()]
        return [permissions.IsAuthenticated()]

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