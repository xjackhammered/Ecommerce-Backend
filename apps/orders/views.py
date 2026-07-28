from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from .models import Order
from .serializers import CreateOrderSerializer, OrderSerializer
from .services import OrderService


class OrderViewSet(mixins.CreateModelMixin, mixins.ListModelMixin,
                    mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    POST /api/orders/       - create an order from a cart of {product_id, quantity}
    GET  /api/orders/       - list the authenticated user's own orders
    GET  /api/orders/{id}/  - retrieve one of the authenticated user's own orders
    """

    serializer_class = OrderSerializer

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by("-created_at")

    def create(self, request, *args, **kwargs):
        input_serializer = CreateOrderSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        order = OrderService().create_order(
            user=request.user, items=input_serializer.validated_data["items"]
        )
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
