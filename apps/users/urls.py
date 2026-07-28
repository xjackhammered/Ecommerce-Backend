from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import MeView, MyOrdersView, MyPaymentsView, RegisterView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="user-register"),
    path("login/", TokenObtainPairView.as_view(), name="user-login"),
    path("login/refresh/", TokenRefreshView.as_view(), name="user-login-refresh"),
    path("me/", MeView.as_view(), name="user-me"),
    path("me/orders/", MyOrdersView.as_view(), name="user-my-orders"),
    path("me/payments/", MyPaymentsView.as_view(), name="user-my-payments"),
]
