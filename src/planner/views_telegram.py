"""API views for Telegram account linking."""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from planner.models import TelegramLinkToken, UserTelegramProfile

LINK_TOKEN_EXPIRY_MINUTES = 15


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
