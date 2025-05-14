"""
Temporal isolated workflows for django-triggers.

This module contains isolated workflow definitions that don't import Django
or other non-deterministic libraries that would cause sandbox issues.
"""

import datetime
from typing import Any, Dict, List, Optional

from temporalio import workflow
from temporalio.common import RetryPolicy


# ---- Workflow Definition ---------------------------------------------------


@workflow.defn(name="trigger_workflow")
class TriggerWorkflow:
    """
    Workflow that processes a single trigger execution for a specific user.

    This is an isolated workflow definition that doesn't import Django or any
    other libraries that could cause sandbox issues with Temporal.
    """

    def __init__(self) -> None:
        """Initialize workflow state."""
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

        # Configure timeouts for activities
        fetch_timeout = datetime.timedelta(seconds=30)  # 30 seconds
        evaluate_timeout = datetime.timedelta(seconds=30)  # 30 seconds
        action_timeout = datetime.timedelta(seconds=120)  # 2 minutes
        log_timeout = datetime.timedelta(seconds=15)  # 15 seconds

        # Configure retry policy parameters
        retry_interval = datetime.timedelta(seconds=1)  # 1 second initial interval
        max_retries = 3  # 3 maximum retries

        # Standard retry policy for most activities
        standard_retry_policy = RetryPolicy(
            maximum_attempts=max_retries,
            initial_interval=retry_interval,
        )

        # More aggressive retry policy for critical operations
        critical_retry_policy = RetryPolicy(
            maximum_attempts=max_retries + 2,
            initial_interval=retry_interval,
        )

        # 1. Pull the full definition of the trigger
        definition = await workflow.execute_activity(
            "fetch_trigger_definition",  # Use activity name instead of direct function ref
            args=[trigger_id],
            start_to_close_timeout=fetch_timeout,
            retry_policy=standard_retry_policy,
        )

        # Check if the trigger is enabled
        if not definition.get("trigger_enabled", False):
            return

        # 2. Check conditions
        for cond in definition.get("conditions", []):
            cond_id = cond.get("id")
            if cond_id is not None:
                ok = await workflow.execute_activity(
                    "evaluate_condition",  # Use activity name instead of direct function ref
                    args=[cond_id, user_pk],
                    start_to_close_timeout=evaluate_timeout,
                    retry_policy=standard_retry_policy,
                )
                if not ok:
                    return  # short-circuit – nothing to do if any condition fails

        # 3. Perform actions (in parallel)
        futures: List[workflow.Future] = []
        for action in definition.get("actions", []):
            action_id = action.get("id")
            if action_id is not None:
                fut = workflow.execute_activity(
                    "perform_action",  # Use activity name instead of direct function ref
                    args=[action_id, user_pk, self.context],
                    start_to_close_timeout=action_timeout,
                    retry_policy=standard_retry_policy,
                )
                futures.append(fut)

        # Wait for all actions to complete (if any)
        if futures:
            await workflow.wait_for_all(futures)

        # 4. Persist activity tracking (frequency / count bookkeeping)
        await workflow.execute_activity(
            "log_activity",  # Use activity name instead of direct function ref
            args=[trigger_id, user_pk],
            start_to_close_timeout=log_timeout,
            retry_policy=critical_retry_policy,
        )
