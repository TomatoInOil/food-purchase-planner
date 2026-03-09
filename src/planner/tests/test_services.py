"""Tests for planner domain services: menu slots, shopping list, friend services."""

from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase

from planner.models import (
    FriendRequest,
    Ingredient,
    Menu,
    MenuSlot,
    Recipe,
    RecipeIngredient,
)
from planner.services import (
    calculate_shopping_list,
    calculate_shopping_list_for_user,
    get_menu_for_user,
    get_menu_slots,
    get_or_create_first_menu,
)
from planner.services_friends import (
    can_friend_edit_menus,
    can_friend_edit_recipes,
    get_editable_owner_ids,
    get_friend_request_between,
    get_friend_user_or_404,
)

User = get_user_model()


class GetOrCreateFirstMenuTests(TestCase):
    """Test get_or_create_first_menu service function."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )

    def test_creates_menu_when_none_exists(self):
        self.assertEqual(Menu.objects.filter(user=self.user).count(), 0)
        menu = get_or_create_first_menu(self.user)
        self.assertIsNotNone(menu)
        self.assertEqual(menu.name, "Меню на неделю")
        self.assertEqual(menu.user, self.user)

    def test_returns_existing_first_menu(self):
        existing = Menu.objects.create(user=self.user, name="My Menu")
        Menu.objects.create(user=self.user, name="Second Menu")
        result = get_or_create_first_menu(self.user)
        self.assertEqual(result.pk, existing.pk)

    def test_does_not_create_duplicate(self):
        get_or_create_first_menu(self.user)
        get_or_create_first_menu(self.user)
        self.assertEqual(Menu.objects.filter(user=self.user).count(), 1)


class GetMenuSlotsTests(TestCase):
    """Test get_menu_slots service function."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.menu = Menu.objects.create(user=self.user, name="Test")
        self.recipe = Recipe.objects.create(
            user=self.user, name="Soup", description="", instructions=""
        )

    def test_empty_menu_returns_all_null_slots(self):
        data = get_menu_slots(self.menu)
        self.assertEqual(len(data), 28)
        for day in range(7):
            for meal in range(4):
                self.assertEqual(data[f"{day}-{meal}"], [])

    def test_filled_slots_returned_correctly(self):
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=0, meal_type=0, recipe=self.recipe
        )
        MenuSlot.objects.create(
            menu=self.menu, day_of_week=6, meal_type=3, recipe=self.recipe
        )
        data = get_menu_slots(self.menu)
        self.assertEqual(data["0-0"], [self.recipe.id])
        self.assertEqual(data["6-3"], [self.recipe.id])
        self.assertEqual(data["0-1"], [])

    def test_slot_with_null_recipe(self):
        MenuSlot.objects.create(menu=self.menu, day_of_week=1, meal_type=0, recipe=None)
        data = get_menu_slots(self.menu)
        self.assertEqual(data["1-0"], [])


