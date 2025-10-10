from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
 RegisterView,
 ToolListCreateView, ToolDetailView,
 RentalListCreateView, RentalDetailView,
 PaymentListCreateView, PaymentDetailView, EmailLoginView
)

urlpatterns = [
 # Auth
 path("auth/register/", RegisterView.as_view(), name="register"),
 path("auth/login/", EmailLoginView.as_view(), name="login"),
 path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

 # Tools
 path("tools/", ToolListCreateView.as_view(), name="tool-list"),
 path("tools/<uuid:pk>/", ToolDetailView.as_view(), name="tool-detail"),

 # Rentals
 path("rentals/", RentalListCreateView.as_view(), name="rental-list"),
 path("rentals/<int:pk>/", RentalDetailView.as_view(), name="rental-detail"),

 # Payments
 path("payments/", PaymentListCreateView.as_view(), name="payment-list"),
 path("payments/<int:pk>/", PaymentDetailView.as_view(), name="payment-detail"),
]