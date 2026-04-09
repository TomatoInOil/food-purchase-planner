"""API views for Telegram account linking and Login Widget authentication."""

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model, login
from django.db import IntegrityError, transaction
from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import redirect
from django.utils import timezone
from django.views import View
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planner.models import TelegramLinkToken, UserTelegramProfile

logger = logging.getLogger(__name__)

User = get_user_model()

LINK_TOKEN_EXPIRY_MINUTES = 15
MAX_AUTH_AGE_SECONDS = 300  # 5 minutes — limits replay window
MAX_CLOCK_SKEW_SECONDS = 10  # tolerance for clock differences between servers


class TelegramLoginCallbackView(View):
    """Handle Telegram Login Widget redirect callback; log in or auto-create user."""

    http_method_names = ["get"]

    def get(self, request):
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)

        next_url = _safe_next_url(request.GET.get("next", ""))
        data = {k: v for k, v in request.GET.items() if k != "next"}

        if not data.get("hash"):
            return HttpResponseBadRequest("Missing auth data")

        if not settings.TELEGRAM_BOT_TOKEN:
            logger.error("Telegram bot token is not configured")
            return HttpResponseForbidden("Telegram auth is not configured")

        if not _verify_telegram_auth(data, settings.TELEGRAM_BOT_TOKEN):
            logger.warning(
                "Telegram auth: invalid hash from IP %s",
                request.META.get("REMOTE_ADDR"),
            )
            return HttpResponseForbidden("Invalid signature")

        try:
            auth_date = int(data["auth_date"])
            telegram_id = int(data["id"])
        except (KeyError, ValueError):
            return HttpResponseBadRequest("Invalid auth data fields")

        if not _is_auth_date_fresh(auth_date):
            return HttpResponseBadRequest("Auth data expired, please try again")

        user = _get_or_create_user(telegram_id, data)

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        logger.info(
            "Telegram auth: user %s logged in (telegram_id=%s)", user.pk, telegram_id
        )
        return redirect(next_url or settings.LOGIN_REDIRECT_URL)


class TelegramGenerateLinkView(APIView):
    """Generate a one-time token for linking Telegram account."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        bot_username = settings.TELEGRAM_BOT_USERNAME
        if not bot_username:
            return Response(
                {"error": "Telegram bot is not configured"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        user = request.user
        expires_at = timezone.now() + timedelta(minutes=LINK_TOKEN_EXPIRY_MINUTES)

        link_token = TelegramLinkToken.objects.create(
            user=user,
            expires_at=expires_at,
        )

        token_str = str(link_token.token)
        link = f"https://t.me/{bot_username}?start={token_str}"

        return Response(
            {
                "bot_username": bot_username,
                "token": token_str,
                "link": link,
                "expires_at": link_token.expires_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )


class TelegramStatusView(APIView):
    """Check if user has linked Telegram account."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        try:
            profile = UserTelegramProfile.objects.get(user=user)
            return Response(
                {
                    "linked": True,
                    "chat_id": profile.chat_id,
                },
                status=status.HTTP_200_OK,
            )
        except UserTelegramProfile.DoesNotExist:
            return Response(
                {
                    "linked": False,
                },
                status=status.HTTP_200_OK,
            )


def _verify_telegram_auth(data: dict, bot_token: str) -> bool:
    """Verify Telegram Login Widget data signature (HMAC-SHA256)."""
    data = dict(data)
    received_hash = data.pop("hash", "")
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret_key = hashlib.sha256(bot_token.encode()).digest()
    expected_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_hash, received_hash)


def _is_auth_date_fresh(auth_date: int) -> bool:
    """Return True if the auth_date timestamp is recent enough.

    Allows a small clock-skew tolerance because auth_date comes from
    Telegram's servers whose clock may be slightly ahead of ours.
    """
    age_seconds = timezone.now().timestamp() - auth_date
    return -MAX_CLOCK_SKEW_SECONDS <= age_seconds <= MAX_AUTH_AGE_SECONDS


def _get_or_create_user(telegram_id: int, data: dict):
    """Return existing user linked to this Telegram ID, or create a new one."""
    try:
        profile = UserTelegramProfile.objects.select_related("user").get(
            chat_id=telegram_id
        )
        return profile.user
    except UserTelegramProfile.DoesNotExist:
        return _create_user_from_telegram(telegram_id, data)


def _create_user_from_telegram(telegram_id: int, data: dict):
    """Create a new User and UserTelegramProfile from Telegram widget data.

    Wrapped in a transaction so that concurrent requests for the same
    telegram_id result in one user rather than an IntegrityError 500.
    """
    try:
        with transaction.atomic():
            username = _build_username(telegram_id, data.get("username"))
            user = User.objects.create_user(
                username=username,
                first_name=data.get("first_name", ""),
                last_name=data.get("last_name", ""),
            )
            UserTelegramProfile.objects.create(user=user, chat_id=telegram_id)
    except IntegrityError:
        profile = UserTelegramProfile.objects.select_related("user").get(
            chat_id=telegram_id
        )
        return profile.user
    logger.info(
        "Telegram auth: created new user %s for telegram_id=%s", user.pk, telegram_id
    )
    return user


def _safe_next_url(next_url: str) -> str:
    """Return next_url if it is a safe relative path, otherwise empty string."""
    if not next_url:
        return ""
    parsed = urlparse(next_url)
    if parsed.scheme or parsed.netloc:
        return ""
    return next_url


def _build_username(telegram_id: int, tg_username: str | None) -> str:
    """Build a unique Django username from Telegram data.

    Tries the Telegram username, then appends the telegram_id as a suffix,
    and falls back to a random hex suffix if both are taken.
    """
    base = tg_username if tg_username else f"user_{telegram_id}"
    for candidate in (base, f"{base}_{telegram_id}"):
        if not User.objects.filter(username=candidate).exists():
            return candidate
    while True:
        candidate = f"tg_{secrets.token_hex(4)}"
        if not User.objects.filter(username=candidate).exists():
            return candidate
