"""
Domain service layer for Orders.

`OrderService` is the OOP class the assessment asks for. It implements the
deterministic algorithm for computing subtotals/totals, and coordinates
order creation. Stock is intentionally NOT touched here - per the required
order flow, stock is only reduced after a successful payment (see
apps.payments.services.PaymentService.confirm).
"""
from decimal import Decimal

from django.db import transaction

from apps.common.exceptions import DomainError
from apps.products.models import Product

from .models import Order, OrderItem


class OrderService:
    def __init__(self, order_model=None, order_item_model=None):
        self.order_model = order_model or Order
        self.order_item_model = order_item_model or OrderItem

    @transaction.atomic
    def create_order(self, user, items: list[dict]) -> Order:
        """
        items: [{"product_id": int, "quantity": int}, ...]

        Deterministic total calculation:
            subtotal_i = unit_price_i * quantity_i
            total      = sum(subtotal_i for all i)

        Prices are snapshotted from the Product table at order time so that
        later price changes never retroactively affect an existing order.
        """
        if not items:
            raise DomainError("An order must contain at least one item.", code="empty_order")

        order = self.order_model.objects.create(user=user, total_amount=Decimal("0"))
        total = Decimal("0")
        order_items = []

        for entry in items:
            product = Product.objects.select_for_update().get(pk=entry["product_id"])
            quantity = int(entry["quantity"])
            if quantity <= 0:
                raise DomainError("Quantity must be positive.", code="invalid_quantity")
            if product.status != Product.STATUS_ACTIVE:
                raise DomainError(f"Product '{product.name}' is not available.", code="product_inactive")
            if product.stock < quantity:
                raise DomainError(
                    f"Insufficient stock for '{product.name}'.", code="insufficient_stock"
                )

            subtotal = (product.price * quantity).quantize(Decimal("0.01"))
            total += subtotal
            order_items.append(
                self.order_item_model(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price=product.price,
                    subtotal=subtotal,
                )
            )

        self.order_item_model.objects.bulk_create(order_items)
        order.total_amount = total
        order.save(update_fields=["total_amount"])
        return order

    def cancel(self, order: Order) -> Order:
        if order.status == Order.STATUS_PAID:
            raise DomainError("A paid order cannot be canceled directly.", code="order_already_paid")
        order.status = Order.STATUS_CANCELED
        order.save(update_fields=["status"])
        return order
