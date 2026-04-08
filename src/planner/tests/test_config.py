"""Tests for config: exception handler, Telegram auth views, protected pages."""

import hashlib
import hmac
import time

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from config.exceptions import _flatten_detail
from planner.models import UserTelegramProfile
from planner.views_telegram import (
    _build_username,
    _is_auth_date_fresh,
    _verify_telegram_auth,
)

User = get_user_model()

BOT_TOKEN = "test_bot_token_12345"


def _make_auth_data(
    telegram_id: int = 123456, username: str = "tguser", age_seconds: int = 0
) -> dict:
    """Build valid Telegram Login Widget auth data signed with BOT_TOKEN."""
    auth_date = int(time.time()) - age_seconds
    data = {
        "id": str(telegram_id),
        "first_name": "Test",
        "last_name": "User",
        "username": username,
        "auth_date": str(auth_date),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
    data["hash"] = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return data


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


class ProtectedPagesTests(TestCase):
    """Test that protected pages redirect unauthenticated users to login."""

    def setUp(self):
        self.client = Client()

    def test_home_requires_login(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_cook_today_requires_login(self):
        response = self.client.get("/cook-today/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response.url)

    def test_cook_today_renders_for_authenticated_user(self):
        user = User.objects.create_user(username="alice", password="pass")
        self.client.force_login(user)
        response = self.client.get("/cook-today/")
        self.assertEqual(response.status_code, 200)

    def test_home_renders_for_authenticated_user(self):
        user = User.objects.create_user(username="alice", password="pass")
        self.client.force_login(user)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)


class TelegramLoginPageTests(TestCase):
    """Test that the Telegram login page renders correctly."""

    def setUp(self):
        self.client = Client()

    def test_login_page_renders(self):
        response = self.client.get("/login/")
        self.assertEqual(response.status_code, 200)

    def test_login_page_uses_telegram_template(self):
        response = self.client.get("/login/")
        self.assertTemplateUsed(response, "auth/telegram_login.html")

    def test_register_url_removed(self):
        response = self.client.get("/register/")
        self.assertEqual(response.status_code, 404)


class VerifyTelegramAuthTests(TestCase):
    """Unit tests for _verify_telegram_auth."""

    def test_valid_signature(self):
        data = _make_auth_data()
        self.assertTrue(_verify_telegram_auth(data, BOT_TOKEN))

    def test_wrong_bot_token_rejected(self):
        data = _make_auth_data()
        self.assertFalse(_verify_telegram_auth(data, "wrong_token"))

    def test_tampered_data_rejected(self):
        data = _make_auth_data()
        data["first_name"] = "Hacker"
        self.assertFalse(_verify_telegram_auth(data, BOT_TOKEN))

    def test_missing_hash_rejected(self):
        data = _make_auth_data()
        data.pop("hash")
        self.assertFalse(_verify_telegram_auth(data, BOT_TOKEN))

    def test_original_dict_not_mutated(self):
        data = _make_auth_data()
        original_keys = set(data.keys())
        _verify_telegram_auth(data, BOT_TOKEN)
        self.assertEqual(set(data.keys()), original_keys)


class IsAuthDateFreshTests(TestCase):
    """Unit tests for _is_auth_date_fresh."""

    def test_fresh_timestamp_accepted(self):
        self.assertTrue(_is_auth_date_fresh(int(time.time())))

    def test_timestamp_55_minutes_ago_accepted(self):
        self.assertTrue(_is_auth_date_fresh(int(time.time()) - 55 * 60))

    def test_timestamp_2_hours_ago_rejected(self):
        self.assertFalse(_is_auth_date_fresh(int(time.time()) - 7200))


class BuildUsernameTests(TestCase):
    """Unit tests for _build_username."""

    def test_uses_telegram_username_if_available(self):
        self.assertEqual(_build_username(123, "johndoe"), "johndoe")

    def test_falls_back_to_user_id_prefix_if_no_username(self):
        self.assertEqual(_build_username(123, None), "user_123")

    def test_appends_telegram_id_on_collision(self):
        User.objects.create_user(username="johndoe")
        self.assertEqual(_build_username(456, "johndoe"), "johndoe_456")

    def test_no_username_collision_appends_id(self):
        User.objects.create_user(username="user_789")
        self.assertEqual(_build_username(789, None), "user_789_789")


class TelegramLoginCallbackTests(TestCase):
    """Integration tests for TelegramLoginCallbackView."""

    def setUp(self):
        self.client = Client()

    def _get_callback(self, data: dict):
        return self.client.get("/telegram/callback/", data)

    def test_missing_hash_returns_400(self):
        response = self._get_callback({"id": "123", "auth_date": str(int(time.time()))})
        self.assertEqual(response.status_code, 400)

    def test_invalid_hash_returns_403(self):
        data = _make_auth_data()
        data["hash"] = "deadbeef" * 8
        with self.settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN):
            response = self._get_callback(data)
        self.assertEqual(response.status_code, 403)

    def test_expired_auth_date_returns_400(self):
        data = _make_auth_data(age_seconds=7200)
        with self.settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN):
            response = self._get_callback(data)
        self.assertEqual(response.status_code, 400)

    def test_existing_user_logs_in_and_redirects(self):
        user = User.objects.create_user(username="tguser")
        UserTelegramProfile.objects.create(user=user, chat_id=123456)
        data = _make_auth_data(telegram_id=123456)

        with self.settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN):
            response = self._get_callback(data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/")

    def test_existing_user_session_is_set(self):
        user = User.objects.create_user(username="tguser")
        UserTelegramProfile.objects.create(user=user, chat_id=123456)
        data = _make_auth_data(telegram_id=123456)

        with self.settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN):
            self.client.get("/telegram/callback/", data)

        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)

    def test_new_user_auto_created_and_logged_in(self):
        data = _make_auth_data(telegram_id=999999, username="newperson")

        with self.settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN):
            response = self._get_callback(data)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newperson").exists())
        self.assertTrue(UserTelegramProfile.objects.filter(chat_id=999999).exists())

    def test_new_user_first_name_saved(self):
        data = _make_auth_data(telegram_id=111111, username="firsttest")

        with self.settings(TELEGRAM_BOT_TOKEN=BOT_TOKEN):
            self.client.get("/telegram/callback/", data)

        user = User.objects.get(username="firsttest")
        self.assertEqual(user.first_name, "Test")

    def test_unconfigured_bot_token_returns_403(self):
        data = _make_auth_data()
        with self.settings(TELEGRAM_BOT_TOKEN=""):
            response = self._get_callback(data)
        self.assertEqual(response.status_code, 403)


class DeleteUnlinkedUsersCommandTests(TestCase):
    """Tests for delete_unlinked_users management command."""

    def _run_command(self, dry_run: bool = False) -> str:
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command("delete_unlinked_users", dry_run=dry_run, stdout=out)
        return out.getvalue()

    def test_dry_run_does_not_delete(self):
        User.objects.create_user(username="nolink")
        output = self._run_command(dry_run=True)
        self.assertIn("DRY RUN", output)
        self.assertTrue(User.objects.filter(username="nolink").exists())

    def test_deletes_unlinked_users(self):
        User.objects.create_user(username="nolink")
        self._run_command()
        self.assertFalse(User.objects.filter(username="nolink").exists())

    def test_does_not_delete_linked_users(self):
        user = User.objects.create_user(username="linked")
        UserTelegramProfile.objects.create(user=user, chat_id=42)
        self._run_command()
        self.assertTrue(User.objects.filter(username="linked").exists())

    def test_does_not_delete_superusers(self):
        User.objects.create_superuser(username="admin", password="pass")
        self._run_command()
        self.assertTrue(User.objects.filter(username="admin").exists())

    def test_reports_no_users_when_none_unlinked(self):
        output = self._run_command()
        self.assertIn("No unlinked users", output)
