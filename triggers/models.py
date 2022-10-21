from contextlib import contextmanager
from typing import Any, Generator, Mapping, Optional, Type

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.dispatch import Signal
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from polymorphic.models import PolymorphicModel

User = get_user_model()


def get_model_name(model: Type[models.Model]) -> str:
    return str(model._meta.verbose_name)  # noqa


class Trigger(PolymorphicModel):
    name = models.CharField(_('name'), max_length=64, unique=True)
    is_enabled = models.BooleanField(_('enabled'), default=False)

    class Meta:
        verbose_name = _('trigger')
        verbose_name_plural = _('triggers')

    def __str__(self):
        return self.name

    @property
    def is_active(self) -> bool:
        return self.is_enabled and hasattr(self, 'action')

    def filter_user_queryset(self, user_queryset: models.QuerySet) -> models.QuerySet:
        if not self.is_active:
            return user_queryset.none()
        for condition in self.conditions.all():
            user_queryset = condition.filter_user_queryset(user_queryset)
        return user_queryset

    def on_event(self, user, context: Mapping[str, Any]):
        if user and all(condition.is_satisfied(user) for condition in self.conditions.all()):
            with Activity.lock(user, self):
                self.action.perform(user, context)


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
    last_action_datetime = models.DateTimeField(_('last action'), blank=True, null=True)
    action_count = models.PositiveIntegerField(_('actions'), default=0)

    class Meta:
        verbose_name = _('activity')
        verbose_name_plural = _('activities')
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
                activity.action_count += 1
                activity.last_action_datetime = timezone.now()
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
        return get_model_name(self.__class__)

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
    fired = Signal()

    class Meta:
        verbose_name = _('event')
        verbose_name_plural = _('events')

    def __str__(self) -> str:
        return get_model_name(self.__class__)

    def should_be_fired(self, **kwargs) -> bool:
        return True

    def get_user_context(self, user, context) -> Mapping[str, Any]:
        user_context = {'user': user}
        user_context.update(context)
        return user_context

    def fire(self, user_queryset: models.QuerySet, **kwargs) -> None:
        if self.should_be_fired(**kwargs):
            prefiltered_user_queryset = self.trigger.filter_user_queryset(user_queryset)
            for user_pk in prefiltered_user_queryset.values_list('pk', flat=True).iterator():
                self.fired.send(self.__class__, event=self, user_pk=user_pk, **kwargs)

    def fire_single(self, user_pk: Any, **kwargs):
        self.fire(User.objects.filter(pk=user_pk), **kwargs)

    def handle(self, user_pk, **context):
        user_queryset = self.trigger.filter_user_queryset(User.objects.filter(pk=user_pk))
        user = user_queryset.first()
        if user:
            user_context = self.get_user_context(user, context)
            self.trigger.on_event(user, user_context)


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

    def __str__(self) -> str:
        return get_model_name(self.__class__)

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


class ActionCountCondition(Condition):  # type: ignore[django-manager-missing]
    limit = models.PositiveIntegerField(
        _('action count limit'),
        default=1,
        help_text=_('Maximal number of actions that can be triggered for the user.'),
        validators=[MinValueValidator(1)],
    )

    class Meta:
        verbose_name = _('action count')
        verbose_name_plural = _('action count')

    def __str__(self):
        return f'{super().__str__()} less than {self.limit}'

    @property
    def exclude_users_q(self) -> Optional[models.Q]:
        return models.Q(
            trigger_activity__trigger=self.trigger,
            trigger_activity__action_count__gte=self.limit,
        )


class ActionFrequencyCondition(Condition):  # type: ignore[django-manager-missing]
    limit = models.DurationField(
        _('action frequency limit'),
        default=timezone.timedelta(days=30),
        help_text=_('Minimal period of time that should run out before the next action can be triggered.'),
    )

    class Meta:
        verbose_name = _('action frequency')
        verbose_name_plural = _('action frequency')

    def __str__(self):
        return f'{super().__str__()} less than {self.limit}'

    @property
    def exclude_users_q(self) -> Optional[models.Q]:
        return models.Q(
            trigger_activity__trigger=self.trigger,
            trigger_activity__last_action_datetime__gt=timezone.now() - self.limit,
        )