class GetMenuForUserTests(TestCase):
    """Test get_menu_for_user backward-compatible wrapper."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )

    def test_creates_menu_and_returns_slots(self):
        data = get_menu_for_user(self.user)
        self.assertEqual(len(data), 28)
        self.assertTrue(Menu.objects.filter(user=self.user).exists())


class CalculateShoppingListTests(TestCase):
    """Test shopping list calculation logic."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.menu = Menu.objects.create(user=self.user, name="Test")
        self.ing_tomato = Ingredient.objects.create(
            user=self.user, name="Tomato", calories=18
        )
        self.ing_cheese = Ingredient.objects.create(
            user=self.user, name="Cheese", calories=300
        )
        self.recipe = Recipe.objects.create(
            user=self.user, name="Salad", description="", instructions=""
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing_tomato, weight_grams=200
        )
        RecipeIngredient.objects.create(
            recipe=self.recipe, ingredient=self.ing_cheese, weight_grams=50
        )

    def test_empty_menu_returns_empty_list(self):
        today = date.today()
        result = calculate_shopping_list(self.menu, today, today + timedelta(days=6))
        self.assertEqual(result, [])

    def test_single_day_single_meal(self):
        today = date.today()
        MenuSlot.objects.create(
            menu=self.menu,
            day_of_week=today.weekday(),
            meal_type=0,
            recipe=self.recipe,
        )
        result = calculate_shopping_list(self.menu, today, today, people_count=1)
        names = {item["name"] for item in result}
        self.assertEqual(names, {"Cheese", "Tomato"})
        tomato = next(i for i in result if i["name"] == "Tomato")
        self.assertEqual(tomato["weight_grams"], 200)

    def test_people_count_multiplier(self):
        today = date.today()
        MenuSlot.objects.create(
            menu=self.menu,
            day_of_week=today.weekday(),
            meal_type=0,
            recipe=self.recipe,
        )
        result = calculate_shopping_list(self.menu, today, today, people_count=3)
        tomato = next(i for i in result if i["name"] == "Tomato")
        self.assertEqual(tomato["weight_grams"], 600)

    def test_multiple_days_same_recipe_aggregates(self):
        today = date.today()
        tomorrow = today + timedelta(days=1)
        MenuSlot.objects.create(
            menu=self.menu,
            day_of_week=today.weekday(),
            meal_type=0,
            recipe=self.recipe,
        )
        MenuSlot.objects.create(
            menu=self.menu,
            day_of_week=tomorrow.weekday(),
            meal_type=0,
            recipe=self.recipe,
        )
        result = calculate_shopping_list(self.menu, today, tomorrow, people_count=1)
        tomato = next(i for i in result if i["name"] == "Tomato")
        self.assertEqual(tomato["weight_grams"], 400)

    def test_result_sorted_by_name(self):
        today = date.today()
        MenuSlot.objects.create(
            menu=self.menu,
            day_of_week=today.weekday(),
            meal_type=0,
            recipe=self.recipe,
        )
        result = calculate_shopping_list(self.menu, today, today, people_count=1)
        names = [item["name"] for item in result]
        self.assertEqual(names, sorted(names))

    def test_date_range_outside_menu_days_returns_empty(self):
        today = date.today()
        MenuSlot.objects.create(
            menu=self.menu,
            day_of_week=(today.weekday() + 3) % 7,
            meal_type=0,
            recipe=self.recipe,
        )
        result = calculate_shopping_list(self.menu, today, today, people_count=1)
        self.assertEqual(result, [])

    def test_multiple_meals_same_day(self):
        today = date.today()
        MenuSlot.objects.create(
            menu=self.menu,
            day_of_week=today.weekday(),
            meal_type=0,
            recipe=self.recipe,
        )
        MenuSlot.objects.create(
            menu=self.menu,
            day_of_week=today.weekday(),
            meal_type=3,
            recipe=self.recipe,
        )
        result = calculate_shopping_list(self.menu, today, today, people_count=1)
        tomato = next(i for i in result if i["name"] == "Tomato")
        self.assertEqual(tomato["weight_grams"], 400)


