"""Domain services for menu and shopping list calculations."""

import logging
from datetime import timedelta

from django.db import models

from planner.models import (
    Menu,
    MenuShare,
    MenuSlot,
    MenuSlotAssignment,
    RecipeIngredient,
    UserActiveMenu,
)

logger = logging.getLogger(__name__)


def get_active_menu(user):
    """Return the user's active menu, falling back to their first own menu.

    Validates that the stored active menu is still accessible (owned or shared).
    """
    setting = UserActiveMenu.objects.filter(user=user).select_related("menu").first()
    if setting and setting.menu:
        menu = setting.menu
        if menu.user_id == user.id or menu.shares.filter(shared_with=user).exists():
            return menu
    return get_or_create_first_menu(user)


def set_active_menu(user, menu):
    """Set a menu as the user's active menu. Menu must be owned or shared."""
    if menu.user_id != user.id and not menu.shares.filter(shared_with=user).exists():
        from rest_framework.exceptions import ValidationError

        raise ValidationError("Нет доступа к этому меню")
    UserActiveMenu.objects.update_or_create(user=user, defaults={"menu": menu})


def share_menu(menu, shared_with_user, permission):
    """Share a menu with a friend. Validates friendship exists."""
    from planner.services_friends import get_friend_request_between

    if menu.user_id == shared_with_user.id:
        from rest_framework.exceptions import ValidationError

        raise ValidationError("Нельзя поделиться меню с самим собой")

    fr = get_friend_request_between(menu.user, shared_with_user)
    if not fr:
        from rest_framework.exceptions import ValidationError

        raise ValidationError("Пользователь не является вашим другом")

    share, created = MenuShare.objects.update_or_create(
        menu=menu,
        shared_with=shared_with_user,
        defaults={"permission": permission},
    )
    return share


def revoke_menu_share(share):
    """Remove a menu share. If the user had it as active, reset to their own menu."""
    user = share.shared_with
    menu = share.menu
    share.delete()
    setting = UserActiveMenu.objects.filter(user=user, menu=menu).first()
    if setting:
        setting.menu = get_or_create_first_menu(user)
        setting.save(update_fields=["menu"])


def get_menu_participants_count(menu):
    """Return the number of people using this menu (owner + shared users)."""
    return 1 + menu.shares.count()


def get_menu_members(menu):
    """Return list of menu members (owner + editors) as [{id, username}, ...]."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    owner = User.objects.filter(pk=menu.user_id).values("id", "username").first()
    members = [owner] if owner else []
    editor_shares = menu.shares.filter(
        permission=MenuShare.PERMISSION_EDIT
    ).select_related("shared_with")
    for share in editor_shares:
        members.append(
            {"id": share.shared_with.id, "username": share.shared_with.username}
        )
    return members


def get_or_create_first_menu(user):
    """Return the user's first (oldest) menu, creating a default one if none exists."""
    menu = Menu.objects.filter(user=user).first()
    if not menu:
        menu = Menu.objects.create(user=user, name="Меню на неделю")
        logger.info("Created default menu for user_id=%s", user.pk)
    return menu


def get_menu_slots(menu):
    """
    Build menu dict from MenuSlot for the given Menu.
    Returns {"day-meal": [{"recipe_id": int, "servings": int}, ...]} with [] for empty slots.
    """
    slots = MenuSlot.objects.filter(menu=menu)
    data: dict[str, list[dict]] = {}
    for s in slots:
        key = f"{s.day_of_week}-{s.meal_type}"
        if s.recipe_id is not None:
            data.setdefault(key, []).append(
                {"recipe_id": s.recipe_id, "servings": s.servings}
            )
    for day in range(7):
        for meal in range(4):
            key = f"{day}-{meal}"
            if key not in data:
                data[key] = []
    return data


def get_menu_for_user(user):
    """
    Build menu dict for the user's first menu.
    Backward-compatible wrapper around get_menu_slots.
    """
    menu = get_or_create_first_menu(user)
    return get_menu_slots(menu)


