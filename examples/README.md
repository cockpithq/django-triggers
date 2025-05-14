# Django-Triggers Temporal Integration Examples

This directory contains example scripts to demonstrate and test the Temporal integration with django-triggers.

## Prerequisites

1. Make sure you have a Temporal server running.

```sh
brew install temporal
temporal server start-dev
```

2. Install the required dependencies:

```sh
# Using uv
uv add temporalio asgiref
uv sync

# Or with pip
pip install temporalio asgiref
```

3. Configure the integration in your Django settings:

```python
# in your project's settings.py
TRIGGERS_USE_TEMPORAL = True

# Optional Temporal configuration
TEMPORAL_HOST = "localhost:7233"  # Your Temporal server address
TEMPORAL_NAMESPACE = "triggers"    # Your Temporal namespace
TEMPORAL_TASK_QUEUE = "triggers"   # Task queue for trigger workflows
```

## Example Scripts

### Run Temporal Worker

This script runs a Temporal worker that processes workflows and activities for the django-triggers system.

```sh
python examples/run_temporal_worker.py
```

Options:

- `--task-queue NAME`: Override the task queue to poll (default from settings)
- `--debug`: Enable debug logging

### Test Temporal Integration

This script demonstrates how to fire an event and verify it's processed by Temporal.

```sh
python examples/test_temporal_integration.py
```

This script:

1. Connects to the Temporal server
2. Lists any running workflows
3. Gets the first trigger and event from the database
4. Fires the event for the first user in the database
5. Monitors the workflow execution

## Monitoring

You can monitor workflows using the Temporal Web UI, which is available at http://localhost:8088 by default when using the Docker Compose setup.

## Troubleshooting

1. **Connection refused**: Make sure your Temporal server is running and accessible.
2. **Namespace not found**: The default namespace is "default". If you're using a custom namespace, make sure it exists in Temporal.
3. **No triggers found**: Create a trigger and event in the Django admin before running the test script.
4. **Worker not processing workflows**: Make sure the worker is running and using the same task queue as the client.
