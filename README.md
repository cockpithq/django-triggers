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

Let's say we have a simple todo app with a model `Todo` and we want to email a user when all todos are completed.
The full example is available in [Todo Example](https://github.com/fireharp/django-triggers-example).

1. Add triggers' models into your app's model.py

```python
class TodoIsFinishedEvent(Event):
    # will be fired when todo is completed
    pass

class SendEmailAction(Action):
    email_message = models.TextField(_('email message'), blank=True)
    # will send email to user with email_message


class UnfinishedTodosCountCondition(Condition):
    value = models.PositiveIntegerField('value')
    
    def is_satisfied(self, user) -> bool:
        unfinished_todos_count = user.todos.filter(date_finished__isnull=True).count()
        return unfinished_todos_count == self.value
```

2. Makemigrations and migrate
```shell
python manage.py makemigrations
python manage.py migrate
```

3. Add trigger in django admin panel
Don't forget to Enable it.

<img width="483" alt="image" src="https://user-images.githubusercontent.com/101798/222222820-debceff7-1122-4011-bb2f-d1a549710bc1.png">

4. Fire trigger's events

```python
class Todo(models.Model):
    def save(self, *args, **kwargs):
        ...
        if is_finished:
            for event in TodoIsFinishedEvent.objects.all():
                event.fire_single(self.user_id)
        ...
```

5. Action's performed when all Todo's are completed
```
DEBUG made it! fireharp {'user': <User: fireharp>} Great job finishing all the Todos.
Keep it up!
INFO Task triggers.tasks.handle_event[87b191f8-581d-4073-b272-0833b5bc821e] succeeded in 2.2159159209999997s: None
```
<img width="979" alt="image" src="https://user-images.githubusercontent.com/101798/222230003-744f3d36-d1dd-40cd-a0ff-eedb7a01d75a.png">

6. Check the result in django admin panel
Recorded triggers' activities are accessible in your django admin panel
<img width="643" alt="image" src="https://user-images.githubusercontent.com/101798/222230395-c49e5147-e8b6-416c-b4a5-70fbaf06eaa9.png">

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
