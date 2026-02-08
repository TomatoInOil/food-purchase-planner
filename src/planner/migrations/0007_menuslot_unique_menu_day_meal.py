"""Add unique constraint for (menu, day_of_week, meal_type) on MenuSlot."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("planner", "0006_menuslot_menu_not_null"),
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