class CalculateShoppingListForUserTests(TestCase):
    """Test the backward-compatible wrapper."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )

    def test_creates_menu_and_returns_empty_list(self):
        today = date.today()
        result = calculate_shopping_list_for_user(
            self.user, today, today + timedelta(days=6)
        )
        self.assertEqual(result, [])
        self.assertTrue(Menu.objects.filter(user=self.user).exists())


class GetFriendUserOr404Tests(TestCase):
    """Test get_friend_user_or_404 service function."""

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.bob = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )

    def test_returns_friend_when_from_user(self):
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        result = get_friend_user_or_404(self.alice, self.bob.id)
        self.assertEqual(result, self.bob)

    def test_returns_friend_when_to_user(self):
        FriendRequest.objects.create(
            from_user=self.bob,
            to_user=self.alice,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        result = get_friend_user_or_404(self.alice, self.bob.id)
        self.assertEqual(result, self.bob)

    def test_raises_validation_error_when_not_friends(self):
        from rest_framework.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            get_friend_user_or_404(self.alice, self.bob.id)

    def test_raises_error_when_friendship_not_accepted(self):
        from rest_framework.exceptions import ValidationError

        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_PENDING,
        )
        with self.assertRaises(ValidationError):
            get_friend_user_or_404(self.alice, self.bob.id)


class GetEditableOwnerIdsTests(TestCase):
    """Test get_editable_owner_ids batch lookup."""

    def setUp(self):
        self.editor = User.objects.create_user(
            username="editor", password="pass", email="editor@test.com"
        )
        self.owner_a = User.objects.create_user(
            username="owner_a", password="pass", email="a@test.com"
        )
        self.owner_b = User.objects.create_user(
            username="owner_b", password="pass", email="b@test.com"
        )
        self.stranger = User.objects.create_user(
            username="stranger", password="pass", email="stranger@test.com"
        )

    def test_returns_empty_set_when_no_friends(self):
        result = get_editable_owner_ids(self.editor)
        self.assertEqual(result, set())

    def test_returns_friend_ids_with_edit_accepted(self):
        FriendRequest.objects.create(
            from_user=self.editor,
            to_user=self.owner_a,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
        )
        FriendRequest.objects.create(
            from_user=self.owner_b,
            to_user=self.editor,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
        )
        result = get_editable_owner_ids(self.editor)
        self.assertEqual(result, {self.owner_a.id, self.owner_b.id})

    def test_excludes_pending_edit_status(self):
        FriendRequest.objects.create(
            from_user=self.editor,
            to_user=self.owner_a,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_PENDING,
        )
        result = get_editable_owner_ids(self.editor)
        self.assertEqual(result, set())

    def test_excludes_non_accepted_friendship(self):
        FriendRequest.objects.create(
            from_user=self.editor,
            to_user=self.owner_a,
            status=FriendRequest.STATUS_PENDING,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
        )
        result = get_editable_owner_ids(self.editor)
        self.assertEqual(result, set())

    def test_excludes_stranger(self):
        FriendRequest.objects.create(
            from_user=self.editor,
            to_user=self.owner_a,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
        )
        result = get_editable_owner_ids(self.editor)
        self.assertNotIn(self.stranger.id, result)


class CanFriendEditRecipesTests(TestCase):
    """Test can_friend_edit_recipes permission check."""

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.bob = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )

    def test_true_when_accepted_and_edit_accepted(self):
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
        )
        self.assertTrue(can_friend_edit_recipes(self.alice, self.bob))

    def test_bidirectional(self):
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
        )
        self.assertTrue(can_friend_edit_recipes(self.bob, self.alice))

    def test_false_when_edit_pending(self):
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_PENDING,
        )
        self.assertFalse(can_friend_edit_recipes(self.alice, self.bob))

    def test_false_when_edit_none(self):
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_NONE,
        )
        self.assertFalse(can_friend_edit_recipes(self.alice, self.bob))

    def test_false_when_not_friends(self):
        self.assertFalse(can_friend_edit_recipes(self.alice, self.bob))

    def test_false_when_friendship_not_accepted(self):
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_PENDING,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
        )
        self.assertFalse(can_friend_edit_recipes(self.alice, self.bob))


class CanFriendEditMenusTests(TestCase):
    """Test can_friend_edit_menus permission check (shares same flag as recipes)."""

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.bob = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )

    def test_true_when_accepted(self):
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
        )
        self.assertTrue(can_friend_edit_menus(self.alice, self.bob))

    def test_false_when_none(self):
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
            can_edit_recipes_status=FriendRequest.EDIT_RECIPES_NONE,
        )
        self.assertFalse(can_friend_edit_menus(self.alice, self.bob))


class GetFriendRequestBetweenTests(TestCase):
    """Test get_friend_request_between helper."""

    def setUp(self):
        self.alice = User.objects.create_user(
            username="alice", password="pass", email="alice@test.com"
        )
        self.bob = User.objects.create_user(
            username="bob", password="pass", email="bob@test.com"
        )

    def test_returns_accepted_request(self):
        fr = FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        result = get_friend_request_between(self.alice, self.bob)
        self.assertEqual(result.pk, fr.pk)

    def test_returns_request_in_reverse_direction(self):
        fr = FriendRequest.objects.create(
            from_user=self.bob,
            to_user=self.alice,
            status=FriendRequest.STATUS_ACCEPTED,
        )
        result = get_friend_request_between(self.alice, self.bob)
        self.assertEqual(result.pk, fr.pk)

    def test_returns_none_when_not_accepted(self):
        FriendRequest.objects.create(
            from_user=self.alice,
            to_user=self.bob,
            status=FriendRequest.STATUS_PENDING,
        )
        result = get_friend_request_between(self.alice, self.bob)
        self.assertIsNone(result)

    def test_returns_none_when_no_request(self):
        result = get_friend_request_between(self.alice, self.bob)
        self.assertIsNone(result)
