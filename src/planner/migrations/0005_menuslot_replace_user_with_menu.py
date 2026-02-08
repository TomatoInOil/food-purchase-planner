"""Replace MenuSlot.user FK with non-nullable MenuSlot.menu FK.

Non-atomic: PostgreSQL raises 'pending trigger events' when AlterField
(nullable→non-null FK) drops and recreates the FK constraint within one
transaction.  With atomic=False each DDL statement auto-commits, so
deferred CREATE INDEX never sees pending events.
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    atomic = False

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
        migrations.AddConstraint(
            model_name="menuslot",
            constraint=models.UniqueConstraint(
                fields=("menu", "day_of_week", "meal_type"),
                name="unique_menu_day_meal",
            ),
        ),
    ]
