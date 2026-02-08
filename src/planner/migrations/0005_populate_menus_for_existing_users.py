"""Populate Menu records for existing users."""

from django.db import migrations


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
        ("planner", "0004_add_menu_model"),
    ]

    operations = [
        migrations.RunPython(
            create_menus_for_existing_users,
            migrations.RunPython.noop,
        ),
    ]
