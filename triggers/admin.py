from typing import Iterable, List, Type

from django.contrib import admin
from django.utils.html import format_html_join
from django.utils.translation import gettext_lazy as _
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


def get_child_inline(cls: Type[PolymorphicModel]) -> Type[StackedPolymorphicInline.Child]:
    class_dict = {'model': cls, 'extra': 0}
    if hasattr(cls, 'admin_initkwargs'):
        class_dict.update(cls.admin_initkwargs())
    return type(f'{cls.__name__}Inline', (StackedPolymorphicInline.Child,), class_dict)


def generate_child_inlines(model: Type[PolymorphicModel]) -> Iterable[Type[StackedPolymorphicInline.Child]]:
    sorted_child_models = sorted(get_child_models(model), key=lambda _model: get_model_name(_model).lower())
    return [get_child_inline(child_model) for child_model in sorted_child_models]


class ConditionInline(StackedPolymorphicInline):
    model = Condition
    child_inlines = generate_child_inlines(Condition)


class ActionInline(StackedPolymorphicInline):
    model = Action
    child_inlines = generate_child_inlines(Action)


class EventInline(StackedPolymorphicInline):
    model = Event
    child_inlines = generate_child_inlines(Event)


class _OverrideTitle:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title = self.__class__.__dict__['title']


def create_related_filter(title):
    return type('_RelatedFilter', (_OverrideTitle, admin.RelatedOnlyFieldListFilter), {'title': title})


@admin.register(Trigger)
class TriggerAdmin(PolymorphicInlineSupportMixin, admin.ModelAdmin):
    inlines = ActionInline, EventInline, ConditionInline,
    list_display = 'id', 'name', 'get_events', 'get_conditions', 'get_action', 'is_enabled',
    list_filter = (
        'is_enabled',
        ('event__polymorphic_ctype', create_related_filter(_('event'))),
        ('condition__polymorphic_ctype', create_related_filter(_('condition'))),
        ('action__polymorphic_ctype', create_related_filter(_('action'))),
    )
    polymorphic_list = True

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('events', 'conditions').select_related('action')

    @admin.display(description=_('events'))
    def get_events(self, obj: Trigger) -> str:
        return format_html_join('\n', '<li>{0}</li>', ((str(event).capitalize(),) for event in obj.events.all()))

    @admin.display(description=_('conditions'))
    def get_conditions(self, obj: Trigger):
        return format_html_join(
            '\n',
            '<li>{0}</li>',
            ((str(condition).capitalize(),) for condition in obj.conditions.all()),
        )

    @admin.display(description=_('action'))
    def get_action(self, obj: Trigger):
        return str(obj.action.get_real_instance()).capitalize() if hasattr(obj, 'action') else None


@admin.register(Activity)
class ActivityActionAdmin(admin.ModelAdmin):
    list_display = 'trigger', 'user', 'last_action_datetime', 'action_count',
    list_filter = 'trigger',
    readonly_fields = list_display
    search_fields = tuple({f'=user__{User.get_email_field_name()}', f'=user__{User.USERNAME_FIELD}'})

    def has_add_permission(self, request, obj=None):
        return False
