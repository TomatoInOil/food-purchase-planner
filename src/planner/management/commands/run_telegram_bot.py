"""Management command to run the Telegram polling bot."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run Telegram polling bot"

    def handle(self, *args, **options):
        from planner.bot import run_bot

        run_bot()
