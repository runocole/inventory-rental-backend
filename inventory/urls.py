from django.urls import path
from .views import (
    EmailLoginView,  AddStaffView, StaffListView, ActivateStaffView,
    ToolListCreateView, ToolDetailView,
    RentalListCreateView, RentalDetailView,
    SaleListCreateView, SaleDetailView,
    PaymentListCreateView, PaymentDetailView,
    confirm_payment, DashboardSummaryView
)

urlpatterns = [
    # Auth & Staff
    path('auth/login/', EmailLoginView.as_view(), name='login'),
    path('auth/add-staff/', AddStaffView.as_view(), name='add-staff'),
    path('auth/staff/', StaffListView.as_view(), name='staff-list'),
    path('auth/staff/<int:pk>/activate/', ActivateStaffView.as_view(), name='activate-staff'),
    # Tools
    path('tools/', ToolListCreateView.as_view(), name='tools'),
    path('tools/<uuid:pk>/', ToolDetailView.as_view(), name='tool-detail'),

    # Rentals
    path('rentals/', RentalListCreateView.as_view(), name='rentals'),
    path('rentals/<int:pk>/', RentalDetailView.as_view(), name='rental-detail'),

    # Payments
    path('payments/', PaymentListCreateView.as_view(), name='payments'),
    path('payments/<int:pk>/', PaymentDetailView.as_view(), name='payment-detail'),

    # Sales
    path('sales/', SaleListCreateView.as_view(), name='sales'),
    path('sales/<int:pk>/', SaleDetailView.as_view(), name='sale-detail'),

    # Confirm payment (mock)
    path('sales/<int:pk>/confirm-payment/', confirm_payment, name='confirm-payment'),

    # Dashboard
    path('dashboard/summary/', DashboardSummaryView.as_view(), name='dashboard-summary'),
]
