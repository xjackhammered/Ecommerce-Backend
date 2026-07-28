from django.urls import path

from .views import BkashCallbackView, CheckoutView, ConfirmPaymentView, StripeWebhookView

urlpatterns = [
    path("checkout/", CheckoutView.as_view(), name="payment-checkout"),
    path("<str:transaction_id>/confirm/", ConfirmPaymentView.as_view(), name="payment-confirm"),
    path("stripe/webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("bkash/callback/", BkashCallbackView.as_view(), name="bkash-callback"),
]
