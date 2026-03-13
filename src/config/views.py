"""Views for config project."""

from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as AuthLoginView
from django.contrib.auth.views import LogoutView as AuthLogoutView
from django.shortcuts import redirect
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import CreateView, TemplateView

from config.forms import RegisterForm


@method_decorator(ensure_csrf_cookie, name="dispatch")
class RecipeManagerView(LoginRequiredMixin, TemplateView):
    """Recipe manager page; requires authentication."""

    template_name = "recipe_manager.html"


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CookTodayView(LoginRequiredMixin, TemplateView):
    """Cook Today page; shows today's recipes in detail."""

    template_name = "cook_today.html"


class LoginView(AuthLoginView):
    """Login page."""

    template_name = "auth/login.html"


class RegisterView(CreateView):
    """Registration page; logs in and redirects to home on success."""

    form_class = RegisterForm
    template_name = "auth/register.html"
    success_url = "/"

    def form_valid(self, form):
        self.object = form.save()
        login(self.request, self.object)
        return redirect(self.get_success_url())


class LogoutView(AuthLogoutView):
    """Logout; redirect configured via LOGOUT_REDIRECT_URL."""

    pass
