from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.common.exceptions import DomainError

from .services import UserService

User = get_user_model()


class UserServiceTests(TestCase):
    def setUp(self):
        self.service = UserService()

    def test_register_creates_user_with_normalized_email(self):
        user = self.service.register(email="Test@Example.com", password="StrongPass123", full_name="Test User")
        self.assertEqual(user.email, "test@example.com")
        self.assertTrue(user.check_password("StrongPass123"))

    def test_register_rejects_duplicate_email(self):
        self.service.register(email="dup@example.com", password="StrongPass123")
        with self.assertRaises(DomainError):
            self.service.register(email="dup@example.com", password="AnotherPass123")
