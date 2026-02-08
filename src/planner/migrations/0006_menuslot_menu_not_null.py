"""Make MenuSlot.menu FK non-nullable and update ordering."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("planner", "0005_menuslot_replace_user_with_menu"),
    ]

    operations = [
        migrations.AlterField(
            model_name="menuslot",
            name="menu",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="slots",
                to="planner.menu",
            ),
        ),
        migrations.AlterModelOptions(
            name="menuslot",
            options={"ordering": ["menu", "day_of_week", "meal_type"]},
        ),
    ]
