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
        fields = ["id", "email", "password", "role"]

    def create(self, validated_data):
        # Generate random password if not provided
        password = validated_data.pop("password", None)
        if not password:
            password = get_random_string(length=10)  # e.g. 'F9kdP2qLxZ'

        user = User(**validated_data)
        user.set_password(password)
        user.save()

        # Send password to user via email
        send_mail(
            subject="Your Account Credentials",
            message=f"Hello {user.email},\n\nYour temporary password is: {password}\nPlease log in and change it.",
            from_email="no-reply@otic.com",
            recipient_list=[user.email],
            fail_silently=True,
        )

        return user

class ToolSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tool
        fields = "__all__"

class RentalSerializer(serializers.ModelSerializer):
    tool = ToolSerializer(read_only=True)
    tool_id = serializers.PrimaryKeyRelatedField(
        queryset=Tool.objects.all(), source="tool", write_only=True
    )

    class Meta:
         model = Rental
         fields = [
            "id", "tool", "tool_id", "customer",
            "start_date", "end_date", "amount_due",
            "amount_paid", "status", "settled"
        ]

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = "__all__"

from rest_framework import serializers
from .models import Sale

class SaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = "__all__"

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = "__all__"
