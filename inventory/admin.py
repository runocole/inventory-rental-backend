from django.contrib import admin
from .models import User, Tool, Payment, Customer, Sale, EquipmentType


class ToolAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'equipment_type', 'stock', 'cost']
    list_filter = ['category', 'equipment_type', 'supplier']
    search_fields = ['name', 'code']

class EquipmentTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'default_cost', 'category', 'invoice_number', 'created_at']  # Added invoice_number
    search_fields = ['name', 'invoice_number']  # Added invoice_number to search
    list_filter = ['category', 'invoice_number']  # Added invoice_number to filters


admin.site.register(User)
admin.site.register(Tool, ToolAdmin)
admin.site.register(EquipmentType, EquipmentTypeAdmin)
admin.site.register(Payment)
admin.site.register(Customer)
admin.site.register(Sale) 