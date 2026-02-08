"""DRF views for friends and friend requests."""

from django.db import models
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from planner.models import FriendRequest, Recipe, UserFriendCode
from planner.serializers import (
    EditRecipesRequestSerializer,
    FriendRequestSerializer,
    FriendSerializer,
    ShoppingListRequestSerializer,
    UserFriendCodeSerializer,
)
from planner.services import calculate_shopping_list_for_user, get_menu_for_user
from planner.services_friends import get_friend_request_between, get_friend_user_or_404


class MyFriendCodeView(APIView):
    """Return the current user's friend code, creating it lazily if needed."""

    def get(self, request):
        code_obj, _ = UserFriendCode.objects.get_or_create(user=request.user)
        serializer = UserFriendCodeSerializer(code_obj)
        return Response(serializer.data)


class SendFriendRequestView(APIView):
    """Send a friend request to a user identified by their friend code."""

    def post(self, request):
        code = (request.data or {}).get("code")
        if not code:
            raise ValidationError("Код обязателен")

        try:
            friend_code = UserFriendCode.objects.select_related("user").get(code=code)
        except UserFriendCode.DoesNotExist:
            raise ValidationError("Пользователь с таким кодом не найден")

        to_user = friend_code.user
        if to_user == request.user:
            raise ValidationError("Нельзя отправить запрос самому себе")

        already_friends = FriendRequest.objects.filter(
            status=FriendRequest.STATUS_ACCEPTED
        ).filter(
            models.Q(from_user=request.user, to_user=to_user)
            | models.Q(from_user=to_user, to_user=request.user)
        )
        if already_friends.exists():
            raise ValidationError("Уже в друзьях")

        friend_request = FriendRequest.objects.create(
            from_user=request.user,
            to_user=to_user,
            status=FriendRequest.STATUS_PENDING,
        )
        serializer = FriendRequestSerializer(friend_request)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class FriendsListView(APIView):
    """Return the list of friends for the current user."""

    def get(self, request):
        qs = (
            FriendRequest.objects.filter(status=FriendRequest.STATUS_ACCEPTED)
            .filter(models.Q(from_user=request.user) | models.Q(to_user=request.user))
            .select_related("from_user", "to_user")
        )

        friends = []
        for fr in qs:
            if fr.from_user_id == request.user.id:
                other = fr.to_user
            else:
                other = fr.from_user
            friends.append(
                {
                    "user_id": other.id,
                    "username": other.username,
                    "friend_request_id": fr.id,
                    "since": fr.created_at,
                    "can_edit_recipes": fr.can_edit_recipes_status
                    == FriendRequest.EDIT_RECIPES_ACCEPTED,
                    "can_edit_recipes_status": fr.can_edit_recipes_status,
                }
            )

        serializer = FriendSerializer(friends, many=True)
        return Response(serializer.data)


class FriendRemoveView(APIView):
    """Remove an existing friend relationship."""

    def post(self, request, user_id):
        qs = FriendRequest.objects.filter(status=FriendRequest.STATUS_ACCEPTED).filter(
            models.Q(from_user=request.user, to_user_id=user_id)
            | models.Q(from_user_id=user_id, to_user=request.user)
        )
        friend_request = qs.first()
        if not friend_request:
            raise ValidationError("Пользователь не является вашим другом")

        friend_request.status = FriendRequest.STATUS_REMOVED
        friend_request.save(update_fields=["status"])
        return Response({"success": True})


class FriendRequestViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """ViewSet for incoming friend requests with accept/decline actions."""

    queryset = FriendRequest.objects.all().select_related("from_user", "to_user")
    serializer_class = FriendRequestSerializer

    def get_queryset(self):
        base_qs = super().get_queryset()
        if self.action == "list":
            return base_qs.filter(
                to_user=self.request.user,
                status=FriendRequest.STATUS_PENDING,
            )
        return base_qs

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        friend_request = self.get_object()
        if friend_request.to_user_id != request.user.id:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if friend_request.status != FriendRequest.STATUS_PENDING:
            raise ValidationError("Некорректный статус запроса")

        friend_request.status = FriendRequest.STATUS_ACCEPTED
        friend_request.save(update_fields=["status"])

        reverse_qs = FriendRequest.objects.filter(
            from_user=friend_request.to_user,
            to_user=friend_request.from_user,
            status=FriendRequest.STATUS_PENDING,
        )
        if reverse_qs.exists():
            reverse_qs.update(status=FriendRequest.STATUS_CANCELLED)

        serializer = self.get_serializer(friend_request)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        friend_request = self.get_object()
        if friend_request.to_user_id != request.user.id:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if friend_request.status != FriendRequest.STATUS_PENDING:
            raise ValidationError("Некорректный статус запроса")

        friend_request.status = FriendRequest.STATUS_DECLINED
        friend_request.save(update_fields=["status"])

        serializer = self.get_serializer(friend_request)
        return Response(serializer.data)


