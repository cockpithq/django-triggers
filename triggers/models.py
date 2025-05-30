from contextlib import contextmanager
import datetime
from typing import Any, Dict, Generator, Mapping, Type

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import JSONField
from django.dispatch import Signal
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from polymorphic.models import PolymorphicModel

from triggers.log import log_trigger_event


User = get_user_model()


def get_model_name(model: Type[models.Model]) -> str:
    return str(model._meta.verbose_name)  # noqa


class Trigger(PolymorphicModel):
    name = models.CharField(_("name"), max_length=64, unique=True)
    is_enabled = models.BooleanField(_("enabled"), default=False)

    class Meta:
        verbose_name = _("trigger")
        verbose_name_plural = _("triggers")

    def __str__(self):
        return self.name

    @property
    def is_active(self) -> bool:
        return self.is_enabled and self.actions.exists()

    def filter_user_queryset(self, user_queryset: models.QuerySet) -> models.QuerySet:
        if not self.is_active:
            log_trigger_event(
                entity=self,
                entity_type="trigger",
                stage="trigger_filter",
                result=False,
                details={"reason": "Trigger not active"}
            )
            return user_queryset.none()
        
        filtered_queryset = user_queryset
        condition: Condition
        for condition in self.conditions.all():
            before_has_users = filtered_queryset.exists()
            filtered_queryset = condition.filter_user_queryset(filtered_queryset)
            after_has_users = filtered_queryset.exists()
            
            log_trigger_event(
                entity=condition,
                entity_type="condition",
                stage="condition_filter",
                trigger=self,
                result=after_has_users,
                details={
                    "condition_type": condition.__class__.__name__,
                    "has_users_before": before_has_users,
                    "has_users_after": after_has_users
                }
            )
        
        has_users = filtered_queryset.exists()
        log_trigger_event(
            entity=self,
            entity_type="trigger",
            stage="trigger_filter",
            result=has_users
        )
        
        return filtered_queryset

    def on_event(self, user, context: Mapping[str, Any]):
        all_conditions_satisfied = True
        condition_results = {}
        
        for condition in self.conditions.all():
            is_satisfied = condition.is_satisfied(user)
            condition_results[condition.__class__.__name__] = is_satisfied
            
            log_trigger_event(
                entity=condition,
                entity_type="condition",
                stage="condition_check",
                trigger=self,
                user=user,
                result=is_satisfied
            )
            
            if not is_satisfied:
                all_conditions_satisfied = False
        
        log_trigger_event(
            entity=self,
            entity_type="trigger",
            stage="condition_check",
            user=user,
            result=all_conditions_satisfied,
            details={"condition_results": condition_results}
        )
        
        if user and all_conditions_satisfied:
            with Activity.lock(user, self):
                for action in self.actions.all():
                    try:
                        action.perform(user, context)
                        log_trigger_event(
                            entity=action,
                            entity_type="action",
                            stage="action_perform",
                            trigger=self,
                            user=user,
                            result=True
                        )
                    except Exception as e:
                        log_trigger_event(
                            entity=action,
                            entity_type="action",
                            stage="action_perform",
                            trigger=self,
                            user=user,
                            result=False,
                            details={"error": str(e)}
                        )
                        raise


class Activity(PolymorphicModel):
    trigger = models.ForeignKey(
        to=Trigger,
        on_delete=models.CASCADE,
        related_name="activities",
        related_query_name="activity",
        verbose_name=_("trigger"),
    )
    user = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trigger_activities",
        related_query_name="trigger_activity",
        verbose_name=_("user"),
    )
    last_action_datetime = models.DateTimeField(_("last action"), blank=True, null=True)
    action_count = models.PositiveIntegerField(_("actions"), default=0)

    class Meta:
        verbose_name = _("activity")
        verbose_name_plural = _("activities")
        unique_together = (("trigger", "user"),)

    def __str__(self) -> str:
        return f"{self.trigger} - {self.user}"

    class Cancel(Exception):
        pass

    @classmethod
    @contextmanager
    def lock(cls, user, trigger: Trigger) -> Generator["Activity", None, None]:
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
        related_name="actions",
        related_query_name="action",
        verbose_name=_("trigger"),
        null=True
    )

    class Meta:
        verbose_name = _("action")
        verbose_name_plural = _("actions")

    def __str__(self) -> str:
        return get_model_name(self.__class__)

    def perform(self, user, context: Dict[str, Any]):
        raise NotImplementedError()


