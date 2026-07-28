import time
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Any

import requests
import stripe
from django.conf import settings
from django.core.cache import cache

from apps.common.exceptions import DomainError


class PaymentStrategy(ABC):

    provider_name: str

    @abstractmethod
    def initiate(self, order, amount: Decimal) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def confirm(self, transaction_id: str, payload: dict) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def query(self, transaction_id: str) -> dict[str, Any]:
        raise NotImplementedError


class StripeStrategy(PaymentStrategy):
    provider_name = "stripe"

    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY

    def initiate(self, order, amount: Decimal) -> dict[str, Any]:
        # Stripe expects the smallest currency unit (cents).
        amount_cents = int((amount * 100).to_integral_value())
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="usd",
            metadata={"order_id": str(order.id)},
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
        )
        return {
            "transaction_id": intent["id"],
            "status": "pending",
            "raw_response": intent.to_dict_recursive() if hasattr(intent, "to_dict_recursive") else dict(intent),
            "client_payload": {"client_secret": intent["client_secret"]},
        }

    def confirm(self, transaction_id: str, payload: dict) -> dict[str, Any]:
        payment_method = payload.get("payment_method", "pm_card_visa")
        intent = stripe.PaymentIntent.confirm(transaction_id, payment_method=payment_method)
        status = "success" if intent["status"] == "succeeded" else (
            "failed" if intent["status"] in ("canceled",) else "pending"
        )
        return {"status": status, "raw_response": dict(intent)}

    def query(self, transaction_id: str) -> dict[str, Any]:
        intent = stripe.PaymentIntent.retrieve(transaction_id)
        status = "success" if intent["status"] == "succeeded" else (
            "failed" if intent["status"] in ("canceled",) else "pending"
        )
        return {"status": status, "raw_response": dict(intent)}

    @staticmethod
    def verify_webhook(payload: bytes, sig_header: str):
        """Verifies a Stripe webhook signature; raises DomainError if invalid."""
        try:
            return stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except (ValueError, stripe.error.SignatureVerificationError) as exc:
            raise DomainError("Invalid Stripe webhook signature.", code="invalid_webhook") from exc


class BkashStrategy(PaymentStrategy):

    provider_name = "bkash"
    TOKEN_CACHE_KEY = "bkash:grant_token"

    def __init__(self):
        self.base_url = settings.BKASH_BASE_URL.rstrip("/")

    def _get_token(self) -> str:
        cached = cache.get(self.TOKEN_CACHE_KEY)
        if cached:
            return cached

        resp = requests.post(
            f"{self.base_url}/tokenized/checkout/token/grant",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "username": settings.BKASH_USERNAME,
                "password": settings.BKASH_PASSWORD,
            },
            json={
                "app_key": settings.BKASH_APP_KEY,
                "app_secret": settings.BKASH_APP_SECRET,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data["id_token"]
        cache.set(self.TOKEN_CACHE_KEY, token, int(data.get("expires_in", 3300)) - 60)
        return token

    def _headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": self._get_token(),
            "X-APP-Key": settings.BKASH_APP_KEY,
        }

    def initiate(self, order, amount: Decimal) -> dict[str, Any]:
        resp = requests.post(
            f"{self.base_url}/tokenized/checkout/create",
            headers=self._headers(),
            json={
                "mode": "0011",
                "payerReference": str(order.user_id),
                "callbackURL": settings.BKASH_CALLBACK_URL,
                "amount": str(amount),
                "currency": "BDT",
                "intent": "sale",
                "merchantInvoiceNumber": f"ORDER-{order.id}-{int(time.time())}",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "transaction_id": data["paymentID"],
            "status": "pending",
            "raw_response": data,
            "client_payload": {"bkash_url": data.get("bkashURL")},
        }

    def confirm(self, transaction_id: str, payload: dict) -> dict[str, Any]:
        resp = requests.post(
            f"{self.base_url}/tokenized/checkout/execute",
            headers=self._headers(),
            json={"paymentID": transaction_id},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        status = "success" if data.get("transactionStatus") == "Completed" else "failed"
        return {"status": status, "raw_response": data}

    def query(self, transaction_id: str) -> dict[str, Any]:
        resp = requests.post(
            f"{self.base_url}/tokenized/checkout/payment/status",
            headers=self._headers(),
            json={"paymentID": transaction_id},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        status = "success" if data.get("transactionStatus") == "Completed" else (
            "pending" if data.get("transactionStatus") in ("Initiated",) else "failed"
        )
        return {"status": status, "raw_response": data}


STRATEGY_REGISTRY: dict[str, type[PaymentStrategy]] = {
    StripeStrategy.provider_name: StripeStrategy,
    BkashStrategy.provider_name: BkashStrategy,
}


def get_strategy(provider: str) -> PaymentStrategy:
    strategy_cls = STRATEGY_REGISTRY.get(provider)
    if not strategy_cls:
        raise DomainError(f"Unsupported payment provider '{provider}'.", code="unsupported_provider")
    return strategy_cls()
