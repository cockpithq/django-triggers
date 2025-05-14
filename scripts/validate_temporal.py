#!/usr/bin/env python
"""
Temporal validation and diagnostic script.

This script helps to diagnose issues with Temporal worker configuration
by validating workflows and printing detailed diagnostic information.
"""

import os
import sys
import asyncio
import logging
import traceback
import inspect

# Set up Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.app.settings")

import django

django.setup()

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("temporal-validator")

# Import components
from temporalio.worker import Worker
from temporalio.client import Client
import temporalio
import temporalio.workflow
from triggers import settings as triggers_settings
from triggers.temporal.workflows import (
    TriggerWorkflow,
    fetch_trigger_definition,
    evaluate_condition,
    perform_action,
    log_activity,
)


def print_header(title):
    """Print a section header."""
    print("\n" + "=" * 80)
    print(f" {title}")
    print("=" * 80)


async def validate_temporal_sdk():
    """Validate Temporal SDK version and installation."""
    print_header("TEMPORAL SDK INFORMATION")

    try:
        print(f"Temporal SDK Version: {temporalio.__version__}")
        print(f"Python Version: {sys.version}")

        print("\nImportant modules:")
        for module_name in [
            "temporalio.workflow",
            "temporalio.activity",
            "temporalio.client",
            "temporalio.worker",
        ]:
            module = sys.modules.get(module_name)
            if module:
                print(f"✅ {module_name}: Found")
            else:
                print(f"❌ {module_name}: Not found")

        return True
    except Exception as e:
        print(f"Error validating Temporal SDK: {e}")
        traceback.print_exc()
        return False


def validate_workflow_signature(workflow_class):
    """Validate that a workflow class has proper signatures."""
    print_header(f"WORKFLOW SIGNATURE: {workflow_class.__name__}")

    has_errors = False

    # Check for @workflow.defn decorator
    if not hasattr(workflow_class, "__temporal_workflow_definition__"):
        print(f"❌ Missing @workflow.defn decorator on {workflow_class.__name__}")
        has_errors = True
    else:
        print(
            f"✅ Has @workflow.defn decorator: {getattr(workflow_class, '__temporal_workflow_definition__', None)}"
        )

    # Check for @workflow.run method
    run_method = None
    for name, method in inspect.getmembers(workflow_class, inspect.isfunction):
        if hasattr(method, "__temporal_workflow_run__"):
            run_method = method
            break

    if not run_method:
        print(f"❌ Missing @workflow.run method on {workflow_class.__name__}")
        has_errors = True
    else:
        print(f"✅ Has @workflow.run method: {run_method.__name__}")

        # Check run method signature
        sig = inspect.signature(run_method)
        print(f"   Method signature: {sig}")

        # Check parameter types
        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            if param.annotation == inspect.Parameter.empty:
                print(f"⚠️ Parameter {param_name} has no type annotation")

        # Check return type
        if sig.return_annotation == inspect.Parameter.empty:
            print("⚠️ Return value has no type annotation")

    return not has_errors


def validate_activity_signature(activity_func):
    """Validate that an activity function has proper signature."""
    print_header(f"ACTIVITY SIGNATURE: {activity_func.__name__}")

    # Check for @activity.defn decorator
    if not hasattr(activity_func, "__temporal_activity_definition__"):
        print(f"❌ Missing @activity.defn decorator on {activity_func.__name__}")
        return False
    else:
        print(
            f"✅ Has @activity.defn decorator: {getattr(activity_func, '__temporal_activity_definition__', None)}"
        )

    # Check signature
    sig = inspect.signature(activity_func)
    print(f"   Method signature: {sig}")

    # Check parameter types
    for param_name, param in sig.parameters.items():
        if param.annotation == inspect.Parameter.empty:
            print(f"⚠️ Parameter {param_name} has no type annotation")

    # Check return type
    if sig.return_annotation == inspect.Parameter.empty:
        print("⚠️ Return value has no type annotation")

    return True


