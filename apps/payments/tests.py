from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.orders.models import Order
from apps.orders.services import OrderService
from apps.products.models import Product

from .models import Payment
from .services import PaymentService
from .strategies import PaymentStrategy

User = get_user_model()


class FakeStrategy(PaymentStrategy):

    provider_name = "fake"

    def __init__(self, outcome="success"):
        self.outcome = outcome

    def initiate(self, order, amount):
        return {
            "transaction_id": f"fake_txn_{order.id}",
            "status": "pending",
            "raw_response": {"amount": str(amount)},
            "client_payload": {"redirect_url": "https://example.com/pay"},
        }

    def confirm(self, transaction_id, payload):
        return {"status": self.outcome, "raw_response": {"transaction_id": transaction_id}}

    def query(self, transaction_id):
        return {"status": self.outcome, "raw_response": {}}


class PaymentServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="buyer2@example.com", password="Pass12345")
        self.product = Product.objects.create(name="Gadget", sku="G-1", price=Decimal("50.00"), stock=3)
        self.order = OrderService().create_order(
            self.user, items=[{"product_id": self.product.id, "quantity": 2}]
        )

    @patch("apps.payments.services.get_strategy")
    def test_checkout_creates_pending_payment(self, mock_get_strategy):
        mock_get_strategy.return_value = FakeStrategy()
        payment = PaymentService().checkout(self.order, provider="stripe")
        self.assertEqual(payment.status, "pending")
        self.assertEqual(payment.transaction_id, f"fake_txn_{self.order.id}")

    @patch("apps.payments.services.get_strategy")
    def test_confirm_success_marks_order_paid_and_reduces_stock(self, mock_get_strategy):
        mock_get_strategy.return_value = FakeStrategy(outcome="success")
        payment = PaymentService().checkout(self.order, provider="stripe")
        confirmed = PaymentService().confirm(payment)

        self.assertEqual(confirmed.status, "success")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PAID)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 1)  # 3 - 2

    @patch("apps.payments.services.get_strategy")
    def test_confirm_failure_leaves_order_pending_and_stock_untouched(self, mock_get_strategy):
        mock_get_strategy.return_value = FakeStrategy(outcome="failed")
        payment = PaymentService().checkout(self.order, provider="bkash")
        confirmed = PaymentService().confirm(payment)

        self.assertEqual(confirmed.status, "failed")
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.STATUS_PENDING)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 3)

    @patch("apps.payments.services.get_strategy")
    def test_webhook_event_updates_payment_and_order(self, mock_get_strategy):
        mock_get_strategy.return_value = FakeStrategy()
        payment = PaymentService().checkout(self.order, provider="stripe")

        PaymentService().handle_webhook_event(
            provider="stripe",
            transaction_id=payment.transaction_id,
            provider_status="success",
            raw_response={"type": "payment_intent.succeeded"},
        )

        payment.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(payment.status, "success")
        self.assertEqual(self.order.status, Order.STATUS_PAID)

    def test_transaction_id_must_be_unique(self):
        Payment.objects.create(
            order=self.order, provider="stripe", transaction_id="dup_txn", status="pending"
        )
        with self.assertRaises(Exception):
            Payment.objects.create(
                order=self.order, provider="stripe", transaction_id="dup_txn", status="pending"
            )
