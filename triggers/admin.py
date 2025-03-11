from typing import Iterable, List, Tuple, Type

from django.contrib import admin
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


def get_child_inline(cls: Type[PolymorphicModel]) -> Type[StackedPolymorphicInline.Child]:
    class_dict = {
        'model': cls,
        'extra': 0,
    }

    if cls.__doc__ and not cls.__doc__.startswith(cls.__name__):
        class_dict['readonly_fields'] = ('__doc__',)

        def get_doc(self, obj):
            print('get docs')
            if obj and obj.__doc__ and not obj.__doc__.startswith(obj.__class__.__name__):
                return obj.__doc__
            return ''

        get_doc.short_description = 'Documentation'

        class_dict['__doc__'] = get_doc

    if hasattr(cls, 'admin_initkwargs'):
        class_dict.update(cls.admin_initkwargs())
    return type(f'{cls.__name__}Inline', (StackedPolymorphicInline.Child,), class_dict)


def generate_child_inlines(
    model: Type[PolymorphicModel]
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
        self.title = self.__class__.__dict__['title']

    def field_choices(self, field, request, model_admin) -> List[Tuple[str, str]]:
        choices = super().field_choices(field, request, model_admin)
        choices.sort(key=lambda choice: choice[1])
        return choices


def create_related_filter(title):
    return type('_RelatedFilter', (RelatedOnlyFieldMultiListFilter,), {'title': title})


@admin.register(Trigger)
class TriggerAdmin(PolymorphicInlineSupportMixin, admin.ModelAdmin):
    inlines = ActionInline, EventInline, ConditionInline,
    list_display = (
        'id',
        'name',
        'display_events',
        'display_conditions',
        'display_actions',
        'is_enabled',
    )
    list_filter = (
        'is_enabled',
        ('event__polymorphic_ctype', create_related_filter(_('event'))),
        ('condition__polymorphic_ctype', create_related_filter(_('condition'))),
        ('action__polymorphic_ctype', create_related_filter(_('action'))),
    )
    polymorphic_list = True

    def get_queryset(self, request):
        base_queryset = super().get_queryset(request)
        return base_queryset.prefetch_related('events', 'conditions', 'actions')

    @admin.display(description=_('events'), ordering="event__polymorphic_ctype")
    def display_events(self, obj: Trigger) -> str:
        return format_html_join(
            '\n',
            '<li>{0}</li>',
            sorted((str(event).capitalize(),) for event in obj.events.all()),
        )

    @admin.display(description=_('conditions'), ordering="condition__polymorphic_ctype")
    def display_conditions(self, obj: Trigger):
        return format_html_join(
            '\n',
            '<li>{0}</li>',
            sorted((str(condition).capitalize(),) for condition in obj.conditions.all()),
        )

    @admin.display(description=_('action'), ordering="action__polymorphic_ctype")
    def display_actions(self, obj: Trigger):
        return format_html_join(
            '\n',
            '<li>{0}</li>',
            sorted((str(action).capitalize(),) for action in obj.actions.all()),
        )


@admin.register(Activity)
class ActivityActionAdmin(admin.ModelAdmin):
    list_display = 'trigger', 'user', 'last_action_datetime', 'action_count',
    list_filter = 'trigger',
    list_select_related = 'trigger', 'user',
    readonly_fields = list_display
    search_fields = tuple({
        f'=user__{User.get_email_field_name()}',
        f'=user__{User.USERNAME_FIELD}',
    })

    def has_add_permission(self, request, obj=None):
        return False
