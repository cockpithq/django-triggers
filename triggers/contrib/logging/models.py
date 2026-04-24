from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from triggers.models import Event, Trigger

User = get_user_model()


class TriggerRunQuerySet(models.QuerySet):
    def for_run_id(
        self,
        *,
        run_id: str,
        event,
        user_pk: Any,
    ) -> "TriggerRun":
        """Get or create run for a specific run_id."""
        user_id = user_pk if User.objects.filter(pk=user_pk).exists() else None
        execution_log, _created = self.get_or_create(
            run_id=run_id,
            defaults={
                "user_id": user_id,
                "trigger": event.trigger,
                "event": event,
            },
        )
        return execution_log


class TriggerRun(models.Model):
    STATUS_ENQUEUED = "enqueued"
    STATUS_STARTED = "started"
    STATUS_SUCCEEDED = "succeeded"
    STATUS_CONDITIONS_FAILED = "conditions_failed"
    STATUS_SKIPPED = "skipped"
    STATUS_ACTION_FAILED = "action_failed"
    STATUS_CHOICES = (
        (STATUS_ENQUEUED, _("Enqueued")),
        (STATUS_STARTED, _("Started")),
        (STATUS_SUCCEEDED, _("Succeeded")),
        (STATUS_CONDITIONS_FAILED, _("Conditions failed")),
        (STATUS_SKIPPED, _("User not found")),
        (STATUS_ACTION_FAILED, _("Action failed")),
    )

    run_id = models.CharField(_("run id"), max_length=32, unique=True, db_index=True)
    status = models.CharField(
        _("status"),
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_ENQUEUED,
    )
    user = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="trigger_runs",
        related_query_name="trigger_run",
        null=True,
        blank=True,
        verbose_name=_("user"),
    )
    trigger = models.ForeignKey(
        to=Trigger,
        on_delete=models.SET_NULL,
        related_name="runs",
        related_query_name="run",
        null=True,
        blank=True,
        verbose_name=_("trigger"),
    )
    event = models.ForeignKey(
        to=Event,
        on_delete=models.SET_NULL,
        related_name="trigger_runs",
        related_query_name="trigger_run",
        null=True,
        blank=True,
        verbose_name=_("event"),
    )
    timeline = models.JSONField(_("timeline"), default=list, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    finished_at = models.DateTimeField(_("finished at"), null=True, blank=True)

    objects = TriggerRunQuerySet.as_manager()

    class Meta:
        verbose_name = _("trigger run")
        verbose_name_plural = _("trigger runs")
        ordering = ("-created_at",)
        indexes = (
            models.Index(fields=("user", "created_at")),
            models.Index(fields=("status", "created_at")),
            models.Index(fields=("trigger", "created_at")),
        )

    def __str__(self):
        return f"{self.run_id} ({self.status})"

    def append_step(self, step):
        """Append a step to the timeline with timestamp."""
        timestamp_ms = int(timezone.now().timestamp() * 1000)
        current_timeline = (
            TriggerRun.objects.filter(pk=self.pk).values_list("timeline", flat=True).first()
        )
        timeline = list(current_timeline or [])
        timeline.append([*step, timestamp_ms])
        TriggerRun.objects.filter(pk=self.pk).update(timeline=timeline)
