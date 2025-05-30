"""
Settings for django-triggers Temporal integration.

These settings can be overridden in the project's settings.py file.
"""

from django.conf import settings


# Whether to use Temporal for trigger processing
TRIGGERS_USE_TEMPORAL = getattr(settings, "TRIGGERS_USE_TEMPORAL", False)

# Default Temporal server connection settings
TEMPORAL_HOST = getattr(settings, "TEMPORAL_HOST", "localhost:7233")
TEMPORAL_NAMESPACE = getattr(settings, "TEMPORAL_NAMESPACE", "triggers")
TEMPORAL_TASK_QUEUE = getattr(settings, "TEMPORAL_TASK_QUEUE", "triggers")

# Connection security options
TEMPORAL_TLS_ENABLED = getattr(settings, "TEMPORAL_TLS_ENABLED", False)
TEMPORAL_TLS_CERT_PATH = getattr(settings, "TEMPORAL_TLS_CERT_PATH", None)
TEMPORAL_TLS_KEY_PATH = getattr(settings, "TEMPORAL_TLS_KEY_PATH", None)

# Workflow execution settings
TEMPORAL_PARALLEL_ACTIONS = getattr(settings, "TEMPORAL_PARALLEL_ACTIONS", True)

# Timeouts
TEMPORAL_FETCH_DEFINITION_TIMEOUT = getattr(
    settings, "TEMPORAL_FETCH_DEFINITION_TIMEOUT", 30
)
TEMPORAL_EVALUATE_CONDITION_TIMEOUT = getattr(
    settings, "TEMPORAL_EVALUATE_CONDITION_TIMEOUT", 30
)
TEMPORAL_PERFORM_ACTION_TIMEOUT = getattr(
    settings, "TEMPORAL_PERFORM_ACTION_TIMEOUT", 120
)
TEMPORAL_LOG_ACTIVITY_TIMEOUT = getattr(settings, "TEMPORAL_LOG_ACTIVITY_TIMEOUT", 15)

# Retries
TEMPORAL_MAX_ACTIVITY_RETRIES = getattr(settings, "TEMPORAL_MAX_ACTIVITY_RETRIES", 3)
TEMPORAL_ACTIVITY_RETRY_INTERVAL = getattr(
    settings, "TEMPORAL_ACTIVITY_RETRY_INTERVAL", 1
)  # seconds
