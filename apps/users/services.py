from django.contrib.auth import get_user_model
from django.db import IntegrityError

from apps.common.exceptions import DomainError

UserModel = get_user_model()


class UserService:

    def __init__(self, user_model=None):
        self.user_model = user_model or UserModel

    def register(self, email: str, password: str, full_name: str = ""):
        email = email.strip().lower()
        if self.user_model.objects.filter(email=email).exists():
            raise DomainError("A user with this email already exists.", code="email_taken")
        try:
            return self.user_model.objects.create_user(
                email=email, password=password, full_name=full_name
            )
        except IntegrityError as exc:
            raise DomainError("Could not create user.", code="user_creation_failed") from exc

    def get_orders(self, user):
        return user.orders.all().order_by("-created_at")

    def get_payments(self, user):
        from apps.payments.models import Payment

        return Payment.objects.filter(order__user=user).order_by("-created_at")
