"""Drop old unique constraint and user FK from MenuSlot."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("planner", "0004_add_menu_model"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="menuslot",
            name="unique_user_day_meal",
        ),
        migrations.RemoveField(
            model_name="menuslot",
            name="user",
        ),
    ]
