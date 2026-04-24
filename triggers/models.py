from contextlib import contextmanager
import datetime
from typing import Any, Dict, Generator, Mapping, Optional, Type
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.dispatch import Signal
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from polymorphic.models import PolymorphicModel

from triggers.constants import (
    RESULT_ACTION_FAILED,
    RESULT_CONDITIONS_FAILED,
    RESULT_SKIPPED,
    RESULT_SUCCEEDED,
)


def _send_trigger_signal(
    signal: Signal,
    sender: type,
    event: 'Event',
    run_id: str,
    **kwargs,
) -> None:
    """Send a trigger signal robustly so observers never break trigger execution."""
    signal.send_robust(sender=sender, event=event, run_id=run_id, **kwargs)


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
        return self.is_enabled and self.actions.exists()

    def filter_user_queryset(self, user_queryset: models.QuerySet) -> models.QuerySet:
        if not self.is_active:
            return user_queryset.none()
        condition: Condition
        for condition in self.conditions.all():
            user_queryset = condition.filter_user_queryset(user_queryset)
        return user_queryset

    def on_event(self, user, context: Mapping[str, Any], event: 'Event', run_id: str):
        is_allowed = True
        failed_condition = None
        for condition in self.conditions.all():
            if not condition.is_satisfied(user):
                is_allowed = False
                if failed_condition is None:
                    failed_condition = condition
        _send_trigger_signal(
            Condition.checked,
            sender=self.__class__,
            event=event,
            run_id=run_id,
            trigger=self,
            user_pk=user.pk,
            is_satisfied=is_allowed,
            failed_condition=failed_condition,
        )
        if user and is_allowed:
            action_error: Optional[Exception] = None
            failed_action = None
            try:
                with Activity.lock(user, self):
                    for action in self.actions.all():
                        try:
                            action.perform(user, context)
                        except Exception as error:
                            action_error = error
                            failed_action = action
                            raise
                        else:
                            _send_trigger_signal(
                                Action.performed,
                                sender=self.__class__,
                                event=event,
                                run_id=run_id,
                                trigger=self,
                                user_pk=user.pk,
                                action=action,
                            )
            except Exception:
                pass  # stored in action_error; signals emitted below outside the atomic block

            if action_error is not None:
                _send_trigger_signal(
                    Action.failed,
                    sender=self.__class__,
                    event=event,
                    run_id=run_id,
                    trigger=self,
                    user_pk=user.pk,
                    action=failed_action,
                    error=action_error,
                )
                _send_trigger_signal(
                    Event.handled,
                    sender=self.__class__,
                    event=event,
                    run_id=run_id,
                    trigger=self,
                    user_pk=user.pk,
                    result=RESULT_ACTION_FAILED,
                )
                raise action_error
            _send_trigger_signal(
                Event.handled,
                sender=self.__class__,
                event=event,
                run_id=run_id,
                trigger=self,
                user_pk=user.pk,
                result=RESULT_SUCCEEDED,
            )
        elif user:
            _send_trigger_signal(
                Event.handled,
                sender=self.__class__,
                event=event,
                run_id=run_id,
                trigger=self,
                user_pk=user.pk,
                result=RESULT_CONDITIONS_FAILED,
            )


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

    def __str__(self) -> str:
        return f'{self.trigger} - {self.user}'

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
    trigger = models.ForeignKey(
        to=Trigger,
        on_delete=models.CASCADE,
        related_name='actions',
        related_query_name='action',
        verbose_name=_('trigger'),
        null=True
    )
    performed = Signal()
    failed = Signal()

    class Meta:
        verbose_name = _('action')
        verbose_name_plural = _('actions')

    def __str__(self) -> str:
        return get_model_name(self.__class__)

    def perform(self, user, context: Dict[str, Any]):
        raise NotImplementedError()


