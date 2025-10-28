# serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Tool, EquipmentType, Payment, Sale, Customer, Supplier, SaleItem
from django.utils import timezone

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = User
        fields = ["id", "email", "name", "phone", "role", "password"]
        read_only_fields = ["id", "role"]

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save()
        return user

class ToolSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source="supplier.name", read_only=True)
    equipment_type_name = serializers.CharField(source="equipment_type.name", read_only=True)
    equipment_type_id = serializers.CharField(source="equipment_type.id", read_only=True)
    box_type = serializers.CharField(source="description", read_only=True)  # Map description to box_type for frontend
    invoice_no = serializers.CharField(source="invoice_number", read_only=True)  # Map invoice_number to invoice_no

    class Meta:
        model = Tool
        fields = [
            "id",
            "name",
            "code",
            "category",
            "description",
            "box_type",  # Added for frontend compatibility
            "cost",
            "stock",
            "supplier",
            "supplier_name",
            "equipment_type",  
            "equipment_type_name",  
            "equipment_type_id",  
            "is_enabled",
            "invoice_number",
            "invoice_no",  # Added for frontend compatibility
            "date_added",
            "expiry_date",  # NEW: Added expiry_date
            "serials",
        ]
        extra_kwargs = {
            'expiry_date': {'required': False, 'allow_null': True}
        }

    def validate_serials(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("Serials must be a list.")
        if not all(isinstance(s, str) for s in value):
            raise serializers.ValidationError("Each serial must be a string.")
        return value

    def validate_expiry_date(self, value):
        """Validate that expiry date is not in the past when creating/updating"""
        if value and value < timezone.now().date():
            raise serializers.ValidationError("Expiry date cannot be in the past.")
        return value

class EquipmentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EquipmentType  
        fields = ["id", "name", "default_cost", "category", "description", "invoice_number", "created_at"]


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = "__all__"

class SaleItemSerializer(serializers.ModelSerializer):
    tool_id = serializers.PrimaryKeyRelatedField(
        queryset=Tool.objects.all(), source="tool", write_only=True
    )
    
    class Meta:
        model = SaleItem
        fields = ['id', 'tool_id', 'equipment', 'cost', 'category']
        read_only_fields = ['id']


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True)
    sold_by = serializers.CharField(source="staff.email", read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "staff",
            "sold_by",
            "name",
            "phone",
            "state",
            "items",
            "total_cost",
            "date_sold",
            "invoice_number",
            "payment_plan",
            "expiry_date",
            "payment_status",
        ]
        read_only_fields = ["staff", "sold_by", "date_sold", "invoice_number", "payment_status"]

    def create(self, validated_data):
        items_data = validated_data.pop('items')
        user = self.context["request"].user
        validated_data["staff"] = user
        
        # Create the sale
        sale = Sale.objects.create(**validated_data)
        
        # Create sale items
        for item_data in items_data:
            SaleItem.objects.create(sale=sale, **item_data)
            
        return sale

    def update(self, instance, validated_data):
        items_data = validated_data.pop('items', None)
        
        # Update sale fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Update items if provided
        if items_data is not None:
            # Delete existing items and create new ones
            instance.items.all().delete()
            for item_data in items_data:
                SaleItem.objects.create(sale=instance, **item_data)
                
        return instance
class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "phone", "email", "state", "is_activated"]


class PaymentSerializer(serializers.ModelSerializer):
    sale = serializers.PrimaryKeyRelatedField(
        queryset=Sale.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "customer",
            "sale",
            "amount",
            "payment_method",
            "payment_reference",
            "payment_date",
            "status",
        ]
        read_only_fields = ["customer", "payment_date", "status"]

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["customer"] = user
        payment = super().create(validated_data)
        payment.status = "completed"
        payment.save()

        if payment.sale:
            sale = payment.sale
            sale.payment_status = "completed"
            sale.save()

        return payment
