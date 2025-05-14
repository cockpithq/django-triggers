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
