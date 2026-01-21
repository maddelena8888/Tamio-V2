"""
Client utility functions for canonical client creation.

This module ensures all clients have consistent structure across
all entry points: manual onboarding, Xero sync, dashboard, and scenarios.
"""
from typing import Dict, Any, Optional
from decimal import Decimal
from app.data.models import Client
from app.data.billing_schemas import (
    get_default_billing_config,
    validate_billing_config
)


def build_canonical_client(
    user_id: str,
    name: str,
    client_type: str,
    currency: str = "USD",
    status: str = "active",
    payment_behavior: Optional[str] = None,
    churn_risk: Optional[str] = None,
    scope_risk: Optional[str] = None,
    billing_config: Optional[Dict[str, Any]] = None,
    notes: Optional[str] = None
) -> Client:
    """
    Build a canonical client with all required fields.

    Ensures consistent structure across all entry points:
    - Manual onboarding
    - Xero sync
    - Dashboard client creation
    - Scenario analysis

    Args:
        user_id: User ID who owns this client
        name: Client name / legal entity
        client_type: One of "retainer", "project", "usage", "mixed"
        currency: Currency code (ISO 4217, e.g., USD, EUR, GBP)
        status: Client status ("active", "paused", "deleted")
        payment_behavior: Typical payment behavior ("on_time", "delayed", "unknown")
        churn_risk: Churn risk level ("low", "medium", "high")
        scope_risk: Scope creep risk level ("low", "medium", "high")
        billing_config: Billing configuration dictionary (type-specific)
        notes: Optional notes about the client

    Returns:
        Client model instance with canonical structure

    Examples:
        >>> # Retainer client
        >>> client = build_canonical_client(
        ...     user_id="user_123",
        ...     name="Acme Corp",
        ...     client_type="retainer",
        ...     billing_config={
        ...         "frequency": "monthly",
        ...         "invoice_day": 1,
        ...         "amount": 5000,
        ...         "payment_terms": "net_30"
        ...     }
        ... )

        >>> # Project client from Xero
        >>> client = build_canonical_client(
        ...     user_id="user_123",
        ...     name="Beta Inc",
        ...     client_type="project",
        ...     payment_behavior="on_time",
        ...     billing_config={
        ...         "xero_contact_id": "abc-123",
        ...         "source": "xero_sync"
        ...     },
        ...     notes="Imported from Xero"
        ... )
    """
    # Set defaults for optional fields
    if payment_behavior is None:
        payment_behavior = "unknown"

    if churn_risk is None:
        churn_risk = "low"

    if scope_risk is None:
        scope_risk = "low"

    # Validate and normalize billing config
    if billing_config is None:
        billing_config = get_default_billing_config(client_type)
    else:
        try:
            billing_config = validate_billing_config(client_type, billing_config)
        except ValueError:
            # If validation fails, merge with defaults
            default_config = get_default_billing_config(client_type)
            billing_config = {**default_config, **billing_config}

    # Create canonical client
    return Client(
        user_id=user_id,
        name=name,
        client_type=client_type,
        currency=currency,
        status=status,
        payment_behavior=payment_behavior,
        churn_risk=churn_risk,
        scope_risk=scope_risk,
        billing_config=billing_config,
        notes=notes
    )


def enrich_client_from_xero_data(
    client: Client,
    xero_data: Dict[str, Any]
) -> Client:
    """
    Enrich a client with additional data from Xero.

    Args:
        client: Existing client instance
        xero_data: Dictionary containing Xero API response data

    Returns:
        Enriched client instance
    """
    # Extract payment behavior from payment terms
    if "payment_terms" in xero_data:
        terms = xero_data["payment_terms"]
        if isinstance(terms, int):
            if terms <= 14:
                client.payment_behavior = "on_time"
            elif terms <= 30:
                client.payment_behavior = "on_time"
            else:
                client.payment_behavior = "delayed"

    # Add Xero contact ID to billing config
    if "contact_id" in xero_data:
        if client.billing_config is None:
            client.billing_config = {}
        client.billing_config["xero_contact_id"] = xero_data["contact_id"]
        client.billing_config["source"] = "xero_sync"

    # Add currency from Xero
    if "default_currency" in xero_data:
        client.currency = xero_data["default_currency"]

    return client


def update_client_billing_from_repeating_invoice(
    client: Client,
    repeating_invoice: Dict[str, Any]
) -> Client:
    """
    Update client billing configuration from Xero repeating invoice.

    Args:
        client: Existing client instance
        repeating_invoice: Xero repeating invoice data

    Returns:
        Updated client instance with retainer billing config
    """
    # Change client type to retainer if we have repeating invoice
    client.client_type = "retainer"

    # Extract billing details
    amount = Decimal(str(repeating_invoice.get("total", 0)))
    schedule = repeating_invoice.get("schedule", {})

    # Map Xero schedule unit to our frequency
    unit = schedule.get("unit", "MONTHLY")
    period = schedule.get("period", 1)

    # Determine frequency based on unit and period
    if unit == "WEEKLY":
        frequency = "weekly" if period == 1 else "bi_weekly"
    elif unit == "MONTHLY":
        frequency = "monthly"
    elif unit == "QUARTERLY":
        frequency = "quarterly"
    else:
        frequency = "monthly"  # Default

    # Get invoice day (day of month when invoice is sent)
    # Default to 1st of month
    invoice_day = 1

    # Build retainer billing config
    billing_config = {
        "frequency": frequency,
        "invoice_day": invoice_day,
        "amount": float(amount),
        "payment_terms": "net_30",  # Default, can be overridden
        "source": "xero_sync",
        "xero_repeating_invoice_id": repeating_invoice.get("repeating_invoice_id")
    }

    # Preserve existing fields from current billing_config
    if client.billing_config:
        # Preserve xero_contact_id
        if "xero_contact_id" in client.billing_config:
            billing_config["xero_contact_id"] = client.billing_config["xero_contact_id"]
        # Preserve outstanding_invoices (from invoice sync)
        if "outstanding_invoices" in client.billing_config:
            billing_config["outstanding_invoices"] = client.billing_config["outstanding_invoices"]

    client.billing_config = billing_config

    # Also set the direct field on the model for UI badge display
    client.xero_repeating_invoice_id = repeating_invoice.get("repeating_invoice_id")

    return client


def ensure_client_has_canonical_structure(client: Client) -> Client:
    """
    Ensure an existing client has all canonical fields.

    Useful for backfilling data on clients created before
    canonical structure was enforced.

    Args:
        client: Existing client instance

    Returns:
        Client with canonical structure
    """
    # Set defaults for missing fields
    if client.payment_behavior is None:
        client.payment_behavior = "unknown"

    if client.churn_risk is None:
        client.churn_risk = "low"

    if client.scope_risk is None:
        client.scope_risk = "low"

    # Ensure billing config has proper structure
    if client.billing_config is None or not client.billing_config:
        client.billing_config = get_default_billing_config(client.client_type)
    else:
        # Add source field if missing
        if "source" not in client.billing_config:
            # Infer source
            if "xero_contact_id" in client.billing_config or "xero_repeating_invoice_id" in client.billing_config:
                client.billing_config["source"] = "xero_sync"
            else:
                client.billing_config["source"] = "manual"

    return client
