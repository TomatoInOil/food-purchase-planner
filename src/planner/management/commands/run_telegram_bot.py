"""Management command to run the Telegram polling bot."""

from django.core.management.base import BaseCommand

from planner.bot import run_bot


class Command(BaseCommand):
    help = "Run Telegram polling bot"

    def handle(self, *args, **options):
        run_bot()
