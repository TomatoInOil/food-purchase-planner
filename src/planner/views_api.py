"""DRF ViewSets and API views for planner API."""

import logging

from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from django.contrib.auth import get_user_model

from planner.models import (
    Ingredient,
    Menu,
    MenuSlot,
    Recipe,
    RecipeCategory,
    RecipeIngredient,
)
from planner.permissions import (
    IsOwnerOrFriendEditorOrReadOnly,
    IsOwnerOrReadOnly,
    is_system_ingredient,
)
from planner.serializers import (
    IngredientSerializer,
    MenuItemSerializer,
    MenuShareSerializer,
    MenuSlotsSerializer,
    RecipeCategorySerializer,
    RecipeCreateUpdateSerializer,
    RecipeSerializer,
    ShoppingListRequestSerializer,
)
from planner.services import (
    calculate_shopping_list,
    calculate_shopping_list_for_user,
    duplicate_menu,
    get_menu_with_access,
    get_or_create_first_menu,
    revoke_menu_share,
    set_active_menu,
    share_menu,
)
from planner.services_friends import get_editable_owner_ids
from planner.services_import import (
    MAX_CONTENT_SIZE,
    IngredientImportError,
    parse_ingredient_from_text,
)

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
        ingredient = serializer.save()
        logger.info(
            "Ingredient created: id=%s name=%r by user_id=%s",
            ingredient.pk,
            ingredient.name,
            request.user.pk,
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def retrieve(self, request, *args, **kwargs):
        return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if is_system_ingredient(instance):
            return Response(
                {"error": "Cannot update system ingredient"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(instance, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(
            "Ingredient updated: id=%s name=%r by user_id=%s",
            instance.pk,
            instance.name,
            request.user.pk,
        )
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        if is_system_ingredient(instance):
            return Response(
                {"error": "Cannot update system ingredient"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        logger.info(
            "Ingredient patched: id=%s name=%r by user_id=%s",
            instance.pk,
            instance.name,
            request.user.pk,
        )
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
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
        logger.info(
            "Ingredient deleted: id=%s name=%r by user_id=%s",
            instance.pk,
            instance.name,
            request.user.pk,
        )
        instance.delete()
        return Response({"status": "ok"})


class IngredientImportFromContentView(APIView):
    """Import an ingredient from pasted page content (e.g. 5ka.ru Ctrl+A copy)."""

    def post(self, request):
        data = request.data or {}
        content = (data.get("content") or "").strip()

        if not content:
            return Response(
                {"error": "Вставьте скопированное содержимое страницы продукта."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(content) > MAX_CONTENT_SIZE:
            return Response(
                {"error": "Содержимое слишком большое."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            parsed = parse_ingredient_from_text(content)
        except IngredientImportError as exc:
            logger.warning(
                "Ingredient import failed for user_id=%s: %s", request.user.pk, exc
            )
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(
            "Ingredient imported from content: name=%r by user_id=%s",
            parsed.name,
            request.user.pk,
        )
        return _save_imported_ingredient(request, parsed)


class RecipeCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = RecipeCategorySerializer
    permission_classes = [IsOwnerOrReadOnly]

    def get_queryset(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        system_user = User.objects.filter(username="system").first()
        user_ids = [self.request.user.id]
        if system_user:
            user_ids.append(system_user.id)
        return RecipeCategory.objects.filter(user_id__in=user_ids).order_by("name")

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if instance.recipes.exists():
            return Response(
                {"error": "Category is used by recipes"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        instance.delete()
        return Response({"status": "ok"})


class RecipeViewSet(viewsets.ModelViewSet):
    permission_classes = [IsOwnerOrFriendEditorOrReadOnly]

    def get_queryset(self):
        return (
            Recipe.objects.select_related("user", "category")
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
            context["editable_owner_ids"] = get_editable_owner_ids(self.request.user)
        return context

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        category_param = request.query_params.get("category")
        if category_param is not None:
            if category_param == "none":
                queryset = queryset.filter(category__isnull=True)
            else:
                queryset = queryset.filter(category_id=category_param)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()
        logger.info(
            "Recipe created: id=%s name=%r by user_id=%s",
            recipe.pk,
            recipe.name,
            request.user.pk,
        )
        out_serializer = RecipeSerializer(recipe, context=self.get_serializer_context())
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
        logger.info(
            "Recipe deleted: id=%s name=%r by user_id=%s",
            instance.pk,
            instance.name,
            request.user.pk,
        )
        instance.delete()
        return Response({"status": "ok"})


class MenuListCreateView(APIView):
    """List own + shared menus for the current user, or create a new one."""

    def get(self, request):
        own = Menu.objects.filter(user=request.user).select_related("user")
        shared = Menu.objects.filter(shares__shared_with=request.user).select_related(
            "user"
        )
        menus = list(own) + list(shared)
        serializer = MenuItemSerializer(menus, many=True, context={"request": request})
        return Response(serializer.data)

    def post(self, request):
        name = (request.data or {}).get("name", "Меню на неделю")
        menu = Menu.objects.create(user=request.user, name=name)
        logger.info(
            "Menu created: id=%s name=%r by user_id=%s",
            menu.pk,
            menu.name,
            request.user.pk,
        )
        serializer = MenuItemSerializer(menu, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MenuDetailView(APIView):
    """Retrieve, update slots, rename, or delete a specific menu."""

    def get(self, request, menu_id):
        menu = get_menu_with_access(menu_id, request.user)
        if not menu:
            return Response(status=status.HTTP_404_NOT_FOUND)
        serializer = MenuSlotsSerializer(instance=menu, context={"request": request})
        return Response(serializer.data)

    def put(self, request, menu_id):
        menu = get_menu_with_access(menu_id, request.user, require_edit=True)
        if not menu:
            return Response(status=status.HTTP_403_FORBIDDEN)
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
        serializer = MenuItemSerializer(menu, context={"request": request})
        return Response(serializer.data)

    def delete(self, request, menu_id):
        menu = get_object_or_404(Menu, pk=menu_id, user=request.user)
        logger.info("Menu deleted: id=%s by user_id=%s", menu.pk, request.user.pk)
        menu.delete()
        return Response({"status": "ok"})


class MenuSetActiveView(APIView):
    """Set a menu as the user's active menu (own or shared)."""

    def post(self, request, menu_id):
        menu = get_menu_with_access(menu_id, request.user)
        if not menu:
            return Response(status=status.HTTP_404_NOT_FOUND)
        set_active_menu(request.user, menu)
        return Response({"status": "ok"})


class MenuShareListCreateView(APIView):
    """List or create shares for a menu (owner only)."""

    def get(self, request, menu_id):
        menu = get_object_or_404(Menu, pk=menu_id, user=request.user)
        shares = menu.shares.select_related("shared_with").all()
        serializer = MenuShareSerializer(shares, many=True)
        return Response(serializer.data)

    def post(self, request, menu_id):
        menu = get_object_or_404(Menu, pk=menu_id, user=request.user)
        user_id = request.data.get("user_id")
        permission = request.data.get("permission", "read")
        if not user_id:
            return Response(
                {"error": "user_id обязателен"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        User = get_user_model()
        try:
            target_user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "Пользователь не найден"},
                status=status.HTTP_404_NOT_FOUND,
            )
        share = share_menu(menu, target_user, permission)
        serializer = MenuShareSerializer(share)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MenuShareDetailView(APIView):
    """Update permission or revoke a menu share."""

    def patch(self, request, menu_id, share_id):
        menu = get_object_or_404(Menu, pk=menu_id, user=request.user)
        share = get_object_or_404(menu.shares, pk=share_id)
        permission = request.data.get("permission")
        if permission:
            share.permission = permission
            share.save(update_fields=["permission"])
        serializer = MenuShareSerializer(share)
        return Response(serializer.data)

    def delete(self, request, menu_id, share_id):
        menu = get_object_or_404(Menu, pk=menu_id)
        share = get_object_or_404(menu.shares, pk=share_id)
        if menu.user_id != request.user.id and share.shared_with_id != request.user.id:
            return Response(status=status.HTTP_403_FORBIDDEN)
        revoke_menu_share(share)
        return Response({"status": "ok"})


class MenuDuplicateView(APIView):
    """Duplicate a menu with all its slots."""

    def post(self, request, menu_id):
        menu = get_object_or_404(Menu, pk=menu_id, user=request.user)
        new_menu = duplicate_menu(menu)
        logger.info(
            "Menu duplicated: id=%s -> id=%s by user_id=%s",
            menu.pk,
            new_menu.pk,
            request.user.pk,
        )
        serializer = MenuItemSerializer(new_menu, context={"request": request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MenuView(APIView):
    """Legacy endpoint: operates on the user's first (oldest) menu."""

    def get(self, request):
        menu = get_or_create_first_menu(request.user)
        serializer = MenuSlotsSerializer(instance=menu, context={"request": request})
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
            menu = get_menu_with_access(menu_id, request.user)
            if not menu:
                return Response(status=status.HTTP_404_NOT_FOUND)
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
    """Delete existing slots and recreate from request body dict.

    Supports three value formats per slot key:
    - New: [{"recipe_id": int, "servings": int}, ...]
    - Legacy list: [int, ...]
    - Legacy single: int
    """
    MenuSlot.objects.filter(menu=menu).delete()
    valid_recipe_ids = set(Recipe.objects.values_list("pk", flat=True))
    for key, value in body.items():
        try:
            day_str, meal_str = key.split("-")
            day_of_week = int(day_str)
            meal_type = int(meal_str)
        except (ValueError, AttributeError):
            continue
        if day_of_week not in range(7) or meal_type not in range(4):
            continue
        items = value if isinstance(value, list) else [value]
        for item in items:
            if item is None:
                continue
            if isinstance(item, dict):
                recipe_id = item.get("recipe_id")
                servings = item.get("servings", 1)
            else:
                recipe_id = item
                servings = 1
            if recipe_id is None or recipe_id not in valid_recipe_ids:
                continue
            MenuSlot.objects.create(
                menu=menu,
                day_of_week=day_of_week,
                meal_type=meal_type,
                recipe_id=recipe_id,
                servings=max(1, int(servings)),
            )
