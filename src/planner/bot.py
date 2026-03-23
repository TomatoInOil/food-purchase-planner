"""Telegram polling bot for account linking."""

import os
import uuid

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django

django.setup()

from django.conf import settings  # noqa: E402
from telegram import Update  # noqa: E402
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

    args = context.args or []

    if not args:
        await chat.send_message("Send /start <token> to link your account.")
        return

    token_str = args[0]

    # Check if this chat_id is already linked
    if UserTelegramProfile.objects.filter(chat_id=chat.id).exists():
        await chat.send_message("This Telegram account is already linked.")
        return

    try:
        token_uuid = uuid.UUID(token_str)
        link_token = TelegramLinkToken.objects.select_related("user").get(
            token=token_uuid
        )
    except (ValueError, TelegramLinkToken.DoesNotExist):
        await chat.send_message("Invalid or expired token. Please generate a new link.")
        return

    if not link_token.is_valid():
        await chat.send_message(
            "Token has expired or already been used. Please generate a new link."
        )
        return

    link_token.is_used = True
    link_token.save(update_fields=["is_used"])
    UserTelegramProfile.objects.create(user=link_token.user, chat_id=chat.id)

    await chat.send_message("Your Telegram account has been successfully linked!")


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
