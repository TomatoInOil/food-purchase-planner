from django.apps import AppConfig


class PlannerConfig(AppConfig):
    """Configuration for the planner application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "planner"
    verbose_name = "Food Purchase Planner"

    def ready(self):
        import planner.signals  # noqa: F401
