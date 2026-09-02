from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Core"

    def ready(self):
        # Importing registers the checks; nothing else uses the module.
        from apps.core import checks  # noqa: F401
