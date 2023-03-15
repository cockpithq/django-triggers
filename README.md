# django-triggers

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

Let's consider a simple tasks app with a model `Task` and we want to email a user when all tasks are completed.

1. Add event, action and condition models into your app's model.py
By doing this, we separate the development of the trigger components from their configuration within the Django admin panel. This ensures a more modular and manageable approach to building and configuring triggers.

The full code example is available in [tests directory](https://github.com/cockpithq/django-triggers/tree/main/tests/app).
```python
from triggers.models import Action, Condition, Event

class TaskCompletedEvent(Event):
    '''
    Will be fired when all Task is completed.
    
    If `important_only` is True, only important tasks will fire this Event.
    '''
    important_only = models.BooleanField(default=False)


class SendEmailAction(Action):
    '''
    This action will make it possible to send an email to a user
    '''
    pass


class HasUncompletedTaskCondition(Condition):
    pass
```

2. Makemigrations and migrate
```shell
python manage.py makemigrations
python manage.py migrate
```

3. Add trigger in django admin panel
Don't forget to Enable it!

<img width="557" alt="SCR-20230315-sooo" src="https://user-images.githubusercontent.com/101798/225434592-db566401-873a-4698-9292-79e51ddec5ee.png">

4. Fire trigger's events

```python
@receiver(Task.completed)
def on_task_completed(sender, task: Task, **kwargs):
    for event in TaskCompletedEvent.objects.all():
        transaction.on_commit(
            lambda: event.fire_single(task.user_id, task_id=task.id))
```

5. Check the results of triggers executed

Recorded triggers' activities are accessible in your django admin panel
<img width="888" alt="SCR-20230315-spck" src="https://user-images.githubusercontent.com/101798/225434595-860d26bb-9c4b-481b-9813-a7467c9b7ed7.png">

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
