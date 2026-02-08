"""Add Menu model and migrate MenuSlot from user FK to menu FK."""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def create_menus_for_existing_users(apps, schema_editor):
    """Create a default Menu for every user that has at least one MenuSlot."""
    Menu = apps.get_model("planner", "Menu")
    MenuSlot = apps.get_model("planner", "MenuSlot")

    user_ids = MenuSlot.objects.values_list("user", flat=True).distinct()
    for user_id in user_ids:
        menu = Menu.objects.create(
            user_id=user_id,
            name="Меню на неделю",
        )
        MenuSlot.objects.filter(user_id=user_id).update(menu=menu)


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("planner", "0003_add_can_edit_recipes_to_friendrequest"),
    ]

    operations = [
        migrations.CreateModel(
            name="Menu",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(default="Меню на неделю", max_length=200),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="menus",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.AddField(
            model_name="menuslot",
            name="menu",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="slots",
                to="planner.menu",
            ),
        ),
        migrations.RunPython(
            create_menus_for_existing_users,
            migrations.RunPython.noop,
        ),
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
