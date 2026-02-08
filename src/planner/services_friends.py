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


def get_editable_owner_ids(editor_user):
    """Return the set of user IDs whose recipes *editor_user* may edit.

    Executes a single DB query instead of one per recipe, eliminating the
    N+1 problem that occurred when ``can_friend_edit_recipes`` was called
    inside a serializer loop.
    """
    qs = FriendRequest.objects.filter(
        status=FriendRequest.STATUS_ACCEPTED,
        can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
    ).filter(
        models.Q(from_user=editor_user) | models.Q(to_user=editor_user)
    )

    owner_ids: set[int] = set()
    for fr in qs.only("from_user_id", "to_user_id").iterator():
        other_id = (
            fr.to_user_id if fr.from_user_id == editor_user.id else fr.from_user_id
        )
        owner_ids.add(other_id)
    return owner_ids


def can_friend_edit_recipes(editor_user, recipe_owner):
    """
    Check if editor_user has permission to edit recipe_owner's recipes.

    Returns True only when both users have mutually agreed to shared editing,
    i.e. an accepted friend request exists with can_edit_recipes_status='accepted'.
    """
    return FriendRequest.objects.filter(
        status=FriendRequest.STATUS_ACCEPTED,
        can_edit_recipes_status=FriendRequest.EDIT_RECIPES_ACCEPTED,
    ).filter(
        models.Q(from_user=editor_user, to_user=recipe_owner)
        | models.Q(from_user=recipe_owner, to_user=editor_user)
    ).exists()


def get_friend_request_between(user_a, user_b):
    """
    Return the accepted FriendRequest between two users, or None.
    """
    return FriendRequest.objects.filter(
        status=FriendRequest.STATUS_ACCEPTED,
    ).filter(
        models.Q(from_user=user_a, to_user=user_b)
        | models.Q(from_user=user_b, to_user=user_a)
    ).select_related("from_user", "to_user").first()
