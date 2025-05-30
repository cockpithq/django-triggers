from unittest.mock import AsyncMock, MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from model_bakery import baker
import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from tests.app.models import ClockEvent
from triggers.models import Event, Trigger
from triggers.temporal.hooks import on_event_fired
from triggers.temporal.workflows import (
    TriggerWorkflow,
    evaluate_condition,
    fetch_trigger_definition,
    log_activity,
    perform_action,
)


@pytest.fixture
async def workflow_environment():
    """Fixture to provide a time-skipping test workflow environment."""
    async with await WorkflowEnvironment.start_time_skipping() as env:
        yield env


@pytest.fixture
async def client(workflow_environment):
    """Fixture to provide a Temporal client connected to the test environment."""
    return workflow_environment.client


@pytest.fixture
async def worker(client):
    """Fixture to provide a worker connected to the test client."""
    async with Worker(
        client,
        task_queue="test-queue",
        workflows=[TriggerWorkflow],
        activities=[
            fetch_trigger_definition,
            evaluate_condition,
            perform_action,
            log_activity,
        ],
    ) as worker:
        yield worker


@pytest.fixture
def test_user():
    """Create a test user."""
    User = get_user_model()
    return baker.make(User, username="test_user", email="test@example.com")


@pytest.fixture
def test_trigger():
    """Create a test trigger."""
    return baker.make(Trigger, name="Test Trigger", is_enabled=True)


@pytest.fixture
def test_event(test_trigger):
    """Create a test clock event for the trigger."""
    return baker.make(ClockEvent, trigger=test_trigger)


@pytest.mark.asyncio
@override_settings(TRIGGERS_USE_TEMPORAL=True)
async def test_temporal_workflow_execution(
    client, worker, test_trigger, test_user, test_event
):
    """Test that a workflow can be executed successfully."""
    # Mock the activities to avoid database access during testing
    with patch("triggers.temporal.workflows.fetch_trigger_definition") as mock_fetch:
        with patch("triggers.temporal.workflows.evaluate_condition") as mock_evaluate:
            with patch("triggers.temporal.workflows.perform_action") as mock_perform:
                with patch("triggers.temporal.workflows.log_activity") as mock_log:
                    # Configure mocks
                    mock_fetch.return_value = {
                        "trigger_name": test_trigger.name,
                        "trigger_enabled": True,
                        "conditions": [
                            {"id": 1, "type": "AlwaysTrueCondition", "params": {}}
                        ],
                        "actions": [{"id": 1, "type": "LogAction", "params": {}}],
                    }
                    mock_evaluate.return_value = True

                    # Run the workflow
                    workflow_id = f"test-workflow-{test_trigger.id}"
                    await client.execute_workflow(
                        TriggerWorkflow.run,
                        test_trigger.id,
                        test_user.id,
                        {},
                        id=workflow_id,
                        task_queue="test-queue",
                    )

                    # Verify activity calls
                    mock_fetch.assert_called_once_with(test_trigger.id)
                    mock_evaluate.assert_called_once_with(1, test_user.id)
                    mock_perform.assert_called_once_with(1, test_user.id, {})
                    mock_log.assert_called_once_with(test_trigger.id, test_user.id)


@pytest.mark.asyncio
@override_settings(TRIGGERS_USE_TEMPORAL=True)
async def test_condition_failed(client, worker, test_trigger, test_user):
    """Test that actions aren't performed when a condition fails."""
    # Mock the activities to avoid database access during testing
    with patch("triggers.temporal.workflows.fetch_trigger_definition") as mock_fetch:
        with patch("triggers.temporal.workflows.evaluate_condition") as mock_evaluate:
            with patch("triggers.temporal.workflows.perform_action") as mock_perform:
                with patch("triggers.temporal.workflows.log_activity") as mock_log:
                    # Configure mocks
                    mock_fetch.return_value = {
                        "trigger_name": test_trigger.name,
                        "trigger_enabled": True,
                        "conditions": [
                            {"id": 1, "type": "AlwaysFalseCondition", "params": {}}
                        ],
                        "actions": [{"id": 1, "type": "LogAction", "params": {}}],
                    }
                    mock_evaluate.return_value = False

                    # Run the workflow
                    workflow_id = f"test-workflow-{test_trigger.id}-condition-fail"
                    await client.execute_workflow(
                        TriggerWorkflow.run,
                        test_trigger.id,
                        test_user.id,
                        {},
                        id=workflow_id,
                        task_queue="test-queue",
                    )

                    # Verify activity calls - perform_action and log_activity shouldn't be called
                    mock_fetch.assert_called_once_with(test_trigger.id)
                    mock_evaluate.assert_called_once_with(1, test_user.id)
                    mock_perform.assert_not_called()
                    mock_log.assert_not_called()


@pytest.mark.django_db
@override_settings(TRIGGERS_USE_TEMPORAL=True)
def test_signal_handler(test_trigger, test_user, test_event):
    """Test that the signal handler starts a Temporal workflow."""
    # Patch the async start workflow function
    with patch("triggers.temporal.hooks.get_temporal_client") as mock_client:
        # Create async mock for client
        mock_client_instance = AsyncMock()
        mock_client.return_value = mock_client_instance

        # Call the signal handler synchronously
        on_event_fired(Event, Event.fired, test_event, test_user.id)

        # Check that the workflow was started with the correct parameters
        mock_client_instance.start_workflow.assert_called_once()
        # Get the arguments from the call
        args, kwargs = mock_client_instance.start_workflow.call_args

        # Verify the workflow ID format
        assert (
            kwargs["id"] == f"trigger-{test_trigger.id}-{test_user.id}-{test_event.id}"
        )
        assert kwargs["task_queue"] == "triggers-test"  # From test settings


@pytest.mark.asyncio
async def test_activity_environment():
    """Test activities can be tested individually using ActivityEnvironment."""
    from temporalio.testing import ActivityEnvironment

    # Create an activity environment
    env = ActivityEnvironment()

    # Test the activity heartbeat functionality
    @patch("triggers.models.Trigger.objects.prefetch_related")
    async def test_fetch_activity(mock_prefetch):
        # Mock the database queries
        mock_trigger = MagicMock()
        mock_trigger.name = "Test Trigger"
        mock_trigger.is_enabled = True
        mock_trigger.conditions.all.return_value = []
        mock_trigger.actions.all.return_value = []

        mock_manager = MagicMock()
        mock_manager.get.return_value = mock_trigger
        mock_prefetch.return_value = mock_manager

        # Run the activity in the test environment
        result = await env.run(fetch_trigger_definition, 1)

        # Verify the result
        assert result["trigger_name"] == "Test Trigger"
        assert result["trigger_enabled"] is True
        assert result["conditions"] == []
        assert result["actions"] == []

    await test_fetch_activity()


@pytest.mark.asyncio
@override_settings(TRIGGERS_USE_TEMPORAL=True)
async def test_workflow_disabled_trigger(client, worker, test_trigger, test_user):
    """Test that workflow exits early if trigger is disabled."""
    # Mock the activities
    with patch("triggers.temporal.workflows.fetch_trigger_definition") as mock_fetch:
        with patch("triggers.temporal.workflows.evaluate_condition") as mock_evaluate:
            with patch("triggers.temporal.workflows.perform_action") as mock_perform:
                # Configure mocks
                mock_fetch.return_value = {
                    "trigger_name": test_trigger.name,
                    "trigger_enabled": False,  # Trigger is disabled
                    "conditions": [
                        {"id": 1, "type": "AlwaysTrueCondition", "params": {}}
                    ],
                    "actions": [{"id": 1, "type": "LogAction", "params": {}}],
                }

                # Run the workflow
                workflow_id = f"test-workflow-{test_trigger.id}-disabled"
                await client.execute_workflow(
                    TriggerWorkflow.run,
                    test_trigger.id,
                    test_user.id,
                    {},
                    id=workflow_id,
                    task_queue="test-queue",
                )

                # Verify activities - only fetch_definition should be called
                mock_fetch.assert_called_once_with(test_trigger.id)
                mock_evaluate.assert_not_called()
                mock_perform.assert_not_called()
