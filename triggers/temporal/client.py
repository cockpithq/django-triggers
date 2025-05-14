"""
Temporal client adapter for django-triggers.

This module provides connectivity to the Temporal server for workflow execution.
"""

import ssl
from typing import Optional

from temporalio.client import Client, TLSConfig

from triggers import settings as triggers_settings


async def get_temporal_client() -> Client:
    """
    Returns a connected Temporal client based on Django settings.

    This function reads configuration from the django-triggers settings module,
    which in turn reads from the Django project settings.

    Returns:
        Client: A connected Temporal client
    """
    # Get connection settings
    host = triggers_settings.TEMPORAL_HOST
    namespace = triggers_settings.TEMPORAL_NAMESPACE

    # Set up TLS if enabled
    tls: Optional[TLSConfig] = None
    if triggers_settings.TEMPORAL_TLS_ENABLED:
        context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)

        # Add client certificate if provided
        if (
            triggers_settings.TEMPORAL_TLS_CERT_PATH
            and triggers_settings.TEMPORAL_TLS_KEY_PATH
        ):
            context.load_cert_chain(
                certfile=triggers_settings.TEMPORAL_TLS_CERT_PATH,
                keyfile=triggers_settings.TEMPORAL_TLS_KEY_PATH,
            )

        tls = TLSConfig(client_context=context)

    # Connect to the Temporal server
    return await Client.connect(
        host,
        namespace=namespace,
        tls=tls,
    )
