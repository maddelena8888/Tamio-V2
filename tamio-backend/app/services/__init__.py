"""
Consolidated services module.

All business logic services are exported from this module.
Services are organized by domain but re-exported here for convenience.

Usage:
    from app.services import ObligationService, NotificationService
    from app.services import AuditService, ExecutionService
"""

# Obligation services (already in services/)
from app.services.obligations import ObligationService

# Exchange rate services (already in services/)
from app.services.exchange_rates import (
    fetch_rates_from_ecb,
    get_fallback_rates,
    store_exchange_rates,
    get_rate,
    convert_amount,
    get_latest_rates,
    refresh_exchange_rates,
    SUPPORTED_CURRENCIES,
)

# Notification services
from app.notifications.service import NotificationService, get_notification_service

# Execution services
from app.execution.service import ExecutionService

# Audit services
from app.audit.services import AuditService, create_audit_service

# Integration services
from app.integrations.services import (
    IntegrationMappingService,
    IntegrationConnectionService,
)

__all__ = [
    # Obligation
    "ObligationService",
    # Exchange rates
    "fetch_rates_from_ecb",
    "get_fallback_rates",
    "store_exchange_rates",
    "get_rate",
    "convert_amount",
    "get_latest_rates",
    "refresh_exchange_rates",
    "SUPPORTED_CURRENCIES",
    # Notification
    "NotificationService",
    "get_notification_service",
    # Execution
    "ExecutionService",
    # Audit
    "AuditService",
    "create_audit_service",
    # Integration
    "IntegrationMappingService",
    "IntegrationConnectionService",
]
