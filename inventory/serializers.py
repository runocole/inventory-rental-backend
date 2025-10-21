from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Tool, ReceiverType, Payment, Sale, Customer
from django.core.mail import send_mail
from django.utils.crypto import get_random_string


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

# ----------------------------
#  TOOL SERIALIZER
# ----------------------------
class ToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tool
        fields = "__all__"

    def validate_serials(self, value):
        """Ensure serials is a list of strings."""
        if not isinstance(value, list):
            raise serializers.ValidationError("Serials must be a list.")
        if not all(isinstance(s, str) for s in value):
            raise serializers.ValidationError("Each serial must be a string.")
        return value


# ----------------------------
# RECEIVER TYPE
# ----------------------------
class ReceiverTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReceiverType
        fields = "__all__"

 # ----------------------------
# SALE SERIALIZER (Staff-managed)
# ----------------------------

class SaleSerializer(serializers.ModelSerializer):
    # Nested read-only tool info
    tool = ToolSerializer(read_only=True)
    tool_id = serializers.PrimaryKeyRelatedField(
        queryset=Tool.objects.all(),
        source="tool",
        write_only=True
    )

    # Customer input handled by ID, not full object
    customer_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role="customer"),
        source="customer",
        write_only=True
    )

    # Expose staff name for admin display
    sold_by = serializers.CharField(source="staff.email", read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "staff",
            "sold_by",           
            "customer",
            "customer_id",
            "tool",
            "tool_id",
            "name",
            "phone",
            "state",
            "equipment",
            "cost_sold",
            "date_sold",
            "invoice_number",
            "payment_plan",
            "expiry_date",
            "payment_status",
        ]
        read_only_fields = [
            "staff",
            "sold_by",
            "date_sold",
            "invoice_number",
            "payment_status",
        ]

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["staff"] = user  # logged-in staff auto-assigned
        return super().create(validated_data)



class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ["id", "name", "phone", "email", "state", "is_activated"]

# ----------------------------
# PAYMENT SERIALIZER
# ----------------------------
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
            "status"
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
        if payment.rental:
            rental = payment.rental
            rental.settled = True
            rental.status = "completed"
            rental.save()

        return payment
