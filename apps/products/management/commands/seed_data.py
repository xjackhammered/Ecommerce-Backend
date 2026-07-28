from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.products.models import Category, Product

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds an admin user, a sample category tree, and sample products."

    @transaction.atomic
    def handle(self, *args, **options):
        admin, created = User.objects.get_or_create(
            email="admin@example.com",
            defaults={"full_name": "Admin", "is_admin": True, "is_staff": True, "is_superuser": True},
        )
        if created:
            admin.set_password("Admin@12345")
            admin.save()
            self.stdout.write(self.style.SUCCESS("Created admin@example.com / Admin@12345"))
        else:
            self.stdout.write("Admin user already exists, skipping.")

        electronics, _ = Category.objects.get_or_create(name="Electronics", parent=None)
        phones, _ = Category.objects.get_or_create(name="Phones", parent=electronics)
        smartphones, _ = Category.objects.get_or_create(name="Smartphones", parent=phones)
        laptops, _ = Category.objects.get_or_create(name="Laptops", parent=electronics)

        products = [
            dict(name="Aurora X12 Smartphone", sku="PHN-AUR-X12", price=Decimal("399.99"),
                 stock=50, category=smartphones,
                 description="6.5-inch display, 128GB storage."),
            dict(name="Nimbus 5G Smartphone", sku="PHN-NIM-5G", price=Decimal("549.00"),
                 stock=30, category=smartphones,
                 description="5G-ready flagship phone."),
            dict(name="Zenith 14 Laptop", sku="LAP-ZEN-14", price=Decimal("899.00"),
                 stock=20, category=laptops,
                 description="14-inch ultrabook, 16GB RAM."),
        ]
        for data in products:
            Product.objects.get_or_create(sku=data["sku"], defaults=data)

        self.stdout.write(self.style.SUCCESS("Seed data ready."))
