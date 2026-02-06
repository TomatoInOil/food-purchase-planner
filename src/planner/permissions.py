"""DRF permission classes for planner API."""

from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Allow read for everyone; create/update/delete only for the owner."""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return obj.user_id == request.user.id


def is_system_ingredient(ingredient):
    return ingredient.user.username == "system"
