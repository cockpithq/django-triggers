"""
Temporal workflows and activities for django-triggers.

This module defines the core Temporal workflows and activities that mirror
the functionality of the django-triggers system, but using Temporal's
workflow engine instead of Celery for orchestration.
"""

import datetime
from typing import Any, Dict, List, Optional

from temporalio import workflow, activity
from asgiref.sync import sync_to_async

from django.conf import settings as django_settings
from django.apps import apps


User = django_settings.AUTH_USER_MODEL  # type: ignore


# ------- Activities -----------------------------------------------------------
# Activities are where all side effects (DB queries, external API calls) happen.
# Activities can be retried independently if they fail.


@activity.defn(name="fetch_trigger_definition")
async def fetch_trigger_definition(trigger_id: int) -> Dict[str, Any]:
    """
    Activity that fetches the full definition of a trigger from the database.

    Args:
        trigger_id: The ID of the Trigger to fetch

    Returns:
        Dict with conditions and actions configurations
    """

    @sync_to_async
    def _fetch_trigger():
        Trigger = apps.get_model("triggers", "Trigger")
        trigger = Trigger.objects.prefetch_related("conditions", "actions").get(
            pk=trigger_id
        )

        return {
            "trigger_name": trigger.name,
            "trigger_enabled": trigger.is_enabled,
            "conditions": [
                {"id": c.pk, "type": c.__class__.__name__, "params": vars(c)}
                for c in trigger.conditions.all()
            ],
            "actions": [
                {"id": a.pk, "type": a.__class__.__name__, "params": vars(a)}
                for a in trigger.actions.all()
            ],
        }

    return await _fetch_trigger()


@activity.defn(name="evaluate_condition")
async def evaluate_condition(condition_id: int, user_pk: int) -> bool:
    """
    Activity that evaluates a single condition for a specific user.

    Args:
        condition_id: The ID of the Condition to evaluate
        user_pk: User primary key to evaluate the condition against

    Returns:
        bool: True if the condition is satisfied, False otherwise
    """

    @sync_to_async
    def _evaluate_condition():
        Condition = apps.get_model("triggers", "Condition")
        condition = Condition.objects.get(pk=condition_id)
        user = apps.get_model(User).objects.get(pk=user_pk)
        return condition.is_satisfied(user)

    return await _evaluate_condition()


@activity.defn(name="perform_action")
async def perform_action(action_id: int, user_pk: int, ctx: Dict[str, Any]) -> None:
    """
    Activity that performs a single action for a specific user.

    Args:
        action_id: The ID of the Action to perform
        user_pk: User primary key to perform the action for
        ctx: Context data for the action (typically event context)
    """

    @sync_to_async
    def _perform_action():
        Action = apps.get_model("triggers", "Action")
        action = Action.objects.get(pk=action_id)
        user = apps.get_model(User).objects.get(pk=user_pk)
        action.perform(user, ctx)

    await _perform_action()


@activity.defn(name="log_activity")
async def log_activity(trigger_id: int, user_pk: int) -> None:
    """
    Activity that logs trigger activity and updates counters.

    This uses the same Activity.lock context manager from the
    django-triggers models to atomically update activity records.

    Args:
        trigger_id: The ID of the Trigger being processed
        user_pk: User primary key the trigger fired for
    """

    @sync_to_async
    def _log_activity():
        Activity = apps.get_model("triggers", "Activity")
        Trigger = apps.get_model("triggers", "Trigger")
        trigger = Trigger.objects.get(pk=trigger_id)
        user = apps.get_model(User).objects.get(pk=user_pk)

        with Activity.lock(user, trigger):
            # The lock context manager automatically increments
            # action_count and updates last_action_datetime
            pass

    await _log_activity()


# ------- Workflow ------------------------------------------------------------
# The workflow is deterministic and contains no side effects.
# It orchestrates the activities and maintains the workflow state.


@workflow.defn(name="trigger_workflow")
class TriggerWorkflow:
    """
    Workflow that processes a single trigger execution for a specific user.

    This workflow fetches the trigger definition, evaluates all conditions,
    and if all conditions pass, performs all actions associated with the trigger.
    It also handles activity retries and timeouts.
    """

    def __init__(self) -> None:
        self.context: Dict[str, Any] = {}

    @workflow.run
    async def run(
        self, trigger_id: int, user_pk: int, ctx: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Main workflow execution method.

        Args:
            trigger_id: The ID of the Trigger to process
            user_pk: User primary key to process the trigger for
            ctx: Optional context data from the event that fired the trigger
        """
        # Ensure we have a dict type for context (even if None)
        context_dict: Dict[str, Any] = {} if ctx is None else dict(ctx)
        self.context = context_dict

        # Configure timeouts and retry policies
        # These values are hardcoded here to avoid importing settings module
        # which would cause sandbox issues
        fetch_timeout = datetime.timedelta(seconds=30)  # 30 seconds
        evaluate_timeout = datetime.timedelta(seconds=30)  # 30 seconds
        action_timeout = datetime.timedelta(seconds=120)  # 2 minutes
        log_timeout = datetime.timedelta(seconds=15)  # 15 seconds

        retry_interval = datetime.timedelta(seconds=1)  # 1 second
        max_retries = 3  # 3 retries

        # Standard retry policy for most activities
        standard_retry_policy = workflow.RetryPolicy(
            maximum_attempts=max_retries,
            initial_interval=retry_interval,
        )

        # Create a more aggressive retry policy for critical operations
        critical_retry_policy = workflow.RetryPolicy(
            maximum_attempts=max_retries + 2,  # More retries for critical operations
            initial_interval=retry_interval,
        )

        # 1. Pull the full definition (re-evaluated at run-time → dynamic config)
        definition = await workflow.execute_activity(
            fetch_trigger_definition,
            trigger_id,
            start_to_close_timeout=fetch_timeout,
            retry_policy=standard_retry_policy,
        )

        # Check if the trigger is enabled
        if not definition.get("trigger_enabled", False):
            return

        # 2. Check conditions
        for cond in definition["conditions"]:
            ok = await workflow.execute_activity(
                evaluate_condition,
                cond["id"],
                user_pk,
                start_to_close_timeout=evaluate_timeout,
                retry_policy=standard_retry_policy,
            )
            if not ok:
                return  # short-circuit – nothing to do if any condition fails

        # 3. Perform actions - we'll use parallel execution by default
        use_parallel = True

        if use_parallel:
            # Run actions in parallel
            futs: List[workflow.Future] = []
            for act in definition["actions"]:
                fut = workflow.execute_activity(
                    perform_action,
                    act["id"],
                    user_pk,
                    self.context,
                    start_to_close_timeout=action_timeout,
                    retry_policy=standard_retry_policy,
                )
                futs.append(fut)

            # Wait for all actions to complete
            await workflow.wait_for_all(futs)
        else:
            # Run actions sequentially
            for act in definition["actions"]:
                await workflow.execute_activity(
                    perform_action,
                    act["id"],
                    user_pk,
                    self.context,
                    start_to_close_timeout=action_timeout,
                    retry_policy=standard_retry_policy,
                )

        # 4. Persist activity tracking (frequency / count bookkeeping)
        await workflow.execute_activity(
            log_activity,
            trigger_id,
            user_pk,
            start_to_close_timeout=log_timeout,
            retry_policy=critical_retry_policy,  # Use more aggressive retries for activity logging
        )
