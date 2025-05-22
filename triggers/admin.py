from typing import Iterable, List, Tuple, Type

from django.contrib import admin
from django.utils.html import format_html_join
from django.utils.translation import gettext_lazy as _
from more_admin_filters import MultiSelectRelatedOnlyFilter
from polymorphic.admin import PolymorphicInlineSupportMixin, StackedPolymorphicInline
from polymorphic.models import PolymorphicModel

from triggers.models import Action, Activity, Condition, Event, Trigger, User, get_model_name, TriggerLog


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


class RunIdFilter(admin.SimpleListFilter):
    title = _("Execution")
    parameter_name = "run_id"

    def lookups(self, request, model_admin):
        # Get unique run_ids from the last 100 logs
        run_ids = TriggerLog.objects.order_by("-timestamp").values_list("run_id", flat=True).distinct()[:100]
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
        from django.utils import timezone
        import datetime
        
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
        "timestamp", "entity_type", "entity_name", "stage", 
        "trigger", "user", "result", "run_id_short"
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
        "timestamp", "run_id", "entity_type", "entity_id", 
        "entity_class_path", "entity_name", "trigger", "user",
        "stage", "result", "details"
    )
    date_hierarchy = "timestamp"
    
    def run_id_short(self, obj):
        """Display a shortened version of the run_id"""
        return str(obj.run_id)[:8] + "..."
    run_id_short.short_description = _("Run ID")
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Allow deletion for log cleanup
        return True
    
    fieldsets = (
        (_("Basic Information"), {
            "fields": ("timestamp", "run_id", "stage", "result")
        }),
        (_("Entity"), {
            "fields": ("entity_type", "entity_id", "entity_class_path", "entity_name")
        }),
        (_("Relations"), {
            "fields": ("trigger", "user")
        }),
        (_("Details"), {
            "fields": ("details",)
        }),
    )