class FriendSendEditRecipesRequestView(APIView):
    """Send a request to enable mutual recipe editing with a friend."""

    def post(self, request, user_id):
        friend_request = get_friend_request_between(request.user, user_id)
        if not friend_request:
            raise ValidationError("Пользователь не является вашим другом")

        if friend_request.can_edit_recipes_status != FriendRequest.EDIT_RECIPES_NONE:
            raise ValidationError("Запрос на совместное редактирование уже отправлен или принят")

        friend_request.can_edit_recipes_status = FriendRequest.EDIT_RECIPES_PENDING
        friend_request.can_edit_recipes_requested_by = request.user
        friend_request.save(
            update_fields=["can_edit_recipes_status", "can_edit_recipes_requested_by"]
        )
        return Response({
            "success": True,
            "can_edit_recipes_status": friend_request.can_edit_recipes_status,
        })


class FriendRevokeEditRecipesView(APIView):
    """Revoke mutual recipe editing permission. Either friend can revoke."""

    def post(self, request, user_id):
        friend_request = get_friend_request_between(request.user, user_id)
        if not friend_request:
            raise ValidationError("Пользователь не является вашим другом")

        if friend_request.can_edit_recipes_status == FriendRequest.EDIT_RECIPES_NONE:
            raise ValidationError("Совместное редактирование не активно")

        friend_request.can_edit_recipes_status = FriendRequest.EDIT_RECIPES_NONE
        friend_request.can_edit_recipes_requested_by = None
        friend_request.save(
            update_fields=["can_edit_recipes_status", "can_edit_recipes_requested_by"]
        )
        return Response({
            "success": True,
            "can_edit_recipes_status": friend_request.can_edit_recipes_status,
        })


class EditRecipesRequestViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """ViewSet for incoming edit-recipes sharing requests with accept/decline."""

    queryset = FriendRequest.objects.all().select_related(
        "from_user", "to_user", "can_edit_recipes_requested_by"
    )
    serializer_class = EditRecipesRequestSerializer

    def get_queryset(self):
        base_qs = super().get_queryset()
        if self.action == "list":
            return base_qs.filter(
                status=FriendRequest.STATUS_ACCEPTED,
                can_edit_recipes_status=FriendRequest.EDIT_RECIPES_PENDING,
            ).exclude(can_edit_recipes_requested_by=self.request.user)
        return base_qs

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        items = []
        for fr in qs:
            if fr.from_user_id == request.user.id:
                other = fr.to_user
            else:
                other = fr.from_user
            items.append({
                "friend_request_id": fr.id,
                "from_user_id": other.id,
                "from_username": other.username,
                "to_user_id": request.user.id,
                "to_username": request.user.username,
                "requested_by_id": fr.can_edit_recipes_requested_by_id,
                "requested_by_username": fr.can_edit_recipes_requested_by.username,
            })
        serializer = EditRecipesRequestSerializer(items, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        """Accept a pending edit-recipes sharing request."""
        friend_request = self.get_object()
        if not self._is_target_user(request.user, friend_request):
            return Response(status=status.HTTP_404_NOT_FOUND)
        if friend_request.can_edit_recipes_status != FriendRequest.EDIT_RECIPES_PENDING:
            raise ValidationError("Некорректный статус запроса")

        friend_request.can_edit_recipes_status = FriendRequest.EDIT_RECIPES_ACCEPTED
        friend_request.save(update_fields=["can_edit_recipes_status"])
        return Response({"success": True, "can_edit_recipes_status": "accepted"})

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        """Decline a pending edit-recipes sharing request."""
        friend_request = self.get_object()
        if not self._is_target_user(request.user, friend_request):
            return Response(status=status.HTTP_404_NOT_FOUND)
        if friend_request.can_edit_recipes_status != FriendRequest.EDIT_RECIPES_PENDING:
            raise ValidationError("Некорректный статус запроса")

        friend_request.can_edit_recipes_status = FriendRequest.EDIT_RECIPES_NONE
        friend_request.can_edit_recipes_requested_by = None
        friend_request.save(
            update_fields=["can_edit_recipes_status", "can_edit_recipes_requested_by"]
        )
        return Response({"success": True, "can_edit_recipes_status": "none"})

    @staticmethod
    def _is_target_user(user, friend_request):
        """Return True if user is the one who should accept/decline (not the requester)."""
        return (
            friend_request.can_edit_recipes_requested_by_id is not None
            and friend_request.can_edit_recipes_requested_by_id != user.id
            and user.id in (friend_request.from_user_id, friend_request.to_user_id)
        )


class FriendMenuView(APIView):
    """Read-only view of a friend's weekly menu."""

    def get(self, request, user_id):
        friend_user = get_friend_user_or_404(request.user, user_id)
        menu = get_menu_for_user(friend_user)
        recipe_ids = {v for v in menu.values() if v is not None}
        recipes_qs = Recipe.objects.filter(pk__in=recipe_ids)
        recipes = [
            {"id": r.id, "name": r.name, "total_calories": r.total_calories or 0}
            for r in recipes_qs
        ]
        return Response({"menu": menu, "recipes": recipes})


class FriendShoppingListView(APIView):
    """Generate shopping list for a friend's menu."""

    def post(self, request, user_id):
        serializer = ShoppingListRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        friend_user = get_friend_user_or_404(request.user, user_id)
        result = calculate_shopping_list_for_user(
            friend_user,
            data["start_date"],
            data["end_date"],
            data.get("people_count", 2),
        )
        return Response(result)
