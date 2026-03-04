from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.translation import gettext_lazy as _

from triggers.models import Trigger


class TriggerExecutionLog(models.Model):
    STATUS_ENQUEUED = "enqueued"
    STATUS_STARTED = "started"
    STATUS_SUCCESS = "success"
    STATUS_CONDITIONS_FAILED = "conditions_failed"
    STATUS_USER_NOT_FOUND = "user_not_found"
    STATUS_ACTION_FAILED = "action_failed"
    STATUS_CHOICES = (
        (STATUS_ENQUEUED, _("Enqueued")),
        (STATUS_STARTED, _("Started")),
        (STATUS_SUCCESS, _("Success")),
        (STATUS_CONDITIONS_FAILED, _("Conditions failed")),
        (STATUS_USER_NOT_FOUND, _("User not found")),
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
        related_name="trigger_execution_logs",
        related_query_name="trigger_execution_log",
        null=True,
        blank=True,
        verbose_name=_("user"),
    )
    trigger = models.ForeignKey(
        to=Trigger,
        on_delete=models.SET_NULL,
        related_name="execution_logs",
        related_query_name="execution_log",
        null=True,
        blank=True,
        verbose_name=_("trigger"),
    )
    event_content_type = models.ForeignKey(
        to=ContentType,
        on_delete=models.SET_NULL,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("event content type"),
    )
    event_object_id = models.BigIntegerField(_("event object id"), null=True, blank=True)
    steps = models.JSONField(_("steps"), default=list, blank=True)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    started_at = models.DateTimeField(_("started at"), null=True, blank=True)
    finished_at = models.DateTimeField(_("finished at"), null=True, blank=True)

    class Meta:
        verbose_name = _("trigger execution log")
        verbose_name_plural = _("trigger execution logs")
        ordering = ("-created_at",)
        indexes = (
            models.Index(fields=("user", "created_at")),
            models.Index(fields=("status", "created_at")),
            models.Index(fields=("trigger", "created_at")),
        )

    def __str__(self):
        return f"{self.run_id} ({self.status})"
