"""DRF serializers matching the existing API response contract."""

from datetime import datetime

from rest_framework import serializers

from planner.models import (
    FriendRequest,
    Ingredient,
    Menu,
    MenuSlot,
    Recipe,
    RecipeIngredient,
    UserFriendCode,
)


class IngredientSerializer(serializers.ModelSerializer):
    is_owner = serializers.SerializerMethodField()

    class Meta:
        model = Ingredient
        fields = ["id", "name", "calories", "protein", "fat", "carbs", "is_owner"]

    def get_is_owner(self, obj):
        request = self.context.get("request")
        return request and request.user.id == obj.user_id

    def validate_name(self, value):
        value = (value or "").strip()
        if not value:
            raise serializers.ValidationError("name is required")
        user = self.context["request"].user
        qs = Ingredient.objects.filter(user=user, name=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Ingredient with this name already exists"
            )
        return value

    def validate_calories(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError("calories must be a number")

    def validate_protein(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError("protein must be a number")

    def validate_fat(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError("fat must be a number")

    def validate_carbs(self, value):
        try:
            return float(value)
        except (TypeError, ValueError):
            raise serializers.ValidationError("carbs must be a number")

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class RecipeIngredientReadSerializer(serializers.Serializer):
    ingredient_id = serializers.IntegerField(read_only=True)
    ingredient_name = serializers.CharField(read_only=True)
    weight_grams = serializers.IntegerField(read_only=True)


class RecipeIngredientWriteSerializer(serializers.Serializer):
    ingredient_id = serializers.IntegerField()
    weight_grams = serializers.IntegerField(min_value=1)


class RecipeSerializer(serializers.ModelSerializer):
    is_owner = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    author_username = serializers.SerializerMethodField()
    ingredients = RecipeIngredientReadSerializer(many=True, read_only=True)
    total_calories = serializers.FloatField(read_only=True, default=0)
    total_protein = serializers.FloatField(read_only=True, default=0)
    total_fat = serializers.FloatField(read_only=True, default=0)
    total_carbs = serializers.FloatField(read_only=True, default=0)

    class Meta:
        model = Recipe
        fields = [
            "id",
            "name",
            "description",
            "instructions",
            "total_calories",
            "total_protein",
            "total_fat",
            "total_carbs",
            "is_owner",
            "can_edit",
            "ingredients",
            "author_username",
        ]

    def get_is_owner(self, obj):
        request = self.context.get("request")
        return request and request.user.id == obj.user_id

    def get_can_edit(self, obj):
        """Return True if the current user is the owner or a friend with edit permission.

        Uses a pre-computed set of owner IDs from the serializer context to
        avoid an extra DB query per recipe (N+1 prevention).
        """
        request = self.context.get("request")
        if not request:
            return False
        if request.user.id == obj.user_id:
            return True
        editable_owner_ids = self.context.get("editable_owner_ids")
        if editable_owner_ids is not None:
            return obj.user_id in editable_owner_ids
        from planner.services_friends import can_friend_edit_recipes

        return can_friend_edit_recipes(request.user, obj.user)

    def get_author_username(self, obj):
        return obj.user.username if obj.user_id else ""

    def _get_ingredients_list(self, recipe):
        return [
            {
                "ingredient_id": ri.ingredient_id,
                "ingredient_name": ri.ingredient.name,
                "weight_grams": ri.weight_grams,
            }
            for ri in recipe.recipe_ingredients.all()
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["description"] = data.get("description") or ""
        data["instructions"] = data.get("instructions") or ""
        data["total_calories"] = instance.total_calories or 0
        data["total_protein"] = instance.total_protein or 0
        data["total_fat"] = instance.total_fat or 0
        data["total_carbs"] = instance.total_carbs or 0
        data["ingredients"] = self._get_ingredients_list(instance)
        return data

    def validate_ingredients(self, value):
        if not value:
            raise serializers.ValidationError("At least one ingredient is required")
        for item in value:
            if item.get("ingredient_id") is None or item.get("weight_grams") is None:
                raise serializers.ValidationError(
                    "Each ingredient must have ingredient_id and weight_grams"
                )
        return value

    def create(self, validated_data):
        ingredients_data = validated_data.pop("ingredients", [])
        validated_data["user"] = self.context["request"].user
        recipe = Recipe.objects.create(
            name=validated_data["name"],
            description=validated_data.get("description", ""),
            instructions=validated_data.get("instructions", ""),
            user=validated_data["user"],
        )
        self._set_recipe_ingredients(recipe, ingredients_data)
        recipe.recalculate_nutrition()
        recipe.save()
        return recipe

    def update(self, instance, validated_data):
        ingredients_data = validated_data.pop("ingredients", [])
        instance.name = validated_data.get("name", instance.name)
        instance.description = validated_data.get("description", instance.description)
        instance.instructions = validated_data.get(
            "instructions", instance.instructions
        )
        instance.save()
        RecipeIngredient.objects.filter(recipe=instance).delete()
        self._set_recipe_ingredients(instance, ingredients_data)
        instance.recalculate_nutrition()
        instance.save()
        return instance

    def _set_recipe_ingredients(self, recipe, ingredients_data):
        for item in ingredients_data:
            ing_id = item["ingredient_id"]
            weight_grams = item["weight_grams"]
            try:
                ingredient = Ingredient.objects.get(pk=ing_id)
            except Ingredient.DoesNotExist:
                raise serializers.ValidationError(f"Ingredient id {ing_id} not found")
            RecipeIngredient.objects.create(
                recipe=recipe,
                ingredient=ingredient,
                weight_grams=weight_grams,
            )


class RecipeCreateUpdateSerializer(RecipeSerializer):
    ingredients = RecipeIngredientWriteSerializer(many=True)  # type: ignore[assignment]

    class Meta(RecipeSerializer.Meta):
        fields = RecipeSerializer.Meta.fields


class MenuItemSerializer(serializers.ModelSerializer):
    """Serializer for menu list items (id, name, created_at)."""

    class Meta:
        model = Menu
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]


def _menu_slot_key(day_of_week, meal_type):
    return f"{day_of_week}-{meal_type}"


class MenuSlotsSerializer(serializers.Serializer):
    """Read-only: represents a Menu's slots as {day-meal: recipe_id}."""

    def to_representation(self, instance):
        slots = MenuSlot.objects.filter(menu=instance).select_related("recipe")
        data = {f"{s.day_of_week}-{s.meal_type}": s.recipe_id for s in slots}
        for day in range(7):
            for meal in range(4):
                key = _menu_slot_key(day, meal)
                if key not in data:
                    data[key] = None
        return data


class ShoppingListRequestSerializer(serializers.Serializer):
    start_date = serializers.CharField()
    end_date = serializers.CharField()
    people_count = serializers.IntegerField(
        required=False, default=2, min_value=1, max_value=20
    )

    def validate_start_date(self, value):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise serializers.ValidationError("Invalid date format, use YYYY-MM-DD")

    def validate_end_date(self, value):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            raise serializers.ValidationError("Invalid date format, use YYYY-MM-DD")

    def validate(self, attrs):
        if attrs["start_date"] > attrs["end_date"]:
            raise serializers.ValidationError(
                "start_date must be before or equal to end_date"
            )
        return attrs


class UserFriendCodeSerializer(serializers.ModelSerializer):
    """Read-only serializer exposing the current user's friend code."""

    class Meta:
        model = UserFriendCode
        fields = ["code"]
        read_only_fields = ["code"]


class FriendRequestSerializer(serializers.ModelSerializer):
    """Serializer for friend request objects including user ids and usernames."""

    from_user_id = serializers.IntegerField(source="from_user.id", read_only=True)
    to_user_id = serializers.IntegerField(source="to_user.id", read_only=True)
    from_username = serializers.SerializerMethodField()
    to_username = serializers.SerializerMethodField()

    class Meta:
        model = FriendRequest
        fields = [
            "id",
            "from_user_id",
            "to_user_id",
            "from_username",
            "to_username",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "from_user_id",
            "to_user_id",
            "from_username",
            "to_username",
            "status",
            "created_at",
        ]

    def get_from_username(self, obj):
        return obj.from_user.username

    def get_to_username(self, obj):
        return obj.to_user.username


class FriendSerializer(serializers.Serializer):
    """Serializer for derived friend objects built from accepted friend requests."""

    user_id = serializers.IntegerField()
    username = serializers.CharField()
    friend_request_id = serializers.IntegerField()
    since = serializers.DateTimeField()
    can_edit_recipes = serializers.BooleanField()
    can_edit_recipes_status = serializers.CharField()


class EditRecipesRequestSerializer(serializers.Serializer):
    """Serializer for pending edit-recipes sharing requests."""

    friend_request_id = serializers.IntegerField()
    from_user_id = serializers.IntegerField()
    from_username = serializers.CharField()
    to_user_id = serializers.IntegerField()
    to_username = serializers.CharField()
    requested_by_id = serializers.IntegerField()
    requested_by_username = serializers.CharField()
