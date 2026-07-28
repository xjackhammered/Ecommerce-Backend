from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.common.exceptions import DomainError
from apps.products.models import Product

from .models import Order
from .services import OrderService

User = get_user_model()


class OrderServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="buyer@example.com", password="Pass12345")
        self.p1 = Product.objects.create(name="A", sku="A-1", price=Decimal("19.99"), stock=10)
        self.p2 = Product.objects.create(name="B", sku="B-1", price=Decimal("5.00"), stock=2)
        self.service = OrderService()

    def test_create_order_computes_totals_deterministically(self):
        order = self.service.create_order(
            self.user,
            items=[
                {"product_id": self.p1.id, "quantity": 2},  # 39.98
                {"product_id": self.p2.id, "quantity": 1},  # 5.00
            ],
        )
        self.assertEqual(order.total_amount, Decimal("44.98"))
        self.assertEqual(order.items.count(), 2)
        item1 = order.items.get(product=self.p1)
        self.assertEqual(item1.subtotal, Decimal("39.98"))
        # Stock must NOT be reduced at order-creation time.
        self.p1.refresh_from_db()
        self.assertEqual(self.p1.stock, 10)

    def test_create_order_rejects_insufficient_stock(self):
        with self.assertRaises(DomainError):
            self.service.create_order(
                self.user, items=[{"product_id": self.p2.id, "quantity": 999}]
            )

    def test_create_order_rejects_empty_items(self):
        with self.assertRaises(DomainError):
            self.service.create_order(self.user, items=[])

    def test_cancel_pending_order(self):
        order = self.service.create_order(
            self.user, items=[{"product_id": self.p1.id, "quantity": 1}]
        )
        canceled = self.service.cancel(order)
        self.assertEqual(canceled.status, Order.STATUS_CANCELED)

    def test_cannot_cancel_paid_order(self):
        order = self.service.create_order(
            self.user, items=[{"product_id": self.p1.id, "quantity": 1}]
        )
        order.status = Order.STATUS_PAID
        order.save()
        with self.assertRaises(DomainError):
            self.service.cancel(order)