class Event(PolymorphicModel):
    trigger = models.ForeignKey(
        Trigger,
        verbose_name=_("trigger"),
        on_delete=models.CASCADE,
        related_name="events",
        related_query_name="event",
    )
    delay = models.DurationField(
        _("delay"),
        default=datetime.timedelta(),
        blank=True,
        help_text=_(
            "Delay from the moment when the event "
            "actually happened until it should be handled."
        ),
    )
    fired = Signal()

    class Meta:
        verbose_name = _("event")
        verbose_name_plural = _("events")

    def __str__(self) -> str:
        return get_model_name(self.__class__)

    def should_be_fired(self, **kwargs) -> bool:
        return True

    def get_user_context(self, user, context: Mapping[str, Any]) -> Dict[str, Any]:
        user_context = {"user": user}
        user_context.update(context)
        return user_context

    def fire(self, user_queryset: models.QuerySet, **kwargs) -> None:
        # Попытаемся определить пользователя из queryset для логирования
        user_for_logging = None
        if user_queryset.count() == 1:
            user_for_logging = user_queryset.first()
        
        run_id = log_trigger_event(
            entity=self, 
            entity_type="event",
            stage="fire",
            user=user_for_logging,
            details={"kwargs": str(kwargs), "user_count": user_queryset.count()}
        )
        
        should_fire = self.should_be_fired(**kwargs)
        log_trigger_event(
            entity=self, 
            entity_type="event",
            stage="should_be_fired",
            user=user_for_logging,
            result=should_fire,
            details={"kwargs": str(kwargs)},
            run_id=run_id
        )
        
        if should_fire:
            prefiltered_user_queryset = self.trigger.filter_user_queryset(user_queryset)
            for user_pk in prefiltered_user_queryset.values_list("pk", flat=True).iterator():
                log_trigger_event(
                    entity=self, 
                    entity_type="event",
                    stage="signal_sent",
                    user=User.objects.get(pk=user_pk),
                    details={"kwargs": str(kwargs)},
                    run_id=run_id
                )
                kwargs_with_run_id = kwargs.copy()
                kwargs_with_run_id["_run_id"] = str(run_id)
                self.fired.send(self.__class__, event=self, user_pk=user_pk, **kwargs_with_run_id)

    def fire_single(self, user_pk: Any, **kwargs):
        self.fire(User.objects.filter(pk=user_pk), **kwargs)

    def handle(self, user_pk, **context):
        user_queryset = self.trigger.filter_user_queryset(User.objects.filter(pk=user_pk))
        user = user_queryset.first()
        if user:
            log_trigger_event(
                entity=self, 
                entity_type="event",
                stage="handle_start",
                user=user,
                result=True,
                details={"user_passed_filter": True}
            )
            user_context = self.get_user_context(user, context)
            self.trigger.on_event(user, user_context)


class Condition(PolymorphicModel):
    trigger = models.ForeignKey(
        Trigger,
        verbose_name=_("trigger"),
        on_delete=models.CASCADE,
        related_name="conditions",
        related_query_name="condition",
    )

    class Meta:
        verbose_name = _("condition")
        verbose_name_plural = _("conditions")

    def __str__(self) -> str:
        return get_model_name(self.__class__)

    def is_satisfied(self, user) -> bool:
        return True

    def filter_user_queryset(self, user_queryset: models.QuerySet) -> models.QuerySet:
        return user_queryset


class ActionCountCondition(Condition):  # type: ignore[django-manager-missing]
    limit = models.PositiveIntegerField(
        _("action count limit"),
        default=1,
        help_text=_("Maximal number of actions that can be triggered for the user."),
        validators=[MinValueValidator(1)],
    )

    class Meta:
        verbose_name = _("action count")
        verbose_name_plural = _("action count")

    def __str__(self):
        return f"{super().__str__()} no more than {self.limit}"

    def filter_user_queryset(self, user_queryset: models.QuerySet) -> models.QuerySet:
        return super().filter_user_queryset(user_queryset).exclude(
            trigger_activity__trigger=self.trigger,
            trigger_activity__action_count__gte=self.limit,
        )


class ActionFrequencyCondition(Condition):  # type: ignore[django-manager-missing]
    limit = models.DurationField(
        _("action frequency limit"),
        default=datetime.timedelta(days=30),
        help_text=_(
            "Minimal period of time that should run out "
            "before the next action can be triggered."
        ),
    )

    class Meta:
        verbose_name = _("action frequency")
        verbose_name_plural = _("action frequency")

    def __str__(self):
        return f"{super().__str__()} no less than {self.limit}"

    def filter_user_queryset(self, user_queryset: models.QuerySet) -> models.QuerySet:
        return super().filter_user_queryset(user_queryset).exclude(
            trigger_activity__trigger=self.trigger,
            trigger_activity__last_action_datetime__gt=timezone.now() - self.limit,
        )



