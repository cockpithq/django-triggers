from typing import Any, Dict

from django.contrib.auth.models import User
from django.db import models, transaction
from django.dispatch import receiver
from django.dispatch.dispatcher import Signal
from django.template import Context, Template
from django.utils.translation import gettext_lazy as _

from triggers.models import Action, Event


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

    completed = Signal()

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
    pass


@receiver(Task.completed)
def on_task_completed(sender, task: Task, **kwargs):
    event: TaskCompletedEvent
    for event in TaskCompletedEvent.objects.all():
        transaction.on_commit(lambda: event.fire_single(task.user_id))


class SendEmailAction(Action):  # type: ignore[django-manager-missing]
    subject = models.CharField(_('subject'), max_length=256)
    message = models.TextField(_('message'), help_text=_('You can use the Django template language.'))

    def perform(self, user: User, context: Dict[str, Any]):
        context['tasks'] = user.tasks.all()
        message_template = Template(self.message)
        rendered_message = message_template.render(Context(context))
        user.email_user(self.subject, rendered_message)