async def connect_to_temporal():
    """Attempt to connect to Temporal server."""
    print_header("TEMPORAL SERVER CONNECTION")

    host = triggers_settings.TEMPORAL_HOST
    namespace = triggers_settings.TEMPORAL_NAMESPACE

    print(f"Host: {host}")
    print(f"Namespace: {namespace}")

    try:
        client = await Client.connect(host, namespace=namespace)
        print("✅ Successfully connected to Temporal server")
        print(f"   Client namespace: {client.namespace}")
        return client
    except Exception as e:
        print(f"❌ Failed to connect to Temporal server: {e}")
        traceback.print_exc()
        return None


async def test_register_worker(client):
    """Test if Worker registration works."""
    print_header("WORKER REGISTRATION")

    if not client:
        print("❌ Cannot test worker without a client connection")
        return False

    task_queue = "validator-test-queue"
    print(f"Task queue: {task_queue}")

    try:
        worker = Worker(
            client,
            task_queue=task_queue,
            workflows=[TriggerWorkflow],
            activities=[
                fetch_trigger_definition,
                evaluate_condition,
                perform_action,
                log_activity,
            ],
        )
        print("✅ Successfully created Worker instance")

        # We don't actually start the worker, just testing registration
        return True
    except Exception as e:
        print(f"❌ Failed to create Worker instance: {e}")
        traceback.print_exc()
        return False


async def test_workflow_type_registration(client):
    """Test registering just the workflow type."""
    print_header("WORKFLOW TYPE REGISTRATION")

    if not client:
        print("❌ Cannot test workflow registration without a client connection")
        return False

    try:
        worker = Worker(
            client,
            task_queue="validator-test-queue-workflow-only",
            workflows=[TriggerWorkflow],
        )
        print("✅ Successfully registered workflow type")
        return True
    except Exception as e:
        print(f"❌ Failed to register workflow type: {e}")
        traceback.print_exc()

        # Print more detailed information about the workflow
        print("\nWorkflow details:")
        print(f"Workflow class: {TriggerWorkflow}")
        print(
            f"Workflow name: {getattr(TriggerWorkflow, '__temporal_workflow_definition__', {}).get('name', 'Unknown')}"
        )

        # Check if the run method exists and has proper annotation
        run_method = None
        for name, method in inspect.getmembers(TriggerWorkflow, inspect.isfunction):
            if hasattr(method, "__temporal_workflow_run__"):
                run_method = method
                break

        if run_method:
            print(f"Run method: {run_method.__name__}")
            print(f"Run method signature: {inspect.signature(run_method)}")
        else:
            print("No run method found with @workflow.run decoration")

        return False


async def main():
    """Run all validation checks."""
    print_header("TEMPORAL VALIDATOR")
    print("This script validates Temporal setup for django-triggers.\n")

    # Track if all validations passed
    all_passed = True

    # Validate SDK
    sdk_ok = await validate_temporal_sdk()
    all_passed = all_passed and sdk_ok

    # Validate workflow signatures
    workflow_sig_ok = validate_workflow_signature(TriggerWorkflow)
    all_passed = all_passed and workflow_sig_ok

    # Validate activity signatures
    for activity_func in [
        fetch_trigger_definition,
        evaluate_condition,
        perform_action,
        log_activity,
    ]:
        activity_sig_ok = validate_activity_signature(activity_func)
        all_passed = all_passed and activity_sig_ok

    # Try to connect to Temporal server
    client = await connect_to_temporal()
    server_ok = client is not None
    all_passed = all_passed and server_ok

    # Test worker registration
    if server_ok:
        worker_ok = await test_register_worker(client)
        all_passed = all_passed and worker_ok

        workflow_reg_ok = await test_workflow_type_registration(client)
        all_passed = all_passed and workflow_reg_ok

    # Print final result
    print_header("VALIDATION RESULTS")
    if all_passed:
        print("✅ All validations passed. Temporal integration should work correctly.")
    else:
        print("❌ Some validations failed. See above for details.")

    return 0 if all_passed else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
