from __future__ import annotations

import datetime

from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from triggers.contrib.logging.models import TriggerLog
from triggers.models import User


class RunIdFilter(admin.SimpleListFilter):
    title = _("Execution")
    parameter_name = "run_id"

    def lookups(self, request, model_admin):
        run_ids = (
            TriggerLog.objects.order_by("-timestamp")
            .values_list("run_id", flat=True)
            .distinct()[:100]
        )
        return [(str(run_id), str(run_id)[:8] + "...") for run_id in run_ids]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(run_id=self.value())
        return queryset


class TimestampFilter(admin.SimpleListFilter):
    title = _("Time")
    parameter_name = "time_period"

    def lookups(self, request, model_admin):
        return [
            ("last_hour", _("Last hour")),
            ("today", _("Today")),
            ("yesterday", _("Yesterday")),
            ("this_week", _("This week")),
            ("this_month", _("This month")),
        ]

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == "last_hour":
            return queryset.filter(timestamp__gte=now - datetime.timedelta(hours=1))
        elif self.value() == "today":
            return queryset.filter(timestamp__date=now.date())
        elif self.value() == "yesterday":
            return queryset.filter(timestamp__date=now.date() - datetime.timedelta(days=1))
        elif self.value() == "this_week":
            week_start = now.date() - datetime.timedelta(days=now.weekday())
            return queryset.filter(timestamp__date__gte=week_start)
        elif self.value() == "this_month":
            return queryset.filter(timestamp__year=now.year, timestamp__month=now.month)
        return queryset


class ResultFilter(admin.SimpleListFilter):
    title = _("Result")
    parameter_name = "result"

    def lookups(self, request, model_admin):
        return [
            ("success", _("Success")),
            ("failure", _("Failure")),
            ("undefined", _("Undefined")),
        ]

    def queryset(self, request, queryset):
        if self.value() == "success":
            return queryset.filter(result=True)
        elif self.value() == "failure":
            return queryset.filter(result=False)
        elif self.value() == "undefined":
            return queryset.filter(result__isnull=True)
        return queryset


@admin.register(TriggerLog)
class TriggerLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "entity_type",
        "entity_name",
        "stage",
        "trigger",
        "user",
        "result",
        "run_id_short",
    )
    list_filter = (
        RunIdFilter,
        "entity_type",
        "stage",
        "trigger",
        ResultFilter,
        TimestampFilter,
    )
    search_fields = (
        "entity_name",
        "details",
        "entity_class_path",
        "run_id",
        f"=user__{User.get_email_field_name()}",
        f"=user__{User.USERNAME_FIELD}",
    )
    readonly_fields = (
        "timestamp",
        "run_id",
        "entity_type",
        "entity_id",
        "entity_class_path",
        "entity_name",
        "trigger",
        "user",
        "stage",
        "result",
        "details",
    )
    date_hierarchy = "timestamp"

    @admin.display(description=_("Run ID"))
    def run_id_short(self, obj):
        return str(obj.run_id)[:8] + "..."

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True

    fieldsets = (
        (_("Basic Information"), {"fields": ("timestamp", "run_id", "stage", "result")}),
        (
            _("Entity"),
            {"fields": ("entity_type", "entity_id", "entity_class_path", "entity_name")},
        ),
        (_("Relations"), {"fields": ("trigger", "user")}),
        (_("Details"), {"fields": ("details",)}),
    )
