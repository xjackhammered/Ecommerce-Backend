from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.permissions import IsAdminOrReadOnly

from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer
from .services import CategoryTreeService, ProductService


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]

    @action(detail=False, methods=["get"], url_path="tree")
    def tree(self, request):
        return Response(CategoryTreeService().get_tree())

    @action(detail=True, methods=["get"], url_path="recommended-products")
    def recommended_products(self, request, pk=None):
        products = CategoryTreeService().recommend_products(int(pk))
        return Response(ProductSerializer(products, many=True).data)


class ProductViewSet(viewsets.ModelViewSet):


    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]

    def get_queryset(self):
        qs = Product.objects.all().order_by("-created_at")
        if not (self.request.user.is_authenticated and self.request.user.is_admin):
            qs = qs.filter(status=Product.STATUS_ACTIVE)
        return qs

    def perform_create(self, serializer):
        service = ProductService()
        product = service.create(**serializer.validated_data)
        serializer.instance = product
