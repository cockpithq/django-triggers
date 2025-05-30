import importlib
import uuid
from typing import Any

from django.conf import settings
from django.db import models
from django.db.models import JSONField
from django.core.exceptions import ObjectDoesNotExist
from django.utils.translation import gettext_lazy as _

from triggers.models import Trigger


class TriggerLog(models.Model):
    """Logging of all trigger processing stages."""

    ENTITY_TYPES = [
        ("event", _("Event")),
        ("trigger", _("Trigger")),
        ("condition", _("Condition")),
        ("action", _("Action")),
    ]

    STAGES = [
        ("fire", _("Fire initiated")),
        ("should_be_fired", _("Should be fired check")),
        ("trigger_filter", _("Trigger filtering")),
        ("condition_filter", _("Condition filtering")),
        ("signal_sent", _("Signal sent")),
        ("task_created", _("Task created")),
        ("handle_start", _("Handle start")),
        ("condition_check", _("Condition satisfied check")),
        ("action_perform", _("Action perform")),
    ]

    timestamp = models.DateTimeField(_("timestamp"), auto_now_add=True)
    run_id = models.UUIDField(
        _("run ID"), db_index=True, help_text=_("Trigger execution identifier")
    )
    entity_type = models.CharField(_("entity type"), max_length=20, choices=ENTITY_TYPES)
    entity_id = models.PositiveIntegerField(_("entity ID"))
    entity_class_path = models.CharField(_("entity class path"), max_length=255)
    entity_name = models.CharField(_("entity name"), max_length=255, blank=True)
    trigger = models.ForeignKey(
        Trigger,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name=_("trigger"),
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trigger_logs",
        null=True,
        blank=True,
        verbose_name=_("user"),
    )
    stage = models.CharField(_("stage"), max_length=30, choices=STAGES)
    result = models.BooleanField(_("result"), null=True, blank=True)
    details = JSONField(_("details"), blank=True, null=True, default=dict)

    class Meta:
        verbose_name = _("trigger log")
        verbose_name_plural = _("trigger logs")
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"{self.get_stage_display()} - {self.entity_name} ({self.timestamp.strftime('%Y-%m-%d %H:%M:%S')})"

    def get_entity_object(self) -> Any:
        try:
            module_path, class_name = self.entity_class_path.rsplit(".", 1)
            module = importlib.import_module(module_path)
            entity_class = getattr(module, class_name)
            return entity_class.objects.get(pk=self.entity_id)
        except (ImportError, AttributeError, ValueError):
            return None
        except ObjectDoesNotExist:
            return None


def log_trigger_event(entity, entity_type, stage, trigger=None, user=None, result=None, details=None, run_id=None):
    """Log a trigger event."""
    if trigger is None:
        if entity_type == "trigger" and isinstance(entity, Trigger):
            trigger = entity
        elif hasattr(entity, "trigger") and isinstance(entity.trigger, Trigger):
            trigger = entity.trigger
        elif hasattr(entity, "trigger_id") and entity.trigger_id:
            try:
                trigger = Trigger.objects.get(pk=entity.trigger_id)
            except Trigger.DoesNotExist:
                pass
    if trigger is None:
        return None

    if not details:
        details = {}

    if run_id is None:
        run_id = uuid.uuid4()

    entity_class = entity.__class__
    entity_class_path = f"{entity_class.__module__}.{entity_class.__name__}"

    TriggerLog.objects.create(
        run_id=run_id,
        entity_type=entity_type,
        entity_id=entity.pk,
        entity_class_path=entity_class_path,
        entity_name=str(entity),
        trigger=trigger,
        user=user,
        stage=stage,
        result=result,
        details=details,
    )

    return run_id
