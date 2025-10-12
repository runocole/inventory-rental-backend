from django.urls import path
from .views import (
    RegisterView, EmailLoginView,
    ToolListCreateView, ToolDetailView,
    RentalListCreateView, RentalDetailView,
    SaleListCreateView, CustomerListCreateView, ActivateCustomerView,
    PaymentListCreateView, PaymentDetailView
)

urlpatterns = [
    # Auth
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', EmailLoginView.as_view(), name='login'),

    # Tools
    path('tools/', ToolListCreateView.as_view(), name='tools'),
    path('tools/<uuid:pk>/', ToolDetailView.as_view(), name='tool-detail'),

    # Rentals
    path('rentals/', RentalListCreateView.as_view(), name='rentals'),
    path('rentals/<uuid:pk>/', RentalDetailView.as_view(), name='rental-detail'),

    # Payments
    path('payments/', PaymentListCreateView.as_view(), name='payments'),
    path('payments/<uuid:pk>/', PaymentDetailView.as_view(), name='payment-detail'),

    # Sales
    path('receiver-sales/', SaleListCreateView.as_view(), name='receiver_sales'),

    # ✅ Customers
    path('customers/', CustomerListCreateView.as_view(), name='customer-list-create'),
    path('customers/activate/<int:pk>/', ActivateCustomerView.as_view(), name='activate-customer'),
]
