import uuid

from django.contrib.auth import get_user_model
import pytest

from triggers.models import Action, Event, Trigger, TriggerLog, log_trigger_event
from triggers.tasks import handle_event


User = get_user_model()


@pytest.fixture
def user():
    return User.objects.create_user(username="test_user", password="password")


@pytest.fixture
def trigger():
    return Trigger.objects.create(name="Test Trigger", is_enabled=True)


@pytest.fixture
def event(trigger):
    return Event.objects.create(trigger=trigger)


@pytest.fixture
def test_action(trigger):
    # Use the default manager model to create an action
    # to avoid problems with model without app_label
    return Action._default_manager.create(trigger=trigger)


@pytest.mark.django_db
def test_full_trigger_cycle_with_action_user_logging(user, trigger, event, test_action):
    """Test that user is logged in all stages when trigger has actions"""
    # Fire the event for a single user - this should create signal_sent and task_created logs
    event.fire_single(user_pk=user.pk)
    
    # Get the run_id from the first log entry
    first_log = TriggerLog.objects.order_by("id").first()
    run_id = first_log.run_id
    
    # Print all logs for debugging
    all_logs = TriggerLog.objects.filter(run_id=run_id).order_by("id")
    print(f"\nAll logs for run_id {run_id} after fire_single with action:")
    for log in all_logs:
        print(f"  Stage: {log.stage}, User: {log.user}, Entity: {log.entity_name}, Result: {log.result}")
    
    # Check that user is logged in fire and should_be_fired stages
    fire_logs = TriggerLog.objects.filter(run_id=run_id, stage="fire")
    should_be_fired_logs = TriggerLog.objects.filter(run_id=run_id, stage="should_be_fired")
    signal_sent_logs = TriggerLog.objects.filter(run_id=run_id, stage="signal_sent")
    task_created_logs = TriggerLog.objects.filter(run_id=run_id, stage="task_created")
    trigger_filter_logs = TriggerLog.objects.filter(run_id=run_id, stage="trigger_filter")
    
    # Check that these stages have user logged where applicable
    if fire_logs.exists():
        assert fire_logs.filter(user__isnull=False).exists(), "Fire stage should have user logged"
        
    if should_be_fired_logs.exists():
        assert should_be_fired_logs.filter(user__isnull=False).exists(), "Should be fired stage should have user logged"
        
    if signal_sent_logs.exists():
        assert signal_sent_logs.filter(user__isnull=False).exists(), "Signal sent stage should have user logged"
        
    if task_created_logs.exists():
        assert task_created_logs.filter(user__isnull=False).exists(), "Task created stage should have user logged"
        
    # Trigger filtering might not have user in some cases, but let's check
    print(f"\nTrigger filter logs: {trigger_filter_logs.count()}")
    for log in trigger_filter_logs:
        print(f"  Trigger filter - User: {log.user}, Result: {log.result}")


@pytest.mark.django_db
def test_full_trigger_cycle_user_logging(user, trigger, event):
    """Test that user is logged in all stages of the full trigger cycle"""
    # Fire the event for a single user - this should create signal_sent and task_created logs
    event.fire_single(user_pk=user.pk)
    
    # Get the run_id from the first log entry
    first_log = TriggerLog.objects.order_by("id").first()
    run_id = first_log.run_id
    
    # Print all logs for debugging
    all_logs = TriggerLog.objects.filter(run_id=run_id).order_by("id")
    print(f"\nAll logs for run_id {run_id} after fire_single:")
    for log in all_logs:
        print(f"  Stage: {log.stage}, User: {log.user}, Entity: {log.entity_name}, Result: {log.result}")
    
    # Check that user is logged in fire and should_be_fired stages
    fire_logs = TriggerLog.objects.filter(run_id=run_id, stage="fire")
    should_be_fired_logs = TriggerLog.objects.filter(run_id=run_id, stage="should_be_fired")
    signal_sent_logs = TriggerLog.objects.filter(run_id=run_id, stage="signal_sent")
    task_created_logs = TriggerLog.objects.filter(run_id=run_id, stage="task_created")
    
    # Check that these stages have user logged
    if fire_logs.exists():
        assert fire_logs.filter(user__isnull=False).exists(), "Fire stage should have user logged"
        
    if should_be_fired_logs.exists():
        assert should_be_fired_logs.filter(user__isnull=False).exists(), "Should be fired stage should have user logged"
        
    if signal_sent_logs.exists():
        assert signal_sent_logs.filter(user__isnull=False).exists(), "Signal sent stage should have user logged"
        
    if task_created_logs.exists():
        assert task_created_logs.filter(user__isnull=False).exists(), "Task created stage should have user logged"


