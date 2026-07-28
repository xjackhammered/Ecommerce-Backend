from decimal import Decimal

from django.test import TestCase

from apps.common.exceptions import DomainError

from .models import Category, Product
from .services import CategoryTreeService, ProductService


class ProductServiceTests(TestCase):
    def setUp(self):
        self.service = ProductService()
        self.product = Product.objects.create(
            name="Test Widget", sku="TW-001", price=Decimal("10.00"), stock=5
        )

    def test_reduce_stock_success(self):
        updated = self.service.reduce_stock(self.product.id, 3)
        self.assertEqual(updated.stock, 2)

    def test_reduce_stock_insufficient(self):
        with self.assertRaises(DomainError):
            self.service.reduce_stock(self.product.id, 10)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 5)  # unchanged

    def test_reduce_stock_rejects_non_positive_quantity(self):
        with self.assertRaises(DomainError):
            self.service.reduce_stock(self.product.id, 0)

    def test_create_rejects_duplicate_sku(self):
        with self.assertRaises(DomainError):
            self.service.create(name="Other", sku="TW-001", price=Decimal("5.00"), stock=1)


class CategoryTreeServiceTests(TestCase):
    def setUp(self):
        self.electronics = Category.objects.create(name="Electronics")
        self.phones = Category.objects.create(name="Phones", parent=self.electronics)
        self.smartphones = Category.objects.create(name="Smartphones", parent=self.phones)
        self.laptops = Category.objects.create(name="Laptops", parent=self.electronics)
        self.service = CategoryTreeService()

    def test_dfs_tree_structure(self):
        tree = self.service.get_tree(use_cache=False)
        self.assertEqual(len(tree), 1)  # single root: Electronics
        electronics_node = tree[0]
        self.assertEqual(electronics_node["name"], "Electronics")
        child_names = {c["name"] for c in electronics_node["children"]}
        self.assertEqual(child_names, {"Phones", "Laptops"})

    def test_descendant_ids_includes_self_and_children(self):
        ids = self.service.get_descendant_ids(self.electronics.id)
        self.assertEqual(
            set(ids), {self.electronics.id, self.phones.id, self.smartphones.id, self.laptops.id}
        )

    def test_recommend_products_across_subtree(self):
        p1 = Product.objects.create(name="Phone A", sku="P-A", price=Decimal("100"), stock=1, category=self.smartphones)
        Product.objects.create(name="Laptop A", sku="L-A", price=Decimal("500"), stock=1, category=self.laptops)
        recs = self.service.recommend_products(self.phones.id)
        self.assertIn(p1, list(recs))

    def test_tree_is_cached(self):
        self.service.get_tree() 
        Category.objects.create(name="Tablets", parent=self.electronics)
        tree = self.service.get_tree()
        names = {c["name"] for c in tree[0]["children"]}
        self.assertIn("Tablets", names)
