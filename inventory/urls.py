from django.urls import path
from .views import (
    EmailLoginView,  AddStaffView, StaffListView,
    ToolListCreateView, ToolDetailView, ReceiverTypeListView,
    SaleListCreateView, SaleDetailView,
    PaymentListCreateView, PaymentDetailView,
    DashboardSummaryView, AddCustomerView, CustomerListView, send_sale_email,
)

urlpatterns = [
    # --- Auth ---
    path("auth/login/", EmailLoginView.as_view(), name="login"),
    path("auth/add-staff/", AddStaffView.as_view(), name="add-staff"),
    path("auth/staff/", StaffListView.as_view(), name="staff-list"),

    # --- Customers ---
    path("customers/add", AddCustomerView.as_view(), name="add-customer"),
    path("customers/", CustomerListView.as_view(), name="customers"),
    path("api/send-sale-email/", send_sale_email),

    # --- Tools ---
    path("tools/", ToolListCreateView.as_view(), name="tools"),
    path("tools/<uuid:pk>/", ToolDetailView.as_view(), name="tool-detail"),
    
    # -- Receiver Type ---
    path("receiver-types/", ReceiverTypeListView.as_view(), name="receiver-types"),

    # --- Sales ---
    path("sales/", SaleListCreateView.as_view(), name="sales"),
    path("sales/<int:pk>/", SaleDetailView.as_view(), name="sale-detail"),
     
    # Payments
    path('payments/', PaymentListCreateView.as_view(), name='payments'),
    path('payments/<int:pk>/', PaymentDetailView.as_view(), name='payment-detail'),
    # Dashboard
    path('dashboard/summary/', DashboardSummaryView.as_view(), name='dashboard-summary'),
]
