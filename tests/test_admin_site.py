from collections import defaultdict
from typing import Dict, List, Mapping, Type, Union

import pytest
from typing_extensions import TypeAlias

from tests.app.models import (
    ClockEvent,
    HasUncompletedTaskCondition,
    SendEmailAction,
    TaskCompletedEvent,
)
from triggers.models import Action, ActionCountCondition, ActionFrequencyCondition, Condition, Event

TriggerComponent: TypeAlias = Union[Action, Condition, Event]


expected_trigger_components: Mapping[str, List[Type[TriggerComponent]]] = {
    'action': [
        SendEmailAction,
    ],
    'conditions': [
        ActionCountCondition,
        ActionFrequencyCondition,
        HasUncompletedTaskCondition,
    ],
    'events': [
        ClockEvent,
        TaskCompletedEvent,
    ],
}


@pytest.mark.django_db()
def test_available_trigger_components(admin_client):
    response = admin_client.get('/admin/triggers/trigger/add/')
    assert response.status_code == 200
    actual_trigger_components: Dict[str, list[Type[TriggerComponent]]] = defaultdict(list)
    for inline_formset in response.context_data['inline_admin_formsets']:
        actual_trigger_components[inline_formset.formset.prefix] = [
            empty_form.instance.__class__ for empty_form
            in inline_formset.formset.empty_forms
        ]
    assert actual_trigger_components == expected_trigger_components
