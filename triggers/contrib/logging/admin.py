from django.contrib import admin

from triggers.contrib.logging.models import TriggerExecutionLog
from triggers.models import User


@admin.register(TriggerExecutionLog)
class TriggerExecutionLogAdmin(admin.ModelAdmin):
    list_display = (
        "run_id",
        "status",
        "user",
        "trigger",
        "event_content_type",
        "event_object_id",
        "created_at",
        "finished_at",
    )
    list_filter = ("status", "trigger", "event_content_type")
    readonly_fields = (
        "run_id",
        "status",
        "user",
        "trigger",
        "event_content_type",
        "event_object_id",
        "steps",
        "created_at",
        "started_at",
        "finished_at",
    )
    search_fields = tuple(
        {
            "run_id",
            f"=user__{User.USERNAME_FIELD}",
            f"=user__{User.get_email_field_name()}",
        }
    )

    def has_add_permission(self, request, obj=None):
        return False
