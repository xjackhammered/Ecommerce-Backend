from django.core.cache import cache
from django.db import transaction
from django.db.models import F

from apps.common.exceptions import DomainError

from .models import Category, Product

CATEGORY_TREE_CACHE_KEY = "category_tree:v1"
CATEGORY_TREE_CACHE_TTL_SECONDS = 60 * 60  # 1 hour


class ProductService:

    def __init__(self, product_model=None):
        self.product_model = product_model or Product

    def create(self, **fields) -> Product:
        if self.product_model.objects.filter(sku=fields.get("sku")).exists():
            raise DomainError("A product with this SKU already exists.", code="sku_taken")
        return self.product_model.objects.create(**fields)

    def list_active(self):
        return self.product_model.objects.filter(status=Product.STATUS_ACTIVE)

    @transaction.atomic
    def reduce_stock(self, product_id: int, quantity: int) -> Product:

        if quantity <= 0:
            raise DomainError("Quantity must be positive.", code="invalid_quantity")

        product = self.product_model.objects.select_for_update().get(pk=product_id)
        if product.stock < quantity:
            raise DomainError(
                f"Insufficient stock for '{product.name}': have {product.stock}, need {quantity}.",
                code="insufficient_stock",
            )
        updated = self.product_model.objects.filter(
            pk=product_id, stock__gte=quantity
        ).update(stock=F("stock") - quantity)
        if updated == 0:
            # Someone else consumed the stock between the check and the update.
            raise DomainError(
                f"Stock for '{product.name}' changed concurrently, please retry.",
                code="stock_conflict",
            )
        product.refresh_from_db()
        return product


class CategoryTreeService:


    def __init__(self, category_model=None, cache_backend=None):
        self.category_model = category_model or Category
        self.cache = cache_backend or cache

    def get_tree(self, use_cache: bool = True) -> list[dict]:
        if use_cache:
            cached = self.cache.get(CATEGORY_TREE_CACHE_KEY)
            if cached is not None:
                return cached

        tree = self._build_tree()
        self.cache.set(CATEGORY_TREE_CACHE_KEY, tree, CATEGORY_TREE_CACHE_TTL_SECONDS)
        return tree

    def invalidate_cache(self):
        self.cache.delete(CATEGORY_TREE_CACHE_KEY)

    def _build_tree(self) -> list[dict]:
        categories = list(self.category_model.objects.all().values("id", "name", "parent_id"))
        children_by_parent: dict = {}
        for c in categories:
            children_by_parent.setdefault(c["parent_id"], []).append(c)

        def dfs(parent_id):
            nodes = []
            for cat in children_by_parent.get(parent_id, []):
                nodes.append(
                    {
                        "id": cat["id"],
                        "name": cat["name"],
                        "children": dfs(cat["id"]),
                    }
                )
            return nodes

        return dfs(None)

    def get_descendant_ids(self, category_id: int) -> list[int]:

        tree = self.get_tree()

        def find_node(nodes, target_id):
            for node in nodes:
                if node["id"] == target_id:
                    return node
                found = find_node(node["children"], target_id)
                if found:
                    return found
            return None

        # The requested category might itself be nested; search the whole tree.
        root_candidates = self.category_model.objects.filter(pk=category_id).values("id", "name")
        if not root_candidates:
            return []

        node = find_node(tree, category_id)
        ids = [category_id]

        def collect(n):
            for child in n["children"] if n else []:
                ids.append(child["id"])
                collect(child)

        if node:
            collect(node)
        return ids

    def recommend_products(self, category_id: int, limit: int = 10):
        
        category_ids = self.get_descendant_ids(category_id)
        if not category_ids:
            return Product.objects.none()
        return Product.objects.filter(
            category_id__in=category_ids, status=Product.STATUS_ACTIVE
        )[:limit]
