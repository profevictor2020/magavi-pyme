from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .factories import UserFactory
from .models import User


class RegisterTests(APITestCase):
    def test_register_creates_user_and_returns_tokens(self):
        response = self.client.post(
            reverse("auth-register"),
            {"email": "nueva@empresa.cl", "password": "ClaveSegura123!", "first_name": "Marcela"},
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertTrue(User.objects.filter(email="nueva@empresa.cl").exists())

    def test_register_rejects_weak_password(self):
        response = self.client.post(
            reverse("auth-register"),
            {"email": "debil@empresa.cl", "password": "123", "first_name": "X"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="debil@empresa.cl").exists())

    def test_register_rejects_duplicate_email(self):
        UserFactory(email="ya@empresa.cl")

        response = self.client.post(
            reverse("auth-register"),
            {"email": "ya@empresa.cl", "password": "ClaveSegura123!", "first_name": "X"},
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(APITestCase):
    def test_login_with_correct_credentials(self):
        UserFactory(email="marcela@empresa.cl", password="ClaveSegura123!")

        response = self.client.post(
            reverse("auth-login"),
            {"email": "marcela@empresa.cl", "password": "ClaveSegura123!"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_login_with_wrong_password_fails(self):
        UserFactory(email="marcela@empresa.cl", password="ClaveSegura123!")

        response = self.client.post(
            reverse("auth-login"),
            {"email": "marcela@empresa.cl", "password": "incorrecta"},
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutTests(APITestCase):
    def test_logout_blacklists_refresh_token(self):
        user = UserFactory(password="ClaveSegura123!")
        login = self.client.post(
            reverse("auth-login"), {"email": user.email, "password": "ClaveSegura123!"}
        )
        refresh = login.data["refresh"]

        logout_response = self.client.post(reverse("auth-logout"), {"refresh": refresh})
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        reuse_response = self.client.post(reverse("auth-refresh"), {"refresh": refresh})
        self.assertEqual(reuse_response.status_code, status.HTTP_401_UNAUTHORIZED)


class MeViewTests(APITestCase):
    def test_requires_authentication(self):
        response = self.client.get(reverse("auth-me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_returns_current_user(self):
        user = UserFactory(email="marcela@empresa.cl")
        self.client.force_authenticate(user)

        response = self.client.get(reverse("auth-me"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "marcela@empresa.cl")
