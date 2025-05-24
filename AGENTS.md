it should be same as README.md but keep it here anyhow

## Development

### Quick setup for development

```shell
uv sync
```

### Run a django-admin command, e.g. `makemigrations`

```shell
uv run django makemigrations --settings=tests.app.settings
```

### Run mypy

```shell
uv run mypy triggers tests
```

### Run pytest

```shell
uv run pytest
```
