# django-triggers

`django-triggers` is intended for implementing event-based business logic configurable through the Django admin site.

## Quickstart

1. Install dj triggers and add to your INSTALLED_APPS
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

2. Add triggers' models into your app's model.py

```python
class SampleEvent(Event):
    pass

class SampleAction(Action):
    pass
```

3. Makemigrations and migrate
```shell
python manage.py makemigrations
python manage.py migrate
```

4. Manage triggers through admin panel

![Feb-28-2023 16-00-54](https://user-images.githubusercontent.com/101798/221892529-90966e29-aff5-4207-83b9-34e1ed1f869d.gif)

5. Fire trigger's events
For example, we may have a simple event that fires when some todos is completed and updated.
```python
class Todo(models.Model):
    def save(self, *args, **kwargs):
        ...
        if is_completed:
            for event in TodoIsCompletedEvent.objects.all():
                event.fire_single(self.user_id)
        ...
```

6. Check the result
Recorded triggers' activities are accessible in your django admin panel
<img width="817" alt="image" src="https://user-images.githubusercontent.com/101798/221951142-61e4f928-f4ba-4c0b-a0f6-884f622fd3ae.png">

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
