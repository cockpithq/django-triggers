# django-triggers

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
