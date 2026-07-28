from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.payments.tests import FakeStrategy
from apps.products.models import Product

User = get_user_model()


class AuthAPITests(APITestCase):
    def test_register_then_login(self):
        resp = self.client.post(
            "/api/users/register/",
            {"email": "newuser@example.com", "password": "StrongPass123", "full_name": "New User"},
        )
        self.assertEqual(resp.status_code, 201, resp.data)

        resp = self.client.post(
            "/api/users/login/", {"email": "newuser@example.com", "password": "StrongPass123"}
        )
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertIn("access", resp.data)

    def test_register_rejects_duplicate_email(self):
        self.client.post("/api/users/register/", {"email": "dup2@example.com", "password": "StrongPass123"})
        resp = self.client.post("/api/users/register/", {"email": "dup2@example.com", "password": "StrongPass123"})
        self.assertEqual(resp.status_code, 400)

    def test_me_requires_authentication(self):
        resp = self.client.get("/api/users/me/")
        self.assertEqual(resp.status_code, 401)


class AuthenticatedAPITestCase(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="shopper@example.com", password="ShopperPass123")
        resp = self.client.post(
            "/api/users/login/", {"email": "shopper@example.com", "password": "ShopperPass123"}
        )
        self.access_token = resp.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")


class OrderAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.product = Product.objects.create(name="Book", sku="BK-1", price=Decimal("12.50"), stock=5)

    def test_create_order(self):
        resp = self.client.post(
            "/api/orders/", {"items": [{"product_id": self.product.id, "quantity": 2}]}, format="json"
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(resp.data["total_amount"], "25.00")
        self.assertEqual(resp.data["status"], "pending")

    def test_list_orders_only_returns_own_orders(self):
        other = User.objects.create_user(email="other@example.com", password="OtherPass123")
        from apps.orders.services import OrderService

        OrderService().create_order(other, items=[{"product_id": self.product.id, "quantity": 1}])
        OrderService().create_order(self.user, items=[{"product_id": self.product.id, "quantity": 1}])

        resp = self.client.get("/api/orders/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.data), 1)

    def test_create_order_rejects_out_of_stock(self):
        resp = self.client.post(
            "/api/orders/", {"items": [{"product_id": self.product.id, "quantity": 999}]}, format="json"
        )
        self.assertEqual(resp.status_code, 400)


class PaymentAPITests(AuthenticatedAPITestCase):
    def setUp(self):
        super().setUp()
        self.product = Product.objects.create(name="Headphones", sku="HP-1", price=Decimal("30.00"), stock=4)
        resp = self.client.post(
            "/api/orders/", {"items": [{"product_id": self.product.id, "quantity": 1}]}, format="json"
        )
        self.order_id = resp.data["id"]

    @patch("apps.payments.services.get_strategy")
    def test_checkout_and_confirm_flow(self, mock_get_strategy):
        mock_get_strategy.return_value = FakeStrategy(outcome="success")

        resp = self.client.post(
            "/api/payments/checkout/", {"order_id": self.order_id, "provider": "stripe"}, format="json"
        )
        self.assertEqual(resp.status_code, 201, resp.data)
        transaction_id = resp.data["transaction_id"]
        self.assertEqual(resp.data["status"], "pending")

        resp = self.client.post(f"/api/payments/{transaction_id}/confirm/", {}, format="json")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["status"], "success")

        order_resp = self.client.get(f"/api/orders/{self.order_id}/")
        self.assertEqual(order_resp.data["status"], "paid")

    def test_checkout_requires_ownership_of_order(self):
        other = User.objects.create_user(email="stranger@example.com", password="StrangerPass123")
        from apps.orders.services import OrderService

        other_order = OrderService().create_order(other, items=[{"product_id": self.product.id, "quantity": 1}])

        resp = self.client.post(
            "/api/payments/checkout/", {"order_id": other_order.id, "provider": "stripe"}, format="json"
        )
        self.assertEqual(resp.status_code, 404)


class WebhookAPITests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(email="webhookuser@example.com", password="WebhookPass123")
        self.product = Product.objects.create(name="Mouse", sku="MS-1", price=Decimal("20.00"), stock=2)

    @patch("apps.payments.services.get_strategy")
    def test_bkash_callback_marks_payment_success(self, mock_get_strategy):
        mock_get_strategy.return_value = FakeStrategy()
        from apps.orders.services import OrderService
        from apps.payments.services import PaymentService

        order = OrderService().create_order(self.user, items=[{"product_id": self.product.id, "quantity": 1}])
        payment = PaymentService().checkout(order, provider="bkash")

        resp = self.client.get(f"/api/payments/bkash/callback/?paymentID={payment.transaction_id}&status=success")
        self.assertEqual(resp.status_code, 200, resp.data)
        self.assertEqual(resp.data["status"], "success")

    def test_bkash_callback_missing_payment_id(self):
        resp = self.client.get("/api/payments/bkash/callback/")
        self.assertEqual(resp.status_code, 400)
