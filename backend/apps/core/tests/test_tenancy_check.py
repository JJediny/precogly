"""What the tenancy check accepts, and what it refuses.

The check exists for models that do not exist yet, so the case that matters is a new
model added without an answer. `isolate_apps` is how that is written without adding a
real model to the tree: models defined inside it are registered for the duration of the
test and never reach a migration.

Those models live in a registry of their own rather than the global one, which is why
each test passes the isolated app config in as `app_configs` — reading
`django.apps.apps` would report on the real tree and never see them.
"""

from django.apps import apps as django_apps
from django.db import models
from django.test import SimpleTestCase
from django.test.utils import isolate_apps

from apps.core.checks import DECLARING_APPS, every_model_declares_its_tenancy
from apps.core.tenancy import MIXED_MODELS, Tenancy


def _ids(errors):
    return [error.id for error in errors]


def _check(isolated_apps):
    return every_model_declares_its_tenancy(
        app_configs=[isolated_apps.get_app_config("core")]
    )


class TenancyCheckTests(SimpleTestCase):
    def test_the_tree_as_it_stands_passes(self):
        """Every model in `apps/` has answered. This is the check doing its job."""
        self.assertEqual(every_model_declares_its_tenancy(app_configs=None), [])

    @isolate_apps("apps.core", kwarg_name="isolated_apps")
    def test_a_model_with_no_declaration_is_an_error(self, isolated_apps):
        class Undeclared(models.Model):
            name = models.CharField(max_length=10)

        errors = _check(isolated_apps)
        self.assertEqual(_ids(errors), ["precogly.E001"])
        self.assertIs(errors[0].obj, Undeclared)

    @isolate_apps("apps.core", kwarg_name="isolated_apps")
    def test_either_value_satisfies_it(self, isolated_apps):
        class OwnedByOneOrganization(models.Model):
            tenancy = Tenancy.TENANT_OWNED

        class ShippedWithEveryInstall(models.Model):
            tenancy = Tenancy.SHARED_REFERENCE

        self.assertEqual(_check(isolated_apps), [])

    @isolate_apps("apps.core", kwarg_name="isolated_apps")
    def test_a_value_that_is_not_a_tenancy_member_is_an_error(self, isolated_apps):
        """A string that looks right is still not an answer.

        `tenancy = "tenant-owned"` would otherwise pass a truthiness test and give
        step 3 something it cannot dispatch on.
        """

        class DeclaredAsAString(models.Model):
            tenancy = "tenant-owned"

        errors = _check(isolated_apps)
        self.assertEqual(_ids(errors), ["precogly.E001"])
        self.assertIs(errors[0].obj, DeclaredAsAString)

    @isolate_apps("apps.core", kwarg_name="isolated_apps")
    def test_a_declaration_is_not_inherited_from_a_concrete_parent(self, isolated_apps):
        """A subclass has to answer for itself.

        Multi-table inheritance would otherwise let a child pick up its parent's answer
        silently, and the parent's answer is not evidence about the child's — the child
        may add exactly the foreign key that changes it.
        """

        class DeclaredParent(models.Model):
            tenancy = Tenancy.SHARED_REFERENCE

        class SilentChild(DeclaredParent):
            pass

        errors = _check(isolated_apps)
        self.assertEqual(_ids(errors), ["precogly.E001"])
        self.assertIs(errors[0].obj, SilentChild)


class MixedModelsTests(SimpleTestCase):
    """`Tenancy.MIXED` is a defect being carried, so the set of them may only shrink.

    A table holding both shared and tenant-owned rows tells them apart by a key that
    exists for another purpose — `source_pack` records provenance, `threat_model`
    records attachment — and reading either as "therefore nobody owns this row" is the
    inference that leaked in #405. A new one must not be added quietly; removing one
    means it was split or given an explicit owner column.
    """

    def test_no_model_has_become_mixed(self):
        declared = {
            model._meta.label
            for model in django_apps.get_models()
            if model._meta.app_label in DECLARING_APPS
            and vars(model).get("tenancy") is Tenancy.MIXED
        }
        self.assertEqual(
            declared - MIXED_MODELS,
            set(),
            "A model has been declared MIXED without being added to MIXED_MODELS. "
            "Splitting the table or giving it an explicit owner column is the fix; "
            "see Tenancy.MIXED in apps/core/tenancy.py.",
        )

    def test_a_model_that_stopped_being_mixed_is_removed_from_the_list(self):
        declared = {
            model._meta.label
            for model in django_apps.get_models()
            if model._meta.app_label in DECLARING_APPS
            and vars(model).get("tenancy") is Tenancy.MIXED
        }
        self.assertEqual(
            MIXED_MODELS - declared,
            set(),
            "MIXED_MODELS names a model that no longer declares MIXED. Delete the "
            "entry — the list is the record of what is still outstanding.",
        )
