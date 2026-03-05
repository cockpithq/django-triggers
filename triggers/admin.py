from typing import Any, Dict, Iterable, List, Tuple, Type
from urllib.parse import urlencode

from django import forms
from django.apps import apps
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.http import HttpRequest, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.html import format_html_join
from django.utils.translation import gettext_lazy as _
from more_admin_filters import MultiSelectRelatedOnlyFilter
from polymorphic.admin import PolymorphicInlineSupportMixin, StackedPolymorphicInline
from polymorphic.models import PolymorphicModel

from triggers.models import Action, Activity, Condition, Event, Trigger, User, get_model_name


def get_child_models(cls: Type[PolymorphicModel]) -> Iterable[Type[PolymorphicModel]]:
    child_models: List[Type[PolymorphicModel]] = []
    subclass: Type[PolymorphicModel]
    for subclass in cls.__subclasses__():
        if subclass.__subclasses__():
            child_models.extend(get_child_models(subclass))
        if not subclass._meta.abstract:
            child_models.append(subclass)
    return child_models


def get_child_inline(
    cls: Type[PolymorphicModel],
) -> Type[StackedPolymorphicInline.Child]:
    class_dict = {
        "model": cls,
        "extra": 0,
    }

    if cls.__doc__ and not cls.__doc__.startswith(cls.__name__):
        class_dict["readonly_fields"] = ("__doc__",)

        def get_doc(self, obj):
            print("get docs")
            if (
                obj
                and obj.__doc__
                and not obj.__doc__.startswith(obj.__class__.__name__)
            ):
                return obj.__doc__
            return ""

        # Make mypy happy by using proper Django admin display decorator type
        from django.contrib.admin import display

        get_doc = display(description="Documentation")(get_doc)

        class_dict["__doc__"] = get_doc

    if hasattr(cls, "admin_initkwargs"):
        class_dict.update(cls.admin_initkwargs())
    return type(f"{cls.__name__}Inline", (StackedPolymorphicInline.Child,), class_dict)


def generate_child_inlines(
    model: Type[PolymorphicModel],
) -> Iterable[Type[StackedPolymorphicInline.Child]]:
    sorted_child_models = sorted(
        get_child_models(model),
        key=lambda _model: get_model_name(_model).lower(),
    )
    return [get_child_inline(child_model) for child_model in sorted_child_models]


class ConditionInline(StackedPolymorphicInline):
    model = Condition
    child_inlines = generate_child_inlines(Condition)


class ActionInline(StackedPolymorphicInline):
    model = Action
    child_inlines = generate_child_inlines(Action)
    fk_name = "trigger"


class EventInline(StackedPolymorphicInline):
    model = Event
    child_inlines = generate_child_inlines(Event)


