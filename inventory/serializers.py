from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Tool, Rental, Payment

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "password", "role"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
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