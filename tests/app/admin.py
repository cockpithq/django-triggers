from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from tests.app.models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    actions = "complete_tasks",
    autocomplete_fields = "user",
    list_display = "name", "user", "is_important", "is_completed"
    list_select_related = "user",
    readonly_fields = "is_completed",

    @admin.action(description=_("Complete selected tasks"))
    def complete_tasks(self, request, queryset):
        task: Task
        for task in queryset:
            task.complete()
