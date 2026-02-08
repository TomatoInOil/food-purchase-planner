"""Drop old user FK and constraint, make menu FK non-nullable."""

import django.db.models.deletion
from django.db import migrations, models


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