class RelatedOnlyFieldMultiListFilter(MultiSelectRelatedOnlyFilter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = self.__class__.__dict__["title"]

    def field_choices(self, field, request, model_admin) -> List[Tuple[str, str]]:
        choices = super().field_choices(field, request, model_admin)
        choices.sort(key=lambda choice: choice[1])
        return choices


def create_related_filter(title):
    return type("_RelatedFilter", (RelatedOnlyFieldMultiListFilter,), {"title": title})


class TriggerExecutionLogsForm(forms.Form):
    email = forms.EmailField(label=_("User email"))


@admin.register(Trigger)
class TriggerAdmin(PolymorphicInlineSupportMixin, admin.ModelAdmin):
    inlines = (
        ActionInline,
        EventInline,
        ConditionInline,
    )
    list_display = (
        "id",
        "name",
        "display_events",
        "display_conditions",
        "display_actions",
        "is_enabled",
    )
    list_filter = (
        "is_enabled",
        ("event__polymorphic_ctype", create_related_filter(_("event"))),
        ("condition__polymorphic_ctype", create_related_filter(_("condition"))),
        ("action__polymorphic_ctype", create_related_filter(_("action"))),
    )
    polymorphic_list = True
    actions = ("view_user_execution_logs",)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "execution-logs/",
                self.admin_site.admin_view(self.execution_logs_timeline_view),
                name="triggers_trigger_execution_logs",
            ),
        ]
        return custom_urls + urls

    def get_queryset(self, request):
        base_queryset = super().get_queryset(request)
        return base_queryset.prefetch_related("events", "conditions", "actions")

    @admin.display(description=_("events"), ordering="event__polymorphic_ctype")
    def display_events(self, obj: Trigger) -> str:
        return format_html_join(
            "\n",
            "<li>{0}</li>",
            sorted((str(event).capitalize(),) for event in obj.events.all()),
        )

    @admin.display(description=_("conditions"), ordering="condition__polymorphic_ctype")
    def display_conditions(self, obj: Trigger):
        return format_html_join(
            "\n",
            "<li>{0}</li>",
            sorted(
                (str(condition).capitalize(),) for condition in obj.conditions.all()
            ),
        )

    @admin.display(description=_("action"), ordering="action__polymorphic_ctype")
    def display_actions(self, obj: Trigger):
        return format_html_join(
            "\n",
            "<li>{0}</li>",
            sorted((str(action).capitalize(),) for action in obj.actions.all()),
        )

    @admin.action(description=_("View user execution logs"))
    def view_user_execution_logs(self, request: HttpRequest, queryset):
        if queryset.count() != 1:
            self.message_user(
                request,
                _("Please select exactly one trigger."),
                level=messages.ERROR,
            )
            return None

        trigger = queryset.first()
        if trigger is None:
            return None

        form = TriggerExecutionLogsForm(request.POST or None)
        if request.POST.get("apply") and form.is_valid():
            query_string = urlencode(
                {
                    "trigger_id": trigger.pk,
                    "email": form.cleaned_data["email"],
                }
            )
            url = reverse("admin:triggers_trigger_execution_logs")
            return HttpResponseRedirect(f"{url}?{query_string}")

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "queryset": queryset,
            "form": form,
            "title": _("View user execution logs timeline"),
            "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
            "action_name": "view_user_execution_logs",
            "trigger": trigger,
        }
        return TemplateResponse(
            request,
            "admin/triggers/trigger/execution_logs_action.html",
            context,
        )

    def _format_steps(
        self,
        *,
        steps: List[Any],
        condition_names: Dict[int, str],
        action_names: Dict[int, str],
    ) -> List[str]:
        formatted_steps: List[str] = []
        for step in steps:
            if not isinstance(step, list) or not step:
                continue
            step_type = step[0]
            if step_type == 1:
                formatted_steps.append(str(_("Event handling started")))
            elif step_type == 2:
                user_found = bool(step[1]) if len(step) > 1 else False
                formatted_steps.append(
                    str(_("User resolved: %(status)s")) % {
                        "status": _("yes") if user_found else _("no")
                    }
                )
            elif step_type == 3 and len(step) > 2:
                condition_id = step[1]
                condition_name = condition_names.get(
                    condition_id,
                    str(_("Condition #%(id)s")) % {"id": condition_id},
                )
                is_satisfied = bool(step[2])
                formatted_steps.append(
                    str(_("%(condition)s -> %(status)s")) % {
                        "condition": condition_name,
                        "status": _("passed") if is_satisfied else _("failed"),
                    }
                )
            elif step_type == 4 and len(step) > 2:
                action_id = step[1]
                action_name = action_names.get(
                    action_id,
                    str(_("Action #%(id)s")) % {"id": action_id},
                )
                is_successful = bool(step[2])
                if is_successful:
                    formatted_steps.append(
                        str(_("%(action)s -> performed")) % {"action": action_name}
                    )
                else:
                    error_name = step[3] if len(step) > 3 else _("Unknown error")
                    formatted_steps.append(
                        str(_("%(action)s -> failed (%(error)s)")) % {
                            "action": action_name,
                            "error": error_name,
                        }
                    )
        return formatted_steps

    def execution_logs_timeline_view(self, request: HttpRequest):
        if not apps.is_installed("triggers.contrib.logging"):
            self.message_user(
                request,
                _("triggers.contrib.logging is not installed."),
                level=messages.ERROR,
            )
            return HttpResponseRedirect(reverse("admin:triggers_trigger_changelist"))

        trigger_id = request.GET.get("trigger_id", "")
        email = request.GET.get("email", "").strip()
        trigger = Trigger.objects.filter(pk=trigger_id).first() if trigger_id else None

        logs = []
        user = None
        if trigger and email:
            execution_log_model = apps.get_model("logging", "TriggerExecutionLog")
            email_field_name = User.get_email_field_name()
            user = User.objects.filter(**{f"{email_field_name}__iexact": email}).first()
            if user:
                condition_names = {
                    condition.pk: str(condition)
                    for condition in trigger.conditions.all()
                    if condition.pk is not None
                }
                action_names = {
                    action.pk: str(action)
                    for action in trigger.actions.all()
                    if action.pk is not None
                }
                raw_logs = execution_log_model.objects.filter(
                    trigger=trigger,
                    user=user,
                ).order_by("-created_at")
                logs = [
                    {
                        "log": log,
                        "steps": self._format_steps(
                            steps=list(log.steps),
                            condition_names=condition_names,
                            action_names=action_names,
                        ),
                    }
                    for log in raw_logs
                ]

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": _("Execution logs timeline"),
            "trigger": trigger,
            "email": email,
            "user": user,
            "logs": logs,
        }
        return TemplateResponse(
            request,
            "admin/triggers/trigger/execution_logs_timeline.html",
            context,
        )


@admin.register(Activity)
class ActivityActionAdmin(admin.ModelAdmin):
    list_display = (
        "trigger",
        "user",
        "last_action_datetime",
        "action_count",
    )
    list_filter = ("trigger",)
    list_select_related = (
        "trigger",
        "user",
    )
    readonly_fields = list_display
    search_fields = tuple(
        {
            f"=user__{User.get_email_field_name()}",
            f"=user__{User.USERNAME_FIELD}",
        }
    )

    def has_add_permission(self, request, obj=None):
        return False
