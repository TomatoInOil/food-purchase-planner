"""Add unique constraint for (menu, day_of_week, meal_type) on MenuSlot."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("planner", "0005_menuslot_replace_user_with_menu"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="menuslot",
            constraint=models.UniqueConstraint(
                fields=("menu", "day_of_week", "meal_type"),
                name="unique_menu_day_meal",
            ),
        ),
    ]
