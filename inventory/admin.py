from django.contrib import admin
from .models import User, Tool, Payment, Customer, Sale, EquipmentType


class ToolAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'category', 'equipment_type', 'stock', 'cost']
    list_filter = ['category', 'equipment_type', 'supplier']
    search_fields = ['name', 'code']


class EquipmentTypeAdmin(admin.ModelAdmin):
    list_display = ['name', 'default_cost', 'created_at']
    search_fields = ['name']


admin.site.register(User)
admin.site.register(Tool, ToolAdmin)
admin.site.register(EquipmentType, EquipmentTypeAdmin)
admin.site.register(Payment)
admin.site.register(Customer)
admin.site.register(Sale) 