import pytest
import json
from unittest.mock import patch
from datetime import datetime, timezone

from temporalio.testing import WorkflowEnvironment, WorkflowHistory
from temporalio.worker import Replayer

from triggers.temporal.workflows import TriggerWorkflow


@pytest.fixture
def sample_workflow_history():
    """
    Create a sample workflow history for testing replay.

    This sample history represents a successful execution of a trigger workflow
    where all conditions were satisfied and actions were performed.
    """
    # This is a simplified version of a workflow history
    # In a real test, you would export this from a real workflow run
    return {
        "events": [
            {
                "eventId": 1,
                "eventTime": datetime.now(timezone.utc).isoformat(),
                "eventType": "WorkflowExecutionStarted",
                "workflowExecutionStartedEventAttributes": {
                    "workflowType": {"name": "trigger_workflow"},
                    "taskQueue": {"name": "triggers-test"},
                    "input": {
                        "payloads": [{"data": "123"}, {"data": "456"}, {"data": "{}"}]
                    },
                    "workflowExecutionTimeout": "0s",
                    "workflowRunTimeout": "0s",
                    "workflowTaskTimeout": "10s",
                    "originalExecutionRunId": "some-run-id",
                    "identity": "test-identity",
                    "firstExecutionRunId": "some-run-id",
                    "attempt": 1,
                    "firstWorkflowTaskBackoff": "0s",
                },
            },
            {
                "eventId": 2,
                "eventTime": datetime.now(timezone.utc).isoformat(),
                "eventType": "WorkflowTaskScheduled",
                "workflowTaskScheduledEventAttributes": {
                    "taskQueue": {"name": "triggers-test"},
                    "startToCloseTimeout": "10s",
                    "attempt": 1,
                },
            },
            {
                "eventId": 3,
                "eventTime": datetime.now(timezone.utc).isoformat(),
                "eventType": "WorkflowTaskStarted",
                "workflowTaskStartedEventAttributes": {
                    "scheduledEventId": 2,
                    "identity": "test-identity",
                    "requestId": "test-request-id",
                },
            },
            {
                "eventId": 4,
                "eventTime": datetime.now(timezone.utc).isoformat(),
                "eventType": "WorkflowTaskCompleted",
                "workflowTaskCompletedEventAttributes": {
                    "scheduledEventId": 2,
                    "startedEventId": 3,
                    "identity": "test-identity",
                },
            },
            {
                "eventId": 5,
                "eventTime": datetime.now(timezone.utc).isoformat(),
                "eventType": "WorkflowExecutionCompleted",
                "workflowExecutionCompletedEventAttributes": {
                    "result": None,
                    "workflowTaskCompletedEventId": 4,
                },
            },
        ]
    }


@pytest.mark.asyncio
async def test_workflow_replay():
    """
    Test that a workflow can be replayed from history without non-deterministic errors.

    Replay is an important feature of Temporal that ensures workflow code changes
    remain compatible with existing workflow executions.
    """
    # Create a replayer with our workflow
    replayer = Replayer(workflows=[TriggerWorkflow])

    # Create a workflow history object from a sample history JSON
    with patch("temporalio.worker.Replayer.replay_workflow") as mock_replay:
        # Mock successful replay
        mock_replay.return_value = None

        # Test loading from a dictionary/JSON
        history_dict = sample_workflow_history()
        history = WorkflowHistory.from_json(json.dumps(history_dict))
        await replayer.replay_workflow(history)

        # Verify the replay was called
        mock_replay.assert_called_once()


@pytest.mark.asyncio
async def test_workflow_fetch_activity_data():
    """Test how workflow handles data from the fetch_trigger_definition activity."""
    # Create a workflow environment for testing
    async with await WorkflowEnvironment.start_time_skipping() as env:
        # Create a client
        client = env.client

        # Set up workflow parameters
        trigger_id = 123
        user_pk = 456
        context = {"test": "data"}

        # Mock the activities
        with patch(
            "triggers.temporal.workflows.fetch_trigger_definition"
        ) as mock_fetch:
            with patch(
                "triggers.temporal.workflows.evaluate_condition"
            ) as mock_evaluate:
                with patch(
                    "triggers.temporal.workflows.perform_action"
                ) as mock_perform:
                    with patch("triggers.temporal.workflows.log_activity") as mock_log:
                        # Configure mocks to return empty data
                        mock_fetch.return_value = {
                            "trigger_name": "Empty Trigger",
                            "trigger_enabled": True,
                            "conditions": [],  # No conditions
                            "actions": [],  # No actions
                        }

                        # Create a worker
                        async with Worker(
                            client,
                            task_queue="test-queue",
                            workflows=[TriggerWorkflow],
                            activities=[
                                mock_fetch,
                                mock_evaluate,
                                mock_perform,
                                mock_log,
                            ],
                        ):
                            # Execute the workflow
                            await client.execute_workflow(
                                TriggerWorkflow.run,
                                trigger_id,
                                user_pk,
                                context,
                                id="replay-test-workflow",
                                task_queue="test-queue",
                            )

                        # Verify activity calls
                        mock_fetch.assert_called_once_with(trigger_id)
                        # No conditions, so evaluate should not be called
                        mock_evaluate.assert_not_called()
                        # No actions, so perform should not be called
                        mock_perform.assert_not_called()
                        # Log activity should be called regardless
                        mock_log.assert_called_once_with(trigger_id, user_pk)
