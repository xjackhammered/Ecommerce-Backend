from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.serializers import OrderSerializer
from apps.payments.serializers import PaymentSerializer

from .serializers import UserRegisterSerializer, UserSerializer
from .services import UserService


class RegisterView(APIView):

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UserRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = UserService().register(**serializer.validated_data)
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)


class MeView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class MyOrdersView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = UserService().get_orders(request.user)
        return Response(OrderSerializer(orders, many=True).data)


class MyPaymentsView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        payments = UserService().get_payments(request.user)
        return Response(PaymentSerializer(payments, many=True).data)
