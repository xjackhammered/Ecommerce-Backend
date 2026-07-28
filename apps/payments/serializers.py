from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ["id", "order", "provider", "transaction_id", "status", "created_at", "updated_at"]
        read_only_fields = fields


class CheckoutSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()
    provider = serializers.ChoiceField(choices=[Payment.PROVIDER_STRIPE, Payment.PROVIDER_BKASH])


class ConfirmPaymentSerializer(serializers.Serializer):
    payment_method = serializers.CharField(required=False)  # Stripe test payment method id
