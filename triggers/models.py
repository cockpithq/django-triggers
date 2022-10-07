from typing import Any, Mapping, Optional

from django.contrib.auth import get_user_model
from django.db import models, transaction
from django.utils.translation import gettext_lazy as _
from polymorphic.models import PolymorphicModel

User = get_user_model()


class Trigger(PolymorphicModel):
    name = models.CharField(_('name'), max_length=64, unique=True)
    is_enabled = models.BooleanField(_('enabled'), default=False)

    class Meta:
        verbose_name = _('action')
        verbose_name_plural = _('actions')

    def __str__(self):
        return self.name

    def filter_user_queryset(self, user_queryset: models.QuerySet) -> models.QuerySet:
        condition: Condition
        for condition in self.conditions.all():
            user_queryset = condition.filter_user_queryset(user_queryset)
        return user_queryset

    def iter_users(self, user_queryset: models.QuerySet):
        for user in self.filter_user_queryset(user_queryset).iterator():
            if all(condition.is_satisfied(user) for condition in self.conditions.all()):
                yield user

    def on_event(self, event: 'Event', user_queryset: models.QuerySet, context: Mapping[str, Any]):
        if not hasattr(self, 'action'):
            return
        for user in self.iter_users(user_queryset):
            self.action.perform_and_track(user, event, context)


class Action(PolymorphicModel):
    trigger = models.OneToOneField(Trigger, on_delete=models.CASCADE, related_name='action')

    @transaction.atomic
    def perform_and_track(self, user, event: 'Event', context: Mapping[str, Any]):
        user_context = event.get_user_context(user, context)
        self.perform(user, user_context)

    def perform(self, user, context: Mapping[str, Any]):
        raise NotImplementedError()


class Event(PolymorphicModel):
    trigger = models.ForeignKey(
        Trigger,
        verbose_name=_('trigger'),
        on_delete=models.CASCADE,
        related_name='events',
        related_query_name='event',
    )

    class Meta:
        verbose_name = _('event')
        verbose_name_plural = _('events')

    def __str__(self) -> str:
        return str(self.__class__._meta.verbose_name)  # noqa

    def should_be_fired(self, **kwargs) -> bool:
        return True

    def get_user_context(self, user, context) -> Mapping[str, Any]:
        user_context = {'user': user}
        user_context.update(context)
        return user_context

    def fire(self, user_queryset: models.QuerySet, **kwargs) -> None:
        if self.trigger.is_enabled and self.should_be_fired(**kwargs):
            self.trigger.on_event(self, user_queryset, kwargs)

    def fire_single(self, user_pk: Any, **kwargs):
        self.fire(User.objects.filter(pk=user_pk), **kwargs)


class Condition(PolymorphicModel):
    trigger = models.ForeignKey(
        Trigger,
        verbose_name=_('trigger'),
        on_delete=models.CASCADE,
        related_name='conditions',
        related_query_name='condition',
    )

    class Meta:
        verbose_name = _('condition')
        verbose_name_plural = _('conditions')

    @property
    def filter_users_q(self) -> Optional[models.Q]:
        return None

    @property
    def exclude_users_q(self) -> Optional[models.Q]:
        return None

    def is_satisfied(self, user) -> bool:
        return True

    def filter_user_queryset(self, user_queryset: models.QuerySet) -> models.QuerySet:
        if self.filter_users_q:
            user_queryset = user_queryset.filter(self.filter_users_q)
        if self.exclude_users_q:
            user_queryset = user_queryset.exclude(self.exclude_users_q)
        return user_queryset
