from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Tool, Rental, Payment, Sale, Customer
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
# TOOL SERIALIZER
# ----------------------------
class ToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tool
        fields = "__all__"

# ----------------------------
# RENTAL SERIALIZER
# ----------------------------
class RentalSerializer(serializers.ModelSerializer):
    tool = ToolSerializer(read_only=True)
    tool_id = serializers.PrimaryKeyRelatedField(queryset=Tool.objects.all(), source="tool", write_only=True)
    customer_name = serializers.CharField(source="customer.email", read_only=True)

    class Meta:
        model = Rental
        fields = [
            "id",
            "tool", "tool_id",
            "customer", "customer_name",
            "start_date", "end_date",
            "amount_due", "amount_paid",
            "status", "settled"
        ]
        read_only_fields = ["customer", "status", "settled"]

    def create(self, validated_data):
        validated_data["customer"] = self.context["request"].user
        rental = super().create(validated_data)

        tool = rental.tool
        if tool.stock > 0:
            tool.stock -= 1
            tool.save()

        return rental

# ----------------------------
# SALE SERIALIZER
# ----------------------------
class SaleSerializer(serializers.ModelSerializer):
    tool = ToolSerializer(read_only=True)
    tool_id = serializers.PrimaryKeyRelatedField(
        queryset=Tool.objects.all(), source="tool", write_only=True
    )

    class Meta:
        model = Sale
        fields = [
            "id", "tool", "tool_id",
            "customer", "name", "phone", "state",
            "equipment", "cost_sold", "date_sold",
            "invoice_number", "payment_plan",
            "expiry_date", "payment_status"
        ]
        read_only_fields = ["date_sold", "invoice_number", "payment_status"]

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["customer"] = user

        try:
            customer_profile = user.customer
            validated_data.setdefault("name", customer_profile.name)
            validated_data.setdefault("phone", customer_profile.phone)
            validated_data.setdefault("state", customer_profile.state)
        except Customer.DoesNotExist:
            pass

        sale = super().create(validated_data)

        tool = sale.tool
        if tool.stock > 0:
            tool.stock -= 1
            if tool.stock == 0:
                tool.status = "sold"
            tool.save()

        return sale

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
    rental = serializers.PrimaryKeyRelatedField(
        queryset=Rental.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = Payment
        fields = [
            "id",
            "customer",
            "sale",
            "rental",
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
