# Task: Migrate Django Triggers from Celery to Temporal.io

## TS: 2025-05-14 22:30:19 CEST

---

## PROBLEM: Current Django triggers implementation uses Celery for workflow orchestration, which lacks some advanced workflow capabilities like long-running user journeys, workflow versioning, and replay protection.

## WHAT WAS DONE: Implemented a Temporal.io adapter for Django triggers that retains the existing models while migrating execution orchestration.

MEMO: This migration can be done incrementally, running both Celery and Temporal in parallel during the transition. Models and admin UI remain unchanged, making this a seamless backend upgrade.

## Task Steps

1. [ ] Install Temporal.io SDK dependencies

   ```sh
   uv add temporalio asgiref
   uv sync
   ```

2. [ ] Create Temporal client adapter

   - [ ] Create directory structure `triggers/temporal/`
   - [ ] Create `triggers/temporal/client.py` with client connection function

3. [ ] Implement workflow and activities

   - [ ] Create `triggers/temporal/workflows.py` with activity definitions
   - [ ] Implement core workflow logic matching Django triggers semantics

4. [ ] Create Temporal worker entry point

   - [ ] Add worker bootstrap code (for running via Django command or standalone)
   - [ ] Register all workflows and activities

5. [ ] Replace Celery integration with Temporal hooks

   - [ ] Create `triggers/temporal/hooks.py` with workflow start function
   - [ ] Replace or duplicate the Event.fired signal handler

6. [ ] Test the integration

   - [ ] Run Temporal server locally (or connect to cloud)
   - [ ] Start worker process
   - [ ] Verify triggers execute properly with Temporal

7. [ ] Monitor and validate parallel execution

   - [ ] Ensure triggers don't execute twice (once in Celery, once in Temporal)
   - [ ] Validate all triggers execute as expected in Temporal

8. [ ] Complete migration
   - [ ] Remove Celery-specific code once Temporal is proven reliable
   - [ ] Update documentation for future development

## Code Sections Already Prepared

### 1. Temporal Client

```python
# triggers/temporal/client.py
from temporalio.client import Client

def get_temporal_client() -> Client:
    #  ❗ put your own address / namespace / TLS settings here
    return Client.connect("temporal:7233", namespace="triggers")
```

### 2. Workflows & Activities

