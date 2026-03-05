from django.dispatch import Signal

TRACE_ID_CONTEXT_KEY = "_triggers_trace_id"

event_enqueued = Signal()
event_started = Signal()
event_user_resolved = Signal()
condition_checked = Signal()
action_performed = Signal()
action_failed = Signal()
run_completed = Signal()


def emit(signal: Signal, sender, **kwargs):
    # Use robust mode to ensure observers never break trigger execution.
    signal.send_robust(sender=sender, **kwargs)
