"""
Temporal workflows and activities for django-triggers.

This module defines the core Temporal workflows and activities that mirror
the functionality of the django-triggers system, but using Temporal's
workflow engine instead of Celery for orchestration.
"""

import datetime
import logging
from typing import Any, Dict, List, Optional

from temporalio import workflow, activity
from asgiref.sync import sync_to_async

from django.conf import settings as django_settings
from django.apps import apps


User = django_settings.AUTH_USER_MODEL  # type: ignore
logger = logging.getLogger(__name__)


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
    logger.info(f"📋 Fetching trigger definition for trigger #{trigger_id}...")

    @sync_to_async
    def _fetch_trigger():
        Trigger = apps.get_model("triggers", "Trigger")
        trigger = Trigger.objects.prefetch_related("conditions", "actions").get(
            pk=trigger_id
        )

        conditions = list(trigger.conditions.all())
        actions = list(trigger.actions.all())

        logger.info(
            f"🔍 Found trigger '{trigger.name}' with {len(conditions)} conditions and {len(actions)} actions"
        )

        if conditions:
            logger.info(f"🔎 Conditions: {', '.join(str(c) for c in conditions)}")

        if actions:
            logger.info(f"🎬 Actions: {', '.join(str(a) for a in actions)}")

        return {
            "trigger_name": trigger.name,
            "trigger_enabled": trigger.is_enabled,
            "conditions": [
                {"id": c.pk, "type": c.__class__.__name__, "params": vars(c)}
                for c in conditions
            ],
            "actions": [
                {"id": a.pk, "type": a.__class__.__name__, "params": vars(a)}
                for a in actions
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

        logger.info(f"⚖️ Evaluating condition '{condition}' for user #{user_pk}...")

        result = condition.is_satisfied(user)

        if result:
            logger.info(f"✅ Condition '{condition}' is SATISFIED for user #{user_pk}")
        else:
            logger.info(
                f"❌ Condition '{condition}' is NOT SATISFIED for user #{user_pk}"
            )

        return result

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

        logger.info(f"🚀 Performing action '{action}' for user #{user_pk}...")

        # Get some context info for logging
        context_summary = ", ".join(
            f"{k}: {v}" for k, v in ctx.items() if k in ["bmi", "height", "weight"]
        )
        if context_summary:
            logger.info(f"📊 Action context: {context_summary}")

        # Perform the action
        action.perform(user, ctx)

        logger.info(f"✅ Action '{action}' completed successfully")

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

        logger.info(
            f"📝 Recording activity for trigger '{trigger.name}' and user #{user_pk}..."
        )

        with Activity.lock(user, trigger):
            # The lock context manager automatically increments
            # action_count and updates last_action_datetime
            pass

        logger.info("✅ Activity recorded successfully - trigger execution complete")

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

        # Log workflow start (using workflow.logger which is safe in workflow code)
        workflow.logger.info(
            f"🔄 Starting workflow for trigger #{trigger_id} and user #{user_pk}"
        )

        # Context summary for logging
        context_summary = ""
        if self.context:
            for key, value in self.context.items():
                if key in ["bmi", "height", "weight"]:
                    context_summary += f"{key}: {value}, "
            if context_summary:
                workflow.logger.info(f"📊 Context data: {context_summary.rstrip(', ')}")

        # 1. Pull the full definition (re-evaluated at run-time → dynamic config)
        workflow.logger.info("📋 Step 1: Fetching trigger definition...")
        definition = await workflow.execute_activity(
            fetch_trigger_definition,
            trigger_id,
            start_to_close_timeout=fetch_timeout,
            retry_policy=standard_retry_policy,
        )

        # Check if the trigger is enabled
        if not definition.get("trigger_enabled", False):
            workflow.logger.info(
                f"⚠️ Trigger '{definition.get('trigger_name')}' is disabled, stopping workflow"
            )
            return

        workflow.logger.info(f"✅ Fetched trigger '{definition.get('trigger_name')}'")

        # 2. Check conditions
        if not definition.get("conditions"):
            workflow.logger.info("ℹ️ No conditions to check - proceeding to actions")
        else:
            workflow.logger.info(
                f"⚖️ Step 2: Checking {len(definition['conditions'])} conditions..."
            )

            for i, cond in enumerate(definition["conditions"], 1):
                workflow.logger.info(
                    f"🔍 Checking condition {i}/{len(definition['conditions'])}: {cond.get('type')}"
                )
                ok = await workflow.execute_activity(
                    evaluate_condition,
                    cond["id"],
                    user_pk,
                    start_to_close_timeout=evaluate_timeout,
                    retry_policy=standard_retry_policy,
                )
                if not ok:
                    workflow.logger.info(
                        "❌ Condition failed - stopping workflow without actions"
                    )
                    return  # short-circuit – nothing to do if any condition fails

            workflow.logger.info("✅ All conditions passed")

        # 3. Perform actions
        if not definition.get("actions"):
            workflow.logger.info("ℹ️ No actions to perform - workflow complete")
            return

        workflow.logger.info(
            f"🚀 Step 3: Performing {len(definition['actions'])} actions..."
        )

        # we'll use parallel execution by default
        use_parallel = True

        if use_parallel:
            # Run actions in parallel
            workflow.logger.info("🔀 Running actions in parallel")
            futs: List[workflow.Future] = []
            for i, act in enumerate(definition["actions"], 1):
                workflow.logger.info(
                    f"🎬 Scheduling action {i}/{len(definition['actions'])}: {act.get('type')}"
                )
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
            workflow.logger.info("⏳ Waiting for all actions to complete...")
            await workflow.wait_for_all(futs)
            workflow.logger.info("✅ All actions completed successfully")
        else:
            # Run actions sequentially
            workflow.logger.info("⏩ Running actions sequentially")
            for i, act in enumerate(definition["actions"], 1):
                workflow.logger.info(
                    f"🎬 Running action {i}/{len(definition['actions'])}: {act.get('type')}"
                )
                await workflow.execute_activity(
                    perform_action,
                    act["id"],
                    user_pk,
                    self.context,
                    start_to_close_timeout=action_timeout,
                    retry_policy=standard_retry_policy,
                )
                workflow.logger.info(
                    f"✅ Action {i}/{len(definition['actions'])} completed"
                )

        # 4. Persist activity tracking (frequency / count bookkeeping)
        workflow.logger.info(
            "📝 Step 4: Recording activity for this trigger execution..."
        )
        await workflow.execute_activity(
            log_activity,
            trigger_id,
            user_pk,
            start_to_close_timeout=log_timeout,
            retry_policy=critical_retry_policy,  # Use more aggressive retries for activity logging
        )

        workflow.logger.info("🎉 Workflow execution completed successfully")
