"""Views for config project."""

from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView


@method_decorator(ensure_csrf_cookie, name="dispatch")
class RecipeManagerView(LoginRequiredMixin, TemplateView):
    """Recipe manager page; requires authentication."""

    template_name = "recipe_manager.html"


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CookTodayView(LoginRequiredMixin, TemplateView):
    """Cook Today page; shows today's recipes in detail."""

    template_name = "cook_today.html"


class TelegramLoginPageView(TemplateView):
    """Login page with Telegram Login Widget; redirects authenticated users home."""

    template_name = "auth/telegram_login.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(settings.LOGIN_REDIRECT_URL)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["bot_username"] = settings.TELEGRAM_BOT_USERNAME
        context["telegram_callback_url"] = self.request.build_absolute_uri(
            reverse("telegram-callback")
        )
        return context
