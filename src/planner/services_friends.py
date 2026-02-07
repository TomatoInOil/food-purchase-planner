"""Friend-related domain services."""

from django.db import models

from planner.models import FriendRequest


def get_friend_user_or_404(request_user, friend_id):
    """
    Ensure the given friend_id belongs to an accepted friend of request_user.
    Returns the friend User instance. Raises ValidationError if not friends.
    """
    qs = FriendRequest.objects.filter(status=FriendRequest.STATUS_ACCEPTED).filter(
        models.Q(from_user=request_user, to_user_id=friend_id)
        | models.Q(from_user_id=friend_id, to_user=request_user)
    )
    friend_request = qs.select_related("from_user", "to_user").first()
    if not friend_request:
        from rest_framework.exceptions import ValidationError

        raise ValidationError("Пользователь не является вашим другом")

    if friend_request.from_user_id == request_user.id:
        return friend_request.to_user
    return friend_request.from_user


def can_friend_edit_recipes(editor_user, recipe_owner):
    """
    Check if editor_user has permission to edit recipe_owner's recipes.
    Returns True if an accepted friend request with can_edit_recipes=True exists.
    """
    return FriendRequest.objects.filter(
        status=FriendRequest.STATUS_ACCEPTED,
        can_edit_recipes=True,
    ).filter(
        models.Q(from_user=editor_user, to_user=recipe_owner)
        | models.Q(from_user=recipe_owner, to_user=editor_user)
    ).exists()
