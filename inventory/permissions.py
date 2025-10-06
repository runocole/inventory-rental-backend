from rest_framework import permissions

class IsAdminOrStaff(permissions.BasePermission):
    """
    Only admins or staff can access
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ["admin", "staff"]

class IsCustomer(permissions.BasePermission):
    """
    Only customers can access
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "customer"

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Customers can only access their own records.
    Admin/Staff can access all.
    """
    def has_object_permission(self, request, view, obj):
        if request.user.role in ["admin", "staff"]:
            return True
        return obj.customer == request.user