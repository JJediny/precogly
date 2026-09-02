"""Startup checks that hold conventions the type system cannot.

Registered from `CoreConfig.ready`.
"""

from django.apps import apps as django_apps
from django.core.checks import Error, register

from apps.core.tenancy import Tenancy

# Only Precogly's own models are asked to declare. Django's own tables, allauth's, and
# every other dependency's are outside the question — nothing here scopes them and
# nothing here may change them.
DECLARING_APPS = frozenset(
    {
        "ai",
        "compliance",
        "core",
        "diagrams",
        "organizations",
        "packs",
        "systems",
        "threat_models",
        "threats",
    }
)


@register()
def every_model_declares_its_tenancy(app_configs, **kwargs):
    """Refuse to start if a model in `apps/` has not said who its rows belong to.

    The point is the models that do not exist yet. A new model added without a
    `tenancy` attribute fails here on the first `manage.py` command rather than
    reaching review as an unscoped queryset nobody thought to ask about — which is how
    #404 and #405 arrived.

    Inheritance is checked deliberately with `vars()` rather than `getattr`: a concrete
    model inheriting another concrete model would otherwise pick up its parent's answer
    silently, and the parent's answer is not evidence about the child.

    `app_configs` is honoured rather than ignored, so `manage.py check organizations`
    reports on that app alone. It is also the seam the tests use: under `isolate_apps`
    the models being checked are not in the global registry, and a check that only ever
    read `django_apps` could not see them.
    """
    if app_configs is None:
        models = django_apps.get_models()
    else:
        models = [model for config in app_configs for model in config.get_models()]

    errors = []

    for model in models:
        if model._meta.app_label not in DECLARING_APPS:
            continue

        declared = vars(model).get("tenancy")
        if isinstance(declared, Tenancy):
            continue

        if declared is None:
            hint = (
                "Add `tenancy = Tenancy.TENANT_OWNED` if every row belongs to one "
                "organization, or `Tenancy.SHARED_REFERENCE` if every installation "
                "holds the same rows. See apps/core/tenancy.py."
            )
        else:
            hint = f"`tenancy` is {declared!r}; it must be a `Tenancy` member."

        errors.append(
            Error(
                f"{model._meta.label} does not declare its tenancy.",
                hint=hint,
                obj=model,
                id="precogly.E001",
            )
        )

    return errors
