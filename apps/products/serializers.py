from rest_framework import serializers

from .models import Category, Product


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "parent"]


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = [
            "id", "name", "sku", "description", "price", "stock",
            "status", "category", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
