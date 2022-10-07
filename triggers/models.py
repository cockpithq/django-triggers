from contextlib import contextmanager
from typing import Any, Generator, Mapping, Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from polymorphic.models import PolymorphicModel

User = get_user_model()


class Trigger(PolymorphicModel):
    name = models.CharField(_('name'), max_length=64, unique=True)
    is_enabled = models.BooleanField(_('enabled'), default=False)
    number_limit = models.PositiveIntegerField(
        _('number limit'),
        default=1,
        help_text=_('Maximal number of actions that can be triggered for the user.'),
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
    )
    frequency_limit = models.DurationField(
        _('frequency limit'),
        default=timezone.timedelta(days=30),
        help_text=_('Minimal period of time that should run out before the next action can be triggered.'),
        null=True,
        blank=True,
    )

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
            user_context = event.get_user_context(user, context)
            with Activity.lock(user, self) as activity:
                if self.number_limit is not None:
                    if activity.execution_count >= self.number_limit:
                        raise Activity.Cancel()
                if self.frequency_limit is not None and activity.last_execution_datetime:
                    if timezone.now() - activity.last_execution_datetime < self.frequency_limit:
                        raise Activity.Cancel()
                self.action.perform(user, user_context)


class Activity(PolymorphicModel):
    trigger = models.ForeignKey(
        to=Trigger,
        on_delete=models.CASCADE,
        related_name='activities',
        related_query_name='activity',
        verbose_name=_('trigger'),
    )
    user = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='trigger_activities',
        related_query_name='trigger_activity',
        verbose_name=_('user'),
    )
    last_execution_datetime = models.DateTimeField(_('executed at'), blank=True, null=True)
    execution_count = models.PositiveIntegerField(_('number of executions'), default=0)

    class Meta:
        verbose_name = _('trigger activity')
        verbose_name_plural = _('trigger activities')
        unique_together = (('trigger', 'user'),)

    class Cancel(Exception):
        pass

    @classmethod
    @contextmanager
    def lock(cls, user, trigger: Trigger) -> Generator['Activity', None, None]:
        activity, _created = trigger.activities.get_or_create(user=user)
        with transaction.atomic():
            activity = Activity.objects.filter(id=activity.id).select_for_update().get()
            try:
                yield activity
            except cls.Cancel:
                pass
            else:
                activity.execution_count += 1
                activity.last_execution_datetime = timezone.now()
                activity.save()


class Action(PolymorphicModel):
    trigger = models.OneToOneField(
        to=Trigger,
        on_delete=models.CASCADE,
        related_name='action',
        verbose_name=_('trigger'),
    )

    class Meta:
        verbose_name = _('action')
        verbose_name_plural = _('actions')

    def __str__(self) -> str:
        return str(self.__class__._meta.verbose_name)  # noqa

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
