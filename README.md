# django-triggers [![Latest Version][latest-version-image]][latest-version-link]
[![Test Status][test-status-image]][test-status-link]
[![codecov][codecov-image]][codecov-link]
[![Python Support][python-support-image]][python-support-link]

`django-triggers` is intended for implementing event-based business logic configurable through the Django admin site.

## Install

```shell
pip install dj-triggers
```

```python
INSTALLED_APPS = [
    ...
    "polymorphic",
    "triggers",
    ...
]
```


### Prerequisites 

Celery is required to be setup in your project.

## Quickstart

Let's consider a simple tasks app with a model `Task` and we want to email a user when a task is completed.

1. Add event, action and condition models into your app's models.py

By doing this, we separate the development of the trigger components from their configuration within the Django admin panel. This ensures a more modular and manageable approach to building and configuring triggers.

The full code example is available in [tests directory](https://github.com/cockpithq/django-triggers/tree/main/tests/app).
```python
from django.dispatch import receiver, Signal
from django.contrib.auth.models import User
from django.db import models, transaction

from triggers.models import Action,  Event


# Our domain model
class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=128)
    is_completed = models.BooleanField(default=False, db_index=True, editable=False)
    is_important = models.BooleanField(default=False)

    completed = Signal()

    def complete(self):
        if not self.is_completed:
            self.is_completed = True
            self.save()
            transaction.on_commit(lambda: self.completed.send(sender=self.__class__, task=self))


# At first, implement an Event which will trigger the notification.
class TaskCompletedEvent(Event):
    # By setting the following `important_only` field through the Django admin site 
    # we can configure what tasks (all or important only) we want to notify the users about.
    important_only = models.BooleanField(
        default=False, 
        help_text='Fire the event for important tasks only if checked.',
    ) 

    def should_be_fired(self, **kwargs) -> bool:
        if self.important_only:
            return Task.objects.filter(id=kwargs['task_id'], is_important=True).exists()
        return True


# Then we need to fire `TaskCompletedEvent` when a task is marked as completed.
@receiver(Task.completed)
def on_task_completed(sender, task: Task, **kwargs):
    for event in TaskCompletedEvent.objects.all():
        transaction.on_commit(lambda: event.fire_single(task.user_id, task_id=task.id))


# At the end, create an Action implementing email notification.
class SendEmailAction(Action):
    subject = models.CharField(max_length=256)
    message = models.TextField()

    def perform(self, user: User, context: Dict[str, Any]):
        user.email_user(self.subject, self.message)
```

2. Makemigrations and migrate
```shell
python manage.py makemigrations
python manage.py migrate
```

3. Add trigger on the Django admin site

Don't forget to enable it :)

<img width="557" alt="SCR-20230315-sooo" src="https://user-images.githubusercontent.com/101798/225434592-db566401-873a-4698-9292-79e51ddec5ee.png">

4. Use the trigger!

```python
task = Task.objects.get(id=...)  # Get your task
task.complete()  # And mark it as completed
```

You may also trigger it manually from the Django admin site if you're checking the test app example.

<img width="369" alt="image" src="https://user-images.githubusercontent.com/101798/225565474-8d594a19-03b7-4501-b995-d66f45acdf64.png">

## Development

### Run a django-admin command, e.g. `makemigrations`
```shell
poetry run python -m django makemigrations --settings=tests.app.settings
```

### Run isort
```shell
poetry run isort triggers tests
```
### Run flake8
```shell
poetry run flake8 triggers tests
```
### Run mypy
```shell
poetry run mypy triggers tests
```
### Run pytest
```shell
poetry run pytest
```

[latest-version-image]: https://img.shields.io/pypi/v/dj-triggers.svg
[latest-version-link]: https://pypi.org/project/dj-triggers/
[codecov-image]: https://codecov.io/gh/cockpithq/django-triggers/branch/main/graph/badge.svg?token=R5CG3VJI73
[codecov-link]: https://codecov.io/gh/cockpithq/django-triggers
[test-status-image]: https://github.com/cockpithq/django-triggers/actions/workflows/test.yml/badge.svg
[test-status-link]: https://github.com/cockpithq/django-triggers/actions/workflows/test.yml
[python-support-image]: https://img.shields.io/pypi/pyversions/dj-triggers.svg
[python-support-link]: https://pypi.org/project/dj-triggers/