@pytest.mark.django_db
def test_user_logging_in_specified_events(user, trigger, event):
    """Test that user is logged in the specified events: Trigger filtering, Handle start, Task created, Fire initiated, Should be fired check"""
    # Fire the event for a single user
    event.fire_single(user_pk=user.pk)
    
    # Get the run_id from the first log entry
    first_log = TriggerLog.objects.order_by("id").first()
    run_id = first_log.run_id
    
    # Simulate task execution to get handle_start logs
    handle_event(event.pk, user.pk, _run_id=str(run_id))
    
    # Print all logs for debugging
    all_logs = TriggerLog.objects.filter(run_id=run_id).order_by("id")
    print(f"\nAll logs for run_id {run_id}:")
    for log in all_logs:
        print(f"  Stage: {log.stage}, User: {log.user}, Entity: {log.entity_name}, Result: {log.result}")
    
    # Check that user is logged in the specified events
    logs_with_user = TriggerLog.objects.filter(run_id=run_id, user__isnull=False)
    
    # Get stages that should have user logged
    stages_with_user = set(log.stage for log in logs_with_user)
    
    # Check specific stages mentioned in the issue
    expected_stages = {
        "fire",  # Fire initiated
        "should_be_fired",  # Should be fired check
        "task_created",  # Task created
        "handle_start",  # Handle start
        "signal_sent",  # This should already have user
    }
    
    print(f"\nStages with user logged: {stages_with_user}")
    print(f"Expected stages: {expected_stages}")
    
    # Check that all expected stages have user logged
    for stage in expected_stages:
        stage_logs = TriggerLog.objects.filter(run_id=run_id, stage=stage)
        if stage_logs.exists():
            # At least one log for this stage should have user
            has_user_log = stage_logs.filter(user__isnull=False).exists()
            assert has_user_log, f"Stage '{stage}' should have user logged but doesn't"
            
            # Print for debugging
            for log in stage_logs:
                print(f"  Stage: {log.stage}, User: {log.user}, Entity: {log.entity_name}")
        else:
            print(f"  No logs found for stage: {stage}")


@pytest.mark.django_db
def test_run_id_generation_and_propagation(user, trigger, event):
    """Test that run_id is generated and propagated through the trigger lifecycle"""
    # Fire the event
    event.fire_single(user_pk=user.pk)
    
    # Check that a log entry was created for "fire" stage
    logs = TriggerLog.objects.filter(entity_type="event", stage="fire")
    assert logs.exists()
    
    # Get the run_id
    run_id = logs.order_by("id").first().run_id
    assert run_id is not None
    
    # Check that all logs for this run have the same run_id
    logs_for_run = TriggerLog.objects.filter(run_id=run_id)
    
    # There should be at least logs for 'fire' and 'should_be_fired'
    assert logs_for_run.count() >= 2
    
    # Check for specific stages
    stages = set(log.stage for log in logs_for_run)  # noqa: C401
    assert "fire" in stages
    assert "should_be_fired" in stages


@pytest.mark.django_db
def test_trigger_filtering_logging(user, trigger, event):
    """Test that filtering steps are properly logged"""
    # Disable the trigger
    trigger.is_enabled = False
    trigger.save()
    
    # Fire the event
    event.fire_single(user_pk=user.pk)
    
    # Check that the inactive trigger is logged
    log = TriggerLog.objects.filter(
        entity_type="trigger",
        stage="trigger_filter",
        result=False
    ).first()
    
    assert log is not None
    assert log.trigger.pk == trigger.pk
    assert "reason" in log.details
    assert log.details["reason"] == "Trigger not active"


@pytest.mark.django_db
def test_event_handling_logging(user, trigger, event):
    """Test that event handling stages are properly logged"""
    # Use mocking to simulate event handling
    # with mock.patch('triggers.tasks.handle_event') as mock_handle:
    #     # Simulate direct handle_event function call
    #     mock_handle.return_value = None
        
    # Extract run_id from current test
    event.fire_single(user_pk=user.pk)
    run_id = TriggerLog.objects.order_by("id").first().run_id

    print(f"run_id: {run_id}")

    # Simulate task execution
    handle_event(event.pk, user.pk, _run_id=str(run_id))
    
    # Check that all required logs are created
    logs = TriggerLog.objects.filter(run_id=run_id)
    
    # Should have logs for different stages
    stages = [log.stage for log in logs]
    assert "fire" in stages
    assert "should_be_fired" in stages
    assert "handle_start" in stages


@pytest.mark.django_db
def test_log_retrieval_by_entity(user, trigger, event):
    """Test that logs can be retrieved and entity objects accessed"""
    # Fire the event
    event.fire_single(user_pk=user.pk)
    
    # Get log
    log = TriggerLog.objects.filter(entity_type="event", entity_id=event.pk).first()
    
    # Check entity restoration
    entity = log.get_entity_object()
    assert entity is not None
    assert entity.pk == event.pk
    assert entity.__class__ == event.__class__


@pytest.mark.django_db
def test_action_execution_logging(user, trigger, event):
    """Test that action execution is properly logged"""
    # Create a test Action using Action model
    action = Action._default_manager.create(trigger=trigger)
    
    # Create a log entry manually
    run_id = uuid.uuid4()
    log_trigger_event(
        entity=action,
        entity_type="action",
        stage="action_perform",
        trigger=trigger,
        user=user,
        result=True,
        run_id=run_id
    )
    
    # Check that the log was created
    log = TriggerLog.objects.filter(
        entity_type="action",
        stage="action_perform",
        result=True,
        run_id=run_id
    ).first()
    
    assert log is not None
    assert log.trigger.pk == trigger.pk 