"""Telegram polling bot for account linking."""

import os
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings  # noqa: E402
from telegram import Chat, Update  # noqa: E402
from telegram.ext import (  # noqa: E402
    AIORateLimiter,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

from planner.models import TelegramLinkToken, UserTelegramProfile  # noqa: E402


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start <token> command for account linking."""
    chat = update.effective_chat
    if chat is None:
        return

    if not context.args:
        await chat.send_message("Send /start <token> to link your account.")
        return

    await _link_account(chat, token_str=context.args[0])


async def _link_account(chat: Chat, token_str: str) -> None:
    """Validate token and link Telegram account to a user."""
    if _is_chat_already_linked(chat.id):
        await chat.send_message("This Telegram account is already linked.")
        return

    link_token = _find_valid_token(token_str)
    if link_token is None:
        await chat.send_message("Invalid or expired token. Please generate a new link.")
        return

    _consume_token_and_save_profile(link_token, chat_id=chat.id)
    await chat.send_message("Your Telegram account has been successfully linked!")


def _is_chat_already_linked(chat_id: int) -> bool:
    """Return True if this Telegram chat is already linked to a user account."""
    return UserTelegramProfile.objects.filter(chat_id=chat_id).exists()


def _find_valid_token(token_str: str) -> TelegramLinkToken | None:
    """Look up and return a valid (unused, non-expired) link token, or None."""
    try:
        token_uuid = uuid.UUID(token_str)
        link_token = TelegramLinkToken.objects.select_related("user").get(
            token=token_uuid
        )
    except (ValueError, TelegramLinkToken.DoesNotExist):
        return None

    return link_token if link_token.is_valid() else None


def _consume_token_and_save_profile(
    link_token: TelegramLinkToken, chat_id: int
) -> None:
    """Mark token as used and create UserTelegramProfile."""
    link_token.is_used = True
    link_token.save(update_fields=["is_used"])
    UserTelegramProfile.objects.create(user=link_token.user, chat_id=chat_id)


def run_bot() -> None:
    """Build and run the polling bot."""
    application = (
        ApplicationBuilder()
        .token(settings.TELEGRAM_BOT_TOKEN)
        .rate_limiter(AIORateLimiter())
        .build()
    )
    application.add_handler(CommandHandler("start", start_handler))
    application.run_polling()
