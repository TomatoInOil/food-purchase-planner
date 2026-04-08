"""Management command to delete users without a linked Telegram account."""

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from planner.models import UserTelegramProfile

logger = logging.getLogger(__name__)

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Delete non-superuser accounts that have no linked Telegram profile. "
        "Run with --dry-run first to preview which users will be deleted."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview deletions without making any changes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        users = _find_unlinked_users()

        if not users:
            self.stdout.write("No unlinked users found.")
            return

        self.stdout.write(
            f"{'[DRY RUN] ' if dry_run else ''}Found {len(users)} unlinked user(s):"
        )
        for user in users:
            self.stdout.write(f"  id={user.pk} username={user.username!r}")

        if dry_run:
            self.stdout.write("Dry run complete. No changes made.")
            return

        deleted_count = _delete_users(users)
        self.stdout.write(f"Deleted {deleted_count} user(s).")
        logger.info("delete_unlinked_users: deleted %d user(s)", deleted_count)


def _find_unlinked_users() -> list:
    """Return non-superuser accounts without a UserTelegramProfile."""
    linked_user_ids = UserTelegramProfile.objects.values_list("user_id", flat=True)
    return list(User.objects.filter(is_superuser=False).exclude(pk__in=linked_user_ids))


def _delete_users(users: list) -> int:
    """Delete given users and return the count of deleted User rows."""
    pks = [u.pk for u in users]
    User.objects.filter(pk__in=pks).delete()
    return len(pks)
