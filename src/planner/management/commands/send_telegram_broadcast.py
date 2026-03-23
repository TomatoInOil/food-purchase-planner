"""Management command to send a broadcast message to all linked Telegram users."""

import asyncio

import telegram
from django.conf import settings
from django.core.management.base import BaseCommand
from telegram.ext import AIORateLimiter

from planner.models import UserTelegramProfile


class Command(BaseCommand):
    help = "Send broadcast message to all linked Telegram users"

    def handle(self, *args, **options):
        profiles = list(UserTelegramProfile.objects.values_list("chat_id", flat=True))
        asyncio.run(self._broadcast(profiles))

    async def _broadcast(self, profiles: list[int]) -> None:
        bot = telegram.Bot(
            token=settings.TELEGRAM_BOT_TOKEN,
            rate_limiter=AIORateLimiter(),
        )
        sent = 0
        failed = 0
        async with bot:
            for chat_id in profiles:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text="Test broadcast from food-purchase-planner",
                    )
                    sent += 1
                except Exception as e:
                    self.stdout.write(f"Failed to send to {chat_id}: {e}")
                    failed += 1
        self.stdout.write(f"Broadcast complete: {sent} sent, {failed} failed.")