```python
# triggers/temporal/workflows.py
import datetime
from typing import Any, Dict, List

from temporalio import workflow, activity

from django.conf import settings
from django.apps import apps

User = settings.AUTH_USER_MODEL            # type: ignore

# ---  activities -------------------------------------------------------------

@activity.defn(name="fetch_trigger_definition")
async def fetch_trigger_definition(trigger_id: int) -> Dict[str, Any]:
    Trigger = apps.get_model("triggers", "Trigger")
    trigger = Trigger.objects.prefetch_related("conditions", "actions").get(pk=trigger_id)

    return {
        "conditions": [
            {"id": c.pk, "type": c.__class__.__name__, "params": vars(c)}
            for c in trigger.conditions.all()
        ],
        "actions": [
            {"id": a.pk, "type": a.__class__.__name__, "params": vars(a)}
            for a in trigger.actions.all()
        ],
    }


@activity.defn(name="evaluate_condition")
async def evaluate_condition(condition_id: int, user_pk: int) -> bool:
    Condition = apps.get_model("triggers", "Condition")
    condition = Condition.objects.get(pk=condition_id)
    user = apps.get_model(User).objects.get(pk=user_pk)
    return condition.is_satisfied(user)


@activity.defn(name="perform_action")
async def perform_action(action_id: int, user_pk: int, ctx: Dict[str, Any]) -> None:
    Action = apps.get_model("triggers", "Action")
    action = Action.objects.get(pk=action_id)
    user = apps.get_model(User).objects.get(pk=user_pk)
    action.perform(user, ctx)


@activity.defn(name="log_activity")
async def log_activity(trigger_id: int, user_pk: int) -> None:
    Activity = apps.get_model("triggers", "Activity")
    Trigger = apps.get_model("triggers", "Trigger")
    trigger = Trigger.objects.get(pk=trigger_id)
    user   = apps.get_model(User).objects.get(pk=user_pk)

    with Activity.lock(user, trigger):      # same helper you already have
        pass                                # increments count + timestamp

# ---  workflow ---------------------------------------------------------------

@workflow.defn(name="trigger_workflow")
class TriggerWorkflow:
    """One workflow instance = one trigger fired for one user."""

    def __init__(self) -> None:
        self.context: Dict[str, Any] = {}

    @workflow.run
    async def run(self,
                  trigger_id: int,
                  user_pk: int,
                  ctx: Dict[str, Any] | None = None) -> None:

        self.context = ctx or {}

        # 1. Pull the full definition (re-evaluated at run-time → dynamic config)
        definition = await workflow.execute_activity(
            fetch_trigger_definition,
            trigger_id,
            start_to_close_timeout=datetime.timedelta(seconds=30),
        )

        # 2. Check conditions
        for cond in definition["conditions"]:
            ok = await workflow.execute_activity(
                evaluate_condition,
                cond["id"], user_pk,
                start_to_close_timeout=datetime.timedelta(seconds=30),
            )
            if not ok:
                return                      # short-circuit – nothing to do

        # 3. Perform actions (they can run in parallel if you like)
        futs: List[workflow.Future] = []
        for act in definition["actions"]:
            fut = workflow.execute_activity(
                perform_action,
                act["id"], user_pk, self.context,
                start_to_close_timeout=datetime.timedelta(minutes=2),
            )
            futs.append(fut)
        await workflow.wait_for_all(futs)

        # 4. Persist frequency / count bookkeeping
        await workflow.execute_activity(
            log_activity,
            trigger_id, user_pk,
            start_to_close_timeout=datetime.timedelta(seconds=15),
        )
```

### 3. Temporal Worker Startup

```python
# manage.py temporal_worker  (simple Django-aware entrypoint)
import asyncio
import os
import django
from temporalio.worker import Worker
from triggers.temporal.client import get_temporal_client
from triggers.temporal.workflows import TriggerWorkflow
from triggers.temporal.workflows import (
    fetch_trigger_definition,
    evaluate_condition,
    perform_action,
    log_activity,
)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "your_project.settings")
django.setup()

async def main() -> None:
    client = await get_temporal_client()
    worker = Worker(
        client,
        task_queue="triggers",         # same queue every emitter will target
        workflows=[TriggerWorkflow],
        activities=[
            fetch_trigger_definition,
            evaluate_condition,
            perform_action,
            log_activity,
        ],
    )
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
```

### 4. Hooks for Event Firing

```python
# triggers/temporal/hooks.py
from triggers.temporal.client import get_temporal_client
from temporalio import workflow

def start_trigger_workflow(event, user_pk, **kwargs):
    """
    Launch (or deduplicate) a workflow instance whenever Event.fired is emitted.
    """
    from asgiref.sync import async_to_sync

    def _run():
        client = get_temporal_client()
        wid = f"trigger-{event.trigger_id}-{user_pk}-{event.pk}"
        async_to_sync(client.start_workflow)(
            "trigger_workflow",               # registered name
            event.trigger_id,
            user_pk,
            kwargs,                           # initial context for activities
            id=wid,
            task_queue="triggers",
            # ensures retries/dup-protection if someone double-fires
        )

    async_to_sync(_run)()
```

### 5. Signal Handler Replacement

```python
# replacement for current triggers.tasks.on_event_fired
from django.dispatch import receiver, Signal
from triggers.temporal.hooks import start_trigger_workflow
from triggers.models import Event

@receiver(Event.fired)
def on_event_fired(sender, signal: Signal, event: Event, user_pk, **kwargs):
    start_trigger_workflow(event, user_pk, **kwargs)
```
