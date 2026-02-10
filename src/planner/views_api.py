"""DRF ViewSets and API views for planner API."""

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from planner.models import Ingredient, Menu, MenuSlot, Recipe, RecipeIngredient
from planner.permissions import (
    IsOwnerOrFriendEditorOrReadOnly,
    IsOwnerOrReadOnly,
    is_system_ingredient,
)
from planner.serializers import (
    IngredientSerializer,
    MenuItemSerializer,
    MenuSlotsSerializer,
    RecipeCreateUpdateSerializer,
    RecipeSerializer,
    ShoppingListRequestSerializer,
)
from planner.services import (
    calculate_shopping_list,
    calculate_shopping_list_for_user,
    get_or_create_first_menu,
)
from planner.services_friends import get_editable_owner_ids
from planner.services_import import IngredientImportError, import_ingredient_from_url

logger = logging.getLogger(__name__)


class IngredientViewSet(viewsets.ModelViewSet):
    serializer_class = IngredientSerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        return Ingredient.objects.select_related("user").order_by("name")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def partial_update(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.user_id != request.user.id:
            return Response(
                {"error": "Not allowed to delete this ingredient"},
                status=status.HTTP_403_FORBIDDEN,
            )
        if is_system_ingredient(instance):
            return Response(
                {"error": "Cannot delete system ingredient"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if RecipeIngredient.objects.filter(ingredient=instance).exists():
            return Response(
                {"error": "Ingredient is used in recipes"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.delete()
        return Response({"status": "ok"})


class IngredientImportView(APIView):
    """Import an ingredient from an external store URL (e.g. 5ka.ru)."""

    def post(self, request):
        url = (request.data or {}).get("url", "").strip()
        if not url:
            return Response(
                {"error": "Укажите ссылку на продукт"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            parsed = _parse_ingredient_from_url(url)
        except IngredientImportError as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if parsed is None:
            return Response(
                {"error": "Не удалось импортировать ингредиент"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return _save_imported_ingredient(request, parsed)


class RecipeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrFriendEditorOrReadOnly]

    def get_queryset(self):
        return (
            Recipe.objects.select_related("user")
            .prefetch_related("recipe_ingredients__ingredient")
            .order_by("name")
        )

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return RecipeCreateUpdateSerializer
        return RecipeSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        if self.request and self.request.user.is_authenticated:
            context["editable_owner_ids"] = get_editable_owner_ids(
                self.request.user
            )
        return context

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()
        out_serializer = RecipeSerializer(
            recipe, context=self.get_serializer_context()
        )
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()
        out_serializer = RecipeSerializer(
            Recipe.objects.prefetch_related("recipe_ingredients__ingredient").get(
                pk=recipe.pk
            ),
            context=self.get_serializer_context(),
        )
        return Response(out_serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({"status": "ok"})


class MenuListCreateView(APIView):
    """List all menus for the current user or create a new one."""

    def get(self, request):
        menus = Menu.objects.filter(user=request.user)
        serializer = MenuItemSerializer(menus, many=True)
        return Response(serializer.data)

    def post(self, request):
        name = (request.data or {}).get("name", "Меню на неделю")
        menu = Menu.objects.create(user=request.user, name=name)
        serializer = MenuItemSerializer(menu)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MenuDetailView(APIView):
    """Retrieve, update slots, rename, or delete a specific menu."""

    def get(self, request, menu_id):
        menu = get_object_or_404(Menu, pk=menu_id, user=request.user)
        serializer = MenuSlotsSerializer(instance=menu, context={"request": request})
        return Response(serializer.data)

    def put(self, request, menu_id):
        menu = get_object_or_404(Menu, pk=menu_id, user=request.user)
        body = request.data
        if not isinstance(body, dict):
            return Response(
                {"error": "Body must be an object"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _replace_menu_slots(menu, body)
        return Response({"status": "ok"})

    def patch(self, request, menu_id):
        menu = get_object_or_404(Menu, pk=menu_id, user=request.user)
        name = (request.data or {}).get("name")
        if name:
            menu.name = name
            menu.save(update_fields=["name"])
        serializer = MenuItemSerializer(menu)
        return Response(serializer.data)

    def delete(self, request, menu_id):
        menu = get_object_or_404(Menu, pk=menu_id, user=request.user)
        menu.delete()
        return Response({"status": "ok"})


class MenuSetPrimaryView(APIView):
    """Set a specific menu as the user's primary (visible to friends)."""

    def post(self, request, menu_id):
        menu = get_object_or_404(Menu, pk=menu_id, user=request.user)
        Menu.objects.filter(user=request.user, is_primary=True).update(is_primary=False)
        menu.is_primary = True
        menu.save(update_fields=["is_primary"])
        return Response({"status": "ok"})


class MenuView(APIView):
    """Legacy endpoint: operates on the user's first (oldest) menu."""

    def get(self, request):
        menu = get_or_create_first_menu(request.user)
        serializer = MenuSlotsSerializer(
            instance=menu, context={"request": request}
        )
        return Response(serializer.data)

    def put(self, request):
        body = request.data
        if not isinstance(body, dict):
            return Response(
                {"error": "Body must be an object"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        menu = get_or_create_first_menu(request.user)
        _replace_menu_slots(menu, body)
        return Response({"status": "ok"})


class ShoppingListView(APIView):
    """Generate shopping list. Accepts optional menu_id in body."""

    def post(self, request):
        serializer = ShoppingListRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        menu_id = request.data.get("menu_id")
        if menu_id:
            menu = get_object_or_404(Menu, pk=menu_id, user=request.user)
            result = calculate_shopping_list(
                menu,
                data["start_date"],
                data["end_date"],
                data.get("people_count", 2),
            )
        else:
            result = calculate_shopping_list_for_user(
                request.user,
                data["start_date"],
                data["end_date"],
                data.get("people_count", 2),
            )
        return Response(result)


def _parse_ingredient_from_url(url):
    """Call import service and handle errors, returning parsed data or None."""
    try:
        return import_ingredient_from_url(url)
    except IngredientImportError:
        raise
    except Exception:
        logger.exception("Unexpected error importing ingredient from %s", url)
        return None


def _save_imported_ingredient(request, parsed):
    """Validate and save parsed ingredient, returning serialized response."""
    data = {
        "name": parsed.name,
        "calories": parsed.calories,
        "protein": parsed.protein,
        "fat": parsed.fat,
        "carbs": parsed.carbs,
    }
    serializer = IngredientSerializer(data=data, context={"request": request})
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response(serializer.data, status=status.HTTP_201_CREATED)


def _replace_menu_slots(menu, body):
    """Delete existing slots and recreate from request body dict."""
    MenuSlot.objects.filter(menu=menu).delete()
    valid_recipe_ids = set(Recipe.objects.values_list("pk", flat=True))
    for key, recipe_id in body.items():
        if recipe_id is None:
            continue
        try:
            day_str, meal_str = key.split("-")
            day_of_week = int(day_str)
            meal_type = int(meal_str)
        except (ValueError, AttributeError):
            continue
        if day_of_week not in range(7) or meal_type not in range(4):
            continue
        if recipe_id not in valid_recipe_ids:
            continue
        MenuSlot.objects.create(
            menu=menu,
            day_of_week=day_of_week,
            meal_type=meal_type,
            recipe_id=recipe_id,
        )
