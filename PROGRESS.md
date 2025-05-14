# Project Progress

## Testing

### TS: 2025-05-14 22:25:14 CEST

---

## PROBLEM: Needed to run tests

WHAT WAS DONE:

- Installed missing dependency `setuptools` using uv
- Successfully ran pytest with `python -m pytest --ds=tests.app.settings`
- All 17 tests passed with 89% code coverage

---

MEMO:

- Test suite requires Django settings to be specified with `--ds=tests.app.settings`
- There are some deprecation warnings that could be addressed in future updates

## Temporal Integration

### TS: 2025-05-14 23:43:33 CEST

---

## PROBLEM: Testing Temporal workflow integration

WHAT WAS DONE:

- Verified Temporal server is running (localhost:7233)
- Attempted to run Temporal worker
- Ran test integration script

---

MEMO:

- Worker failed with error due to trying to use Django ORM directly in async context
- Fixed by wrapping Django ORM calls in `sync_to_async`

### TS: 2025-05-15 00:12:09 CEST

---

## PROBLEM: Implement a medical form BMI check workflow with Temporal

WHAT WAS DONE:

- Created a script to test the Temporal integration with simulated medical form data
- Successfully ran and fixed the sync_to_async wrapper for Django ORM operations
- Successfully fired an event with BMI data that triggered the workflow

---

MEMO:

- When working with Django in async context (like Temporal), always wrap DB operations in `sync_to_async`
- The BMI-based doctor appointment scheduler is a good example of event-based workflows
- Temporal offers better reliability and observability than Celery for these workflows

### TS: 2025-05-15 00:22:59 CEST

---

## PROBLEM: Verify medical form workflow and test reliability

WHAT WAS DONE:

- Ran the test_form_submit.py script again to verify workflow execution
- Successfully simulated form submission with BMI of 46.3
- Attempted to run the test suite with pytest, identified an issue with temporal test imports

---

MEMO:

- The workflow correctly triggers based on the high BMI value
- Test suite has an incompatibility with current Temporal SDK version (missing WorkflowHistory import)
- Temporal integration works correctly for the main use case despite the test issues

### TS: 2025-05-15 00:32:51 CEST

---

## PROBLEM: Fix Temporal workflow retry policy error

WHAT WAS DONE:

- Identified error in Temporal workflow execution: 'dict' object has no attribute 'apply_to_proto'
- Fixed the retry_policy implementation in hooks.py to use RetryPolicy objects instead of dictionary
- Successfully executed the medical form workflow with high BMI value
- Verified appointment creation with the correct details

---

MEMO:

- Temporal RetryPolicy must use timedelta objects, not string values like "1s"
- The workflow ID format is "trigger-{trigger_id}-{user_id}-{event_id}" for deduplication
- For idempotency, rerunning the same event with the same user will detect duplicate execution
- Multiple doctor appointments were successfully created based on the BMI threshold rule

### TS: 2025-05-15 00:39:11 CEST

---

## PROBLEM: Improve workflow execution logging and readability

WHAT WAS DONE:

- Enhanced logging in Temporal workflows to show steps and progress
- Added emojis and descriptive messages to create a narrative of the workflow execution
- Improved worker and activity logging to tell a coherent story
- Updated the test script to summarize results of workflow execution

---

MEMO:

- Narrative-focused logging helps understand the sequence of events in complex workflows
- Added structured logging with logger names to distinguish between components
- Workflow logging shows the complete process: trigger lookup → condition evaluation → action execution
- Enhanced logging is essential for complex workflows that span multiple components
