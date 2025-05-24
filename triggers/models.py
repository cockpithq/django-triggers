from contextlib import contextmanager
import datetime
import importlib
from typing import Any, Dict, Generator, Mapping, Type
import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import JSONField
from django.dispatch import Signal
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from polymorphic.models import PolymorphicModel


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


class TriggerLog(models.Model):
    """
    Logging of all trigger processing stages
    
    This model stores information about every step in the trigger processing pipeline,
    allowing for complete visualization and debugging of the trigger execution flow.
    
    Stages in the trigger execution flow:
    
    1. Event triggered:
       * 'fire' - Initial event firing
       * 'should_be_fired' - Check if the event should be processed
    
    2. User filtering:
       * 'trigger_filter' - Trigger-level filtering of users
       * 'condition_filter' - Individual condition filtering
    
    3. Signal sending:
       * 'signal_sent' - Signal sent for a specific user
       * 'task_created' - Celery task created to handle the event
    
    4. Event handling:
       * 'handle_start' - Event handling begins
       * 'condition_check' - Individual condition satisfaction check for a specific user
       * 'action_perform' - Action execution
       
    The 'run_id' field connects all log entries from a single trigger execution,
    making it possible to trace the complete processing path from event firing to action execution.
    """
    
    ENTITY_TYPES = [
        ("event", _("Event")),
        ("trigger", _("Trigger")),
        ("condition", _("Condition")), 
        ("action", _("Action")),
    ]
    
    STAGES = [
        ("fire", _("Fire initiated")),
        ("should_be_fired", _("Should be fired check")),
        ("trigger_filter", _("Trigger filtering")),
        ("condition_filter", _("Condition filtering")),
        ("signal_sent", _("Signal sent")),
        ("task_created", _("Task created")),
        ("handle_start", _("Handle start")),
        ("condition_check", _("Condition satisfied check")),
        ("action_perform", _("Action perform")),
    ]
    
    timestamp = models.DateTimeField(_("timestamp"), auto_now_add=True)
    run_id = models.UUIDField(_("run ID"), db_index=True, help_text=_("Trigger execution identifier"))
    entity_type = models.CharField(_("entity type"), max_length=20, choices=ENTITY_TYPES)
    entity_id = models.PositiveIntegerField(_("entity ID"))
    entity_class_path = models.CharField(_("entity class path"), max_length=255)
    entity_name = models.CharField(_("entity name"), max_length=255, blank=True)
    trigger = models.ForeignKey(
        Trigger, 
        on_delete=models.CASCADE, 
        related_name="logs",
        verbose_name=_("trigger")
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="trigger_logs",
        null=True, blank=True,
        verbose_name=_("user")
    )
    stage = models.CharField(_("stage"), max_length=30, choices=STAGES)
    result = models.BooleanField(_("result"), null=True, blank=True)
    details = JSONField(_("details"), blank=True, null=True, default=dict)
    
    class Meta:
        verbose_name = _("trigger log")
        verbose_name_plural = _("trigger logs")
        ordering = ["-timestamp"]
        
    def __str__(self):
        return f"{self.get_stage_display()} - {self.entity_name} ({self.timestamp.strftime('%Y-%m-%d %H:%M:%S')})"

    def get_entity_object(self):
        """
        Returns the entity object using the stored class path and ID
        """
        try:
            # Split path into module and class name
            module_path, class_name = self.entity_class_path.rsplit(".", 1)
            
            # Import module and get class
            module = importlib.import_module(module_path)
            entity_class = getattr(module, class_name)
            
            # Return the object
            return entity_class.objects.get(pk=self.entity_id)
        except (ImportError, AttributeError, ValueError):
            return None
        except models.ObjectDoesNotExist:
            # Object has been deleted
            return None


def log_trigger_event(entity, entity_type, stage, trigger=None, user=None, result=None, details=None, run_id=None):
    """
    Log a trigger event
    
    :param entity: Entity object (Event, Trigger, Condition, Action)
    :param entity_type: Entity type ('event', 'trigger', 'condition', 'action')
    :param stage: Processing stage
    :param trigger: Trigger (if not contained in entity)
    :param user: User (if applicable)
    :param result: Operation result
    :param details: Additional details (dictionary)
    :param run_id: Execution identifier. If not specified, a new one is generated.
    """
    # Improved trigger detection logic
    if trigger is None:
        # If this is a trigger, use it directly
        if entity_type == "trigger" and isinstance(entity, Trigger):
            trigger = entity
        # If the entity has a trigger attribute and it's a Trigger model
        elif hasattr(entity, "trigger") and isinstance(entity.trigger, Trigger):
            trigger = entity.trigger
        # If we have an attribute related to the trigger, try to use it
        elif hasattr(entity, "trigger_id") and entity.trigger_id:
            try:
                trigger = Trigger.objects.get(pk=entity.trigger_id)
            except Trigger.DoesNotExist:
                pass
    # Check that the trigger is defined
    if trigger is None:
        # Can throw an exception or just add information about missing trigger to details
        return None
    
    if not details:
        details = {}
    
    # If execution identifier not provided, generate a new one
    if run_id is None:
        run_id = uuid.uuid4()
    
    # Get string path to the object class
    entity_class = entity.__class__
    entity_class_path = f"{entity_class.__module__}.{entity_class.__name__}"

    # If needed to verify or fix, probably better
    TriggerLog.objects.create(
        run_id=run_id,
        entity_type=entity_type,
        entity_id=entity.pk,
        entity_class_path=entity_class_path,
        entity_name=str(entity),
        trigger=trigger,
        user=user,
        stage=stage,
        result=result,
        details=details
    )
    
    return run_id  # Return run_id for use in subsequent calls
