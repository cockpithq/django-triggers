from typing import Any, Dict, Optional

from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models import Q
from django.dispatch import receiver
from django.dispatch.dispatcher import Signal
from django.template import Context, Template
from django.utils.translation import gettext_lazy as _

from triggers.models import Action, Condition, Event


class TaskQuerySet(models.QuerySet):
    def filter_uncompleted(self, *args, **kwargs):
        return self.filter(is_completed=False).filter(*args, **kwargs)


class Task(models.Model):
    user = models.ForeignKey(
        to=User,
        on_delete=models.CASCADE,
        verbose_name=_('user'),
        related_name='tasks',
        related_query_name='task',
    )
    name = models.CharField(_('name'), max_length=128)
    is_completed = models.BooleanField(_('completed'), default=False, db_index=True)
    is_important = models.BooleanField(_('important'), default=False)

    completed = Signal()

    objects = TaskQuerySet.as_manager()  # type: ignore[django-manager-missing]

    class Meta:
        verbose_name = _('task')
        verbose_name_plural = _('tasks')

    def __str__(self):
        return self.name

    def complete(self):
        if not self.is_completed:
            self.is_completed = True
            self.save()
            self.completed.send(sender=self.__class__, task=self)


class TaskCompletedEvent(Event):  # type: ignore[django-manager-missing]
    important_only = models.BooleanField(_('important only'), default=False)

    def __str__(self):
        if self.important_only:
            return f'important {super().__str__()}'
        return super().__str__()

    def should_be_fired(self, **kwargs) -> bool:
        if self.important_only:
            return Task.objects.filter(id=kwargs['task_id'], is_important=True).exists()
        return True

    def get_user_context(self, user, context) -> Dict[str, Any]:
        user_context = super().get_user_context(user, context)
        task: Task = Task.objects.get(id=context['task_id'])
        user_context.update({'task': task})
        return user_context


@receiver(Task.completed)
def on_task_completed(sender, task: Task, **kwargs):
    event: TaskCompletedEvent
    for event in TaskCompletedEvent.objects.all():
        transaction.on_commit(lambda: event.fire_single(task.user_id, task_id=task.id))


class ClockEvent(Event):  # type: ignore[django-manager-missing]
    pass


class HasUncompletedTaskCondition(Condition):  # type: ignore[django-manager-missing]
    @property
    def filter_users_q(self) -> Optional[Q]:
        return Q(task__is_completed=False)


class SendEmailAction(Action):  # type: ignore[django-manager-missing]
    subject = models.CharField(_('subject'), max_length=256)
    message = models.TextField(_('message'), help_text=_('You can use the Django template language.'))

    def perform(self, user: User, context: Dict[str, Any]):
        message_template = Template(self.message)
        rendered_message = message_template.render(Context(context))
        user.email_user(self.subject, rendered_message)
