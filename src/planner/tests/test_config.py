"""Tests for config: exception handler, auth views, RegisterForm."""

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from config.exceptions import _flatten_detail

User = get_user_model()


class FlattenDetailTests(TestCase):
    """Test _flatten_detail utility used by the custom exception handler."""

    def test_string_returned_as_is(self):
        self.assertEqual(_flatten_detail("error msg"), "error msg")

    def test_list_of_strings_joined(self):
        result = _flatten_detail(["one", "two"])
        self.assertEqual(result, "one two")

    def test_dict_values_joined(self):
        result = _flatten_detail({"field1": "err1", "field2": "err2"})
        self.assertIn("err1", result)
        self.assertIn("err2", result)

    def test_nested_dict_with_list(self):
        result = _flatten_detail({"name": ["required", "invalid"]})
        self.assertIn("required", result)
        self.assertIn("invalid", result)


class ExceptionHandlerIntegrationTests(TestCase):
    """Test that API validation errors are wrapped in {"error": "..."} format."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.client.force_login(self.user)

    def test_validation_error_returns_error_key(self):
        response = self.client.post(
            "/api/shopping-list/",
            data={},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("error", data)

    def test_validation_error_is_string(self):
        response = self.client.post(
            "/api/shopping-list/",
            data={},
            content_type="application/json",
        )
        data = response.json()
        self.assertIsInstance(data["error"], str)


class AuthViewsTests(TestCase):
    """Test login, register, and logout views."""

    def setUp(self):
        self.client = Client()

    def test_login_page_renders(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)

    def test_register_page_renders(self):
        response = self.client.get("/register/")
        self.assertEqual(response.status_code, 200)

    def test_successful_registration_redirects_and_logs_in(self):
        response = self.client.post(
            "/register/",
            data={
                "username": "newuser",
                "email": "new@test.com",
                "password1": "Str0ng!Pass#99",
                "password2": "Str0ng!Pass#99",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newuser").exists())
        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)

    def test_registration_password_mismatch(self):
        response = self.client.post(
            "/register/",
            data={
                "username": "newuser",
                "password1": "Str0ng!Pass#99",
                "password2": "DifferentPass#99",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_successful_login(self):
        User.objects.create_user(
            username="alice", password="pass123!Strong", email="alice@test.com"
        )
        response = self.client.post(
            "/login/",
            data={"username": "alice", "password": "pass123!Strong"},
        )
        self.assertEqual(response.status_code, 302)

    def test_failed_login(self):
        response = self.client.post(
            "/login/",
            data={"username": "nobody", "password": "wrongpass"},
        )
        self.assertEqual(response.status_code, 200)

    def test_logout_redirects(self):
        user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.client.force_login(user)
        response = self.client.post("/logout/")
        self.assertIn(response.status_code, [200, 302])

    def test_home_requires_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)


class RegisterFormTests(TestCase):
    """Test RegisterForm validation."""

    def test_valid_form(self):
        from config.forms import RegisterForm

        form = RegisterForm(
            data={
                "username": "newuser",
                "email": "new@test.com",
                "password1": "Str0ng!Pass#99",
                "password2": "Str0ng!Pass#99",
            }
        )
        self.assertTrue(form.is_valid())

    def test_cook_today_requires_login(self):
        response = self.client.get("/cook-today/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_cook_today_renders_for_authenticated_user(self):
        User.objects.create_user(
            username="alice", password="pass123!Strong", email="alice@test.com"
        )
        self.client.login(username="alice", password="pass123!Strong")
        response = self.client.get("/cook-today/")
        self.assertEqual(response.status_code, 200)

    def test_email_optional(self):
        from config.forms import RegisterForm

        form = RegisterForm(
            data={
                "username": "newuser",
                "password1": "Str0ng!Pass#99",
                "password2": "Str0ng!Pass#99",
            }
        )
        self.assertTrue(form.is_valid())
