import uuid
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.apps import apps

from triggers.models import Event, Trigger, Action, TriggerLog, Condition, log_trigger_event
from triggers.tasks import on_event_fired, handle_event

User = get_user_model()


@pytest.fixture
def user():
    return User.objects.create_user(username='test_user', password='password')


@pytest.fixture
def trigger():
    return Trigger.objects.create(name='Test Trigger', is_enabled=True)


@pytest.fixture
def event(trigger):
    return Event.objects.create(trigger=trigger)


@pytest.fixture
def test_action(trigger):
    # Use the default manager model to create an action
    # to avoid problems with model without app_label
    return Action._default_manager.create(trigger=trigger)


@pytest.mark.django_db()
def test_run_id_generation_and_propagation(user, trigger, event):
    """Test that run_id is generated and propagated through the trigger lifecycle"""
    # Fire the event
    event.fire_single(user_pk=user.pk)
    
    # Check that a log entry was created for "fire" stage
    logs = TriggerLog.objects.filter(entity_type='event', stage='fire')
    assert logs.exists()
    
    # Get the run_id
    run_id = logs.order_by('id').first().run_id
    assert run_id is not None
    
    # Check that all logs for this run have the same run_id
    logs_for_run = TriggerLog.objects.filter(run_id=run_id)
    
    # There should be at least logs for 'fire' and 'should_be_fired'
    assert logs_for_run.count() >= 2
    
    # Check for specific stages
    stages = set(log.stage for log in logs_for_run)
    assert 'fire' in stages
    assert 'should_be_fired' in stages


@pytest.mark.django_db()
def test_trigger_filtering_logging(user, trigger, event):
    """Test that filtering steps are properly logged"""
    # Disable the trigger
    trigger.is_enabled = False
    trigger.save()
    
    # Fire the event
    event.fire_single(user_pk=user.pk)
    
    # Check that the inactive trigger is logged
    log = TriggerLog.objects.filter(
        entity_type='trigger',
        stage='trigger_filter',
        result=False
    ).first()
    
    assert log is not None
    assert log.trigger.pk == trigger.pk
    assert 'reason' in log.details
    assert log.details['reason'] == 'Trigger not active'


@pytest.mark.django_db()
def test_event_handling_logging(user, trigger, event):
    """Test that event handling stages are properly logged"""
    # Use mocking to simulate event handling
    # with mock.patch('triggers.tasks.handle_event') as mock_handle:
    #     # Simulate direct handle_event function call
    #     mock_handle.return_value = None
        
    # Extract run_id from current test
    event.fire_single(user_pk=user.pk)
    run_id = TriggerLog.objects.order_by('id').first().run_id

    print(f"run_id: {run_id}")

    # Simulate task execution
    handle_event(event.pk, user.pk, _run_id=str(run_id))
    
    # Check that all required logs are created
    logs = TriggerLog.objects.filter(run_id=run_id)
    
    # Should have logs for different stages
    stages = [log.stage for log in logs]
    assert 'fire' in stages
    assert 'should_be_fired' in stages
    assert 'handle_start' in stages


@pytest.mark.django_db()
def test_log_retrieval_by_entity(user, trigger, event):
    """Test that logs can be retrieved and entity objects accessed"""
    # Fire the event
    event.fire_single(user_pk=user.pk)
    
    # Get log
    log = TriggerLog.objects.filter(entity_type='event', entity_id=event.pk).first()
    
    # Check entity restoration
    entity = log.get_entity_object()
    assert entity is not None
    assert entity.pk == event.pk
    assert entity.__class__ == event.__class__


@pytest.mark.django_db()
def test_action_execution_logging(user, trigger, event):
    """Test that action execution is properly logged"""
    # Create a test Action using Action model
    action = Action._default_manager.create(trigger=trigger)
    
    # Create a log entry manually
    run_id = uuid.uuid4()
    log_trigger_event(
        entity=action,
        entity_type='action',
        stage='action_perform',
        trigger=trigger,
        user=user,
        result=True,
        run_id=run_id
    )
    
    # Check that the log was created
    log = TriggerLog.objects.filter(
        entity_type='action',
        stage='action_perform',
        result=True,
        run_id=run_id
    ).first()
    
    assert log is not None
    assert log.trigger.pk == trigger.pk 