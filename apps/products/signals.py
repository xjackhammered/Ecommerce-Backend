from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Category
from .services import CategoryTreeService


@receiver([post_save, post_delete], sender=Category)
def invalidate_category_tree_cache(sender, **kwargs):
    CategoryTreeService().invalidate_cache()