class Event(PolymorphicModel):
    trigger = models.ForeignKey(
        Trigger,
        verbose_name=_('trigger'),
        on_delete=models.CASCADE,
        related_name='events',
        related_query_name='event',
    )
    delay = models.DurationField(
        _('delay'),
        default=datetime.timedelta(),
        blank=True,
        help_text=_(
            'Delay from the moment when the event '
            'actually happened until it should be handled.'
        ),
    )
    fired = Signal()
    received = Signal()
    user_resolved = Signal()
    handled = Signal()

    class Meta:
        verbose_name = _('event')
        verbose_name_plural = _('events')

    def __str__(self) -> str:
        return get_model_name(self.__class__)

    def should_be_fired(self, **kwargs) -> bool:
        return True

    def get_user_context(self, user, context: Mapping[str, Any]) -> Dict[str, Any]:
        user_context = {'user': user}
        user_context.update(context)
        return user_context

    def fire(self, user_queryset: models.QuerySet, **kwargs) -> None:
        if self.should_be_fired(**kwargs):
            prefiltered_user_queryset = self.trigger.filter_user_queryset(user_queryset)
            for user_pk in prefiltered_user_queryset.values_list('pk', flat=True).iterator():
                run_id = uuid.uuid4().hex
                _send_trigger_signal(
                    Event.fired,
                    sender=self.__class__,
                    event=self,
                    run_id=run_id,
                    user_pk=user_pk,
                    **kwargs,
                )

    def fire_single(self, user_pk: Any, **kwargs):
        self.fire(User.objects.filter(pk=user_pk), **kwargs)

    def handle(self, user_pk, run_id: str = "", **context):
        run_id = run_id or uuid.uuid4().hex
        _send_trigger_signal(
            self.received,
            sender=self.__class__,
            event=self,
            run_id=run_id,
            user_pk=user_pk,
            **context,
        )
        # Filter by conditions again (conditions may have changed between fire() and handle())
        user_queryset = self.trigger.filter_user_queryset(User.objects.filter(pk=user_pk))
        user = user_queryset.first()
        _send_trigger_signal(
            self.user_resolved,
            sender=self.__class__,
            event=self,
            run_id=run_id,
            user_pk=user_pk,
            is_found=bool(user),
        )
        if user:
            user_context = self.get_user_context(user, context)
            self.trigger.on_event(user, context=user_context, event=self, run_id=run_id)
        else:
            _send_trigger_signal(
                self.handled,
                sender=self.__class__,
                event=self,
                run_id=run_id,
                trigger=self.trigger,
                user_pk=user_pk,
                result=RESULT_SKIPPED,
            )


class Condition(PolymorphicModel):
    trigger = models.ForeignKey(
        Trigger,
        verbose_name=_('trigger'),
        on_delete=models.CASCADE,
        related_name='conditions',
        related_query_name='condition',
    )
    checked = Signal()

    class Meta:
        verbose_name = _('condition')
        verbose_name_plural = _('conditions')

    def __str__(self) -> str:
        return get_model_name(self.__class__)

    def is_satisfied(self, user) -> bool:
        return True

    def filter_user_queryset(self, user_queryset: models.QuerySet) -> models.QuerySet:
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
        return f'{super().__str__()} no more than {self.limit}'

    def filter_user_queryset(self, user_queryset: models.QuerySet) -> models.QuerySet:
        return super().filter_user_queryset(user_queryset).exclude(
            trigger_activity__trigger=self.trigger,
            trigger_activity__action_count__gte=self.limit,
        )


class ActionFrequencyCondition(Condition):  # type: ignore[django-manager-missing]
    limit = models.DurationField(
        _('action frequency limit'),
        default=datetime.timedelta(days=30),
        help_text=_(
            'Minimal period of time that should run out '
            'before the next action can be triggered.'
        ),
    )

    class Meta:
        verbose_name = _('action frequency')
        verbose_name_plural = _('action frequency')

    def __str__(self):
        return f'{super().__str__()} no less than {self.limit}'

    def filter_user_queryset(self, user_queryset: models.QuerySet) -> models.QuerySet:
        return super().filter_user_queryset(user_queryset).exclude(
            trigger_activity__trigger=self.trigger,
            trigger_activity__last_action_datetime__gt=timezone.now() - self.limit,
        )
