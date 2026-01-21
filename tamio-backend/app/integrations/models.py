"""
Integration Mapping models for centralized external system ID management.

This module provides a unified registry for tracking relationships between
Tamio entities and external system identifiers (Xero, QuickBooks, etc.).

Benefits over scattered xero_contact_id fields:
- Single source of truth for all integration mappings
- Easy to add new integrations without schema changes
- Supports multiple mappings per entity (e.g., same client in Xero AND QuickBooks)
- Centralized sync status tracking
- Query-friendly (find entity by external ID, find external ID by entity)
"""
from sqlalchemy import Column, String, DateTime, Text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.data.base import generate_id


class IntegrationMapping(Base):
    """
    Integration Mapping - Links Tamio entities to external system identifiers.

    This centralizes all external ID management, replacing scattered fields like
    xero_contact_id, quickbooks_customer_id, etc. on individual entity tables.

    Design Principles:
    - One entity can have multiple mappings (to different integrations)
    - One external ID maps to exactly one entity (within its type)
    - Sync status is tracked per mapping, not per entity
    - Metadata can store integration-specific details
    """

    __tablename__ = "integration_mappings"

    id = Column(String, primary_key=True, default=lambda: generate_id("intmap"))

    # Tamio Entity Reference
    entity_type = Column(String, nullable=False, index=True)
    # Options: "client", "expense_bucket", "obligation", "cash_account", "user"
    entity_id = Column(String, nullable=False, index=True)

    # External System Reference
    integration_type = Column(String, nullable=False, index=True)
    # Options: "xero", "quickbooks", "stripe", etc.
    external_id = Column(String, nullable=False, index=True)
    external_type = Column(String, nullable=False)
    # Options depend on integration:
    #   Xero: "contact", "invoice", "bill", "repeating_invoice", "bank_transaction", "account"
    #   QuickBooks: "customer", "vendor", "invoice", "bill", "account"

    # Sync Status
    sync_status = Column(String, nullable=False, default="synced")
    # Options:
    # - "synced": In sync with external system
    # - "pending_push": Tamio changes need to be pushed
    # - "pending_pull": External changes need to be pulled
    # - "conflict": Both systems have changes (needs resolution)
    # - "error": Sync failed

    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)

    # Extra data for integration-specific details
    # Note: "metadata" is a reserved name in SQLAlchemy, so we use "extra_data"
    extra_data = Column(JSONB, nullable=True)
    # Example extra_data:
    # {
    #     "xero_tenant_id": "abc123",
    #     "last_modified_time": "2024-01-15T10:30:00Z",
    #     "contact_type": "SUPPLIER",
    #     "has_validation_errors": false
    # }

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Indexes and Constraints
    __table_args__ = (
        # Ensure each entity has at most one mapping per integration type
        UniqueConstraint(
            "entity_type", "entity_id", "integration_type",
            name="uq_integration_mapping_entity"
        ),
        # Ensure each external ID is unique within integration/type
        UniqueConstraint(
            "integration_type", "external_id", "external_type",
            name="uq_integration_mapping_external"
        ),
        # Common query patterns
        Index("ix_integration_mapping_entity", "entity_type", "entity_id"),
        Index("ix_integration_mapping_external", "integration_type", "external_id"),
        Index("ix_integration_mapping_status", "sync_status"),
        Index("ix_integration_mapping_type_status", "integration_type", "sync_status"),
    )

    def __repr__(self):
        return (
            f"<IntegrationMapping {self.id}: "
            f"{self.entity_type}/{self.entity_id} <-> "
            f"{self.integration_type}/{self.external_type}/{self.external_id}>"
        )


class IntegrationConnection(Base):
    """
    Integration Connection - Tracks user's connection to external systems.

    Stores OAuth tokens and connection metadata for each user's integration.
    This replaces the xero_connections table with a more general model.
    """

    __tablename__ = "integration_connections"

    id = Column(String, primary_key=True, default=lambda: generate_id("intconn"))
    user_id = Column(String, nullable=False, index=True)
    integration_type = Column(String, nullable=False, index=True)
    # Options: "xero", "quickbooks", "stripe", etc.

    # Connection Status
    status = Column(String, nullable=False, default="active")
    # Options: "active", "expired", "revoked", "error"

    # OAuth Tokens (encrypted in production)
    access_token = Column(Text, nullable=True)
    refresh_token = Column(Text, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)

    # Integration-specific identifiers
    tenant_id = Column(String, nullable=True)  # Xero tenant ID
    realm_id = Column(String, nullable=True)   # QuickBooks realm ID

    # Connection extra data
    # Note: "metadata" is a reserved name in SQLAlchemy, so we use "extra_data"
    extra_data = Column(JSONB, nullable=True)
    # Example:
    # {
    #     "organization_name": "Acme Corp",
    #     "scopes": ["accounting.transactions", "accounting.contacts"],
    #     "connected_at": "2024-01-15T10:30:00Z"
    # }

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Constraints
    __table_args__ = (
        # Each user has at most one connection per integration
        UniqueConstraint(
            "user_id", "integration_type",
            name="uq_integration_connection_user"
        ),
        Index("ix_integration_connection_user", "user_id"),
        Index("ix_integration_connection_type", "integration_type"),
        Index("ix_integration_connection_status", "status"),
    )

    def __repr__(self):
        return (
            f"<IntegrationConnection {self.id}: "
            f"user={self.user_id} type={self.integration_type} status={self.status}>"
        )

    @property
    def is_active(self) -> bool:
        """Check if connection is active and tokens are valid."""
        from datetime import datetime, timezone
        if self.status != "active":
            return False
        if self.token_expires_at and self.token_expires_at < datetime.now(timezone.utc):
            return False
        return True
