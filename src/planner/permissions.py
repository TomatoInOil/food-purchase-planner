"""DRF permission classes for planner API."""

from rest_framework import permissions

from planner.services_friends import can_friend_edit_recipes


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Allow read for everyone; create/update/delete only for the owner."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user_id == request.user.id


class IsOwnerOrFriendEditorOrReadOnly(permissions.BasePermission):
    """Allow read for everyone; write for the owner or a friend with edit permission."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if obj.user_id == request.user.id:
            return True
        return can_friend_edit_recipes(request.user, obj.user)


def is_system_ingredient(ingredient):
    return ingredient.user.username == "system"
