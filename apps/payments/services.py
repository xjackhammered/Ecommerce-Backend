import logging

from django.db import transaction

from apps.common.exceptions import DomainError
from apps.orders.models import Order
from apps.products.services import ProductService

from .models import Payment
from .strategies import get_strategy

logger = logging.getLogger("apps")


class PaymentService:
    def __init__(self, product_service: ProductService | None = None):
        self.product_service = product_service or ProductService()

    def checkout(self, order: Order, provider: str) -> Payment:
        if order.status != Order.STATUS_PENDING:
            raise DomainError("Only pending orders can be checked out.", code="order_not_pending")

        strategy = get_strategy(provider)
        result = strategy.initiate(order, order.total_amount)

        payment = Payment.objects.create(
            order=order,
            provider=provider,
            transaction_id=result["transaction_id"],
            status=result["status"],
            raw_response=result.get("raw_response", {}),
        )
        payment.client_payload = result.get("client_payload", {})
        return payment

    @transaction.atomic
    def confirm(self, payment: Payment, payload: dict | None = None) -> Payment:
        """
        Steps 4-6 of the order flow: provider confirms/fails payment, order
        status updates, and stock is reduced only on success.
        """
        strategy = get_strategy(payment.provider)
        result = strategy.confirm(payment.transaction_id, payload or {})

        payment.status = result["status"]
        payment.raw_response = result.get("raw_response", payment.raw_response)
        payment.save(update_fields=["status", "raw_response", "updated_at"])

        order = payment.order
        if result["status"] == "success":
            for item in order.items.select_related("product").all():
                self.product_service.reduce_stock(item.product_id, item.quantity)
            order.status = Order.STATUS_PAID
            order.save(update_fields=["status"])
            logger.info("Order #%s paid via %s (%s)", order.id, payment.provider, payment.transaction_id)
        elif result["status"] == "failed":
            logger.warning("Payment %s for order #%s failed", payment.transaction_id, order.id)

        return payment

    def handle_webhook_event(self, provider: str, transaction_id: str, provider_status: str, raw_response: dict) -> Payment:

        try:
            payment = Payment.objects.select_related("order").get(
                transaction_id=transaction_id, provider=provider
            )
        except Payment.DoesNotExist as exc:
            raise DomainError("Unknown transaction_id for webhook.", code="unknown_transaction") from exc

        with transaction.atomic():
            payment.status = provider_status
            payment.raw_response = raw_response
            payment.save(update_fields=["status", "raw_response", "updated_at"])

            order = payment.order
            if provider_status == "success" and order.status != Order.STATUS_PAID:
                for item in order.items.select_related("product").all():
                    self.product_service.reduce_stock(item.product_id, item.quantity)
                order.status = Order.STATUS_PAID
                order.save(update_fields=["status"])

        return payment