def duplicate_menu(menu):
    """Create a copy of the menu with all its slots, shares, and assignments."""
    new_menu = Menu.objects.create(
        user=menu.user,
        name=f"{menu.name} — копия",
    )
    for share in menu.shares.all():
        MenuShare.objects.create(
            menu=new_menu,
            shared_with=share.shared_with,
            permission=share.permission,
        )
    old_slots = MenuSlot.objects.filter(menu=menu).prefetch_related("assignments")
    for old_slot in old_slots:
        new_slot = MenuSlot.objects.create(
            menu=new_menu,
            day_of_week=old_slot.day_of_week,
            meal_type=old_slot.meal_type,
            recipe=old_slot.recipe,
            servings=old_slot.servings,
        )
        old_assignments = list(old_slot.assignments.all())
        if old_assignments:
            MenuSlotAssignment.objects.bulk_create(
                [
                    MenuSlotAssignment(menu_slot=new_slot, user=a.user)
                    for a in old_assignments
                ]
            )
    return new_menu


def calculate_shopping_list(menu, start_date, end_date, people_count=2):
    """
    Compute aggregated shopping list for a specific menu over the date range.
    Returns list of {"name": str, "weight_grams": int} sorted by name.
    """
    slots_by_day_meal: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for s in MenuSlot.objects.filter(menu=menu):
        if s.recipe_id is not None:
            slots_by_day_meal.setdefault((s.day_of_week, s.meal_type), []).append(
                (s.recipe_id, s.servings)
            )
    aggregated = _aggregate_ingredients(slots_by_day_meal, start_date, end_date)
    result = _build_shopping_result(aggregated, people_count)
    logger.info(
        "Shopping list for menu_id=%s (%s — %s, people=%d): %d items",
        menu.pk,
        start_date,
        end_date,
        people_count,
        len(result),
    )
    return result


def calculate_shopping_list_for_user(user, start_date, end_date, people_count=2):
    """
    Compute shopping list for the user's active menu.
    Backward-compatible wrapper around calculate_shopping_list.
    """
    menu = get_active_menu(user)
    return calculate_shopping_list(menu, start_date, end_date, people_count)


def get_menu_with_access(menu_id, user, require_edit=False):
    """Return a Menu if the user has access, or None.

    When require_edit=True, shared menus require edit permission.
    """
    menu = Menu.objects.filter(pk=menu_id).first()
    if not menu:
        return None
    if menu.user_id == user.id:
        return menu
    share = menu.shares.filter(shared_with=user).first()
    if not share:
        return None
    if require_edit and share.permission != MenuShare.PERMISSION_EDIT:
        return None
    return menu


def revoke_all_shares_between(user_a, user_b):
    """Remove all menu shares between two users (both directions)."""
    shares = MenuShare.objects.filter(
        models.Q(menu__user=user_a, shared_with=user_b)
        | models.Q(menu__user=user_b, shared_with=user_a)
    )
    for share in shares:
        revoke_menu_share(share)


def _aggregate_ingredients(slots_by_day_meal, start_date, end_date):
    """Walk date range and collect ingredient weights from recipe slots."""
    aggregated = {}
    current = start_date
    while current <= end_date:
        day_of_week = current.weekday()
        for meal_type in range(4):
            recipe_entries = slots_by_day_meal.get((day_of_week, meal_type), [])
            for recipe_id, servings in recipe_entries:
                for ri in RecipeIngredient.objects.filter(
                    recipe_id=recipe_id
                ).select_related("ingredient"):
                    ing_id = ri.ingredient_id
                    if ing_id not in aggregated:
                        aggregated[ing_id] = {
                            "name": ri.ingredient.name,
                            "weight_grams": 0,
                        }
                    aggregated[ing_id]["weight_grams"] += ri.weight_grams * servings
        current += timedelta(days=1)
    return aggregated


def _build_shopping_result(aggregated, people_count):
    """Format aggregated ingredients into sorted list with people multiplier."""
    result = [
        {"name": v["name"], "weight_grams": round(v["weight_grams"] * people_count)}
        for v in aggregated.values()
    ]
    result.sort(key=lambda x: x["name"])
    return result
