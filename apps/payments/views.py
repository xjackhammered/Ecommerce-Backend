import logging

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.exceptions import DomainError
from apps.orders.models import Order

from .models import Payment
from .serializers import CheckoutSerializer, ConfirmPaymentSerializer, PaymentSerializer
from .services import PaymentService
from .strategies import StripeStrategy

logger = logging.getLogger("apps")


class CheckoutView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = get_object_or_404(
            Order, pk=serializer.validated_data["order_id"], user=request.user
        )
        payment = PaymentService().checkout(order, serializer.validated_data["provider"])
        data = PaymentSerializer(payment).data
        data["client_payload"] = getattr(payment, "client_payload", {})
        return Response(data, status=status.HTTP_201_CREATED)


class ConfirmPaymentView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, transaction_id):
        payment = get_object_or_404(
            Payment, transaction_id=transaction_id, order__user=request.user
        )
        serializer = ConfirmPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payment = PaymentService().confirm(payment, serializer.validated_data)
        return Response(PaymentSerializer(payment).data)


class StripeWebhookView(APIView):

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")
        event = StripeStrategy.verify_webhook(request.body, sig_header)

        intent = event["data"]["object"]
        provider_status = {
            "payment_intent.succeeded": "success",
            "payment_intent.payment_failed": "failed",
        }.get(event["type"])

        if provider_status:
            try:
                PaymentService().handle_webhook_event(
                    provider="stripe",
                    transaction_id=intent["id"],
                    provider_status=provider_status,
                    raw_response=dict(intent),
                )
            except DomainError as exc:
                logger.warning("Stripe webhook ignored: %s", exc.message)

        return Response({"received": True})


class BkashCallbackView(APIView):


    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        payment_id = request.query_params.get("paymentID")
        bkash_status = request.query_params.get("status")  # success | failure | cancel

        if not payment_id:
            return Response({"error": "missing paymentID"}, status=status.HTTP_400_BAD_REQUEST)

        provider_status = "success" if bkash_status == "success" else "failed"
        try:
            payment = PaymentService().handle_webhook_event(
                provider="bkash",
                transaction_id=payment_id,
                provider_status=provider_status,
                raw_response=dict(request.query_params),
            )
        except DomainError as exc:
            return Response({"error": exc.code, "detail": exc.message}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PaymentSerializer(payment).data)
