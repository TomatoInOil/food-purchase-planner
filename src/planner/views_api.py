"""DRF ViewSets and API views for planner API."""

from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from planner.models import Ingredient, MenuSlot, Recipe, RecipeIngredient
from planner.services import calculate_shopping_list_for_user
from planner.permissions import (
    IsOwnerOrFriendEditorOrReadOnly,
    IsOwnerOrReadOnly,
    is_system_ingredient,
)
from planner.serializers import (
    IngredientSerializer,
    MenuSerializer,
    RecipeCreateUpdateSerializer,
    RecipeSerializer,
    ShoppingListRequestSerializer,
)


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
        return context

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        recipe = serializer.save()
        out_serializer = RecipeSerializer(recipe, context={"request": request})
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
            context={"request": request},
        )
        return Response(out_serializer.data)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.delete()
        return Response({"status": "ok"})


class MenuView(APIView):
    def get(self, request):
        serializer = MenuSerializer(instance=request.user, context={"request": request})
        return Response(serializer.data)

    def put(self, request):
        body = request.data
        if not isinstance(body, dict):
            return Response(
                {"error": "Body must be an object"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user = request.user
        MenuSlot.objects.filter(user=user).delete()
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
                user=user,
                day_of_week=day_of_week,
                meal_type=meal_type,
                recipe_id=recipe_id,
            )
        return Response({"status": "ok"})


class ShoppingListView(APIView):
    def post(self, request):
        serializer = ShoppingListRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        result = calculate_shopping_list_for_user(
            request.user,
            data["start_date"],
            data["end_date"],
            data.get("people_count", 2),
        )
        return Response(result)
