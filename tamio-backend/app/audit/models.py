"""
Audit Log model for tracking all data changes.

This provides a comprehensive audit trail for debugging, compliance, and
understanding data flow through the system.
"""
from sqlalchemy import Column, String, DateTime, Text, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from app.database import Base
from app.data.base import generate_id


class AuditLog(Base):
    """
    Audit Log - Tracks all data changes in the system.

    Every create, update, delete, and sync operation is logged here,
    providing a complete audit trail for:
    - Debugging data issues
    - Compliance requirements
    - Understanding data provenance
    - Tracking sync operations
    """

    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True, default=lambda: generate_id("audit"))

    # What changed?
    entity_type = Column(String, nullable=False, index=True)
    # Options: "client", "expense_bucket", "obligation", "schedule", "payment", "cash_event", etc.

    entity_id = Column(String, nullable=False, index=True)

    # What kind of change?
    action = Column(String, nullable=False, index=True)
    # Options:
    # - "create": New record created
    # - "update": Record updated
    # - "delete": Record deleted (soft or hard)
    # - "sync_push": Pushed to external system
    # - "sync_pull": Pulled from external system
    # - "sync_error": Sync failed
    # - "reconcile": Reconciliation action
    # - "archive": Record archived

    # What field changed? (for updates)
    field_name = Column(String, nullable=True)

    # What were the values?
    old_value = Column(JSONB, nullable=True)
    new_value = Column(JSONB, nullable=True)

    # Who made the change?
    user_id = Column(String, nullable=True, index=True)

    # What triggered the change?
    source = Column(String, nullable=False, default="api")
    # Options:
    # - "api": Direct API call
    # - "xero_sync": Xero sync process
    # - "quickbooks_sync": QuickBooks sync process
    # - "system": System/background process
    # - "migration": Data migration
    # - "admin": Admin action

    # Additional context (renamed from 'metadata' which is reserved in SQLAlchemy)
    extra_data = Column("extra_data", JSONB, nullable=True)
    # Example:
    # {
    #     "request_id": "abc123",
    #     "ip_address": "192.168.1.1",
    #     "user_agent": "...",
    #     "integration_type": "xero",
    #     "sync_direction": "push"
    # }

    notes = Column(Text, nullable=True)

    # When?
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)

    # Indexes for common queries
    __table_args__ = (
        Index("ix_audit_log_entity", "entity_type", "entity_id"),
        Index("ix_audit_log_entity_action", "entity_type", "action"),
        Index("ix_audit_log_user_time", "user_id", "created_at"),
        Index("ix_audit_log_source", "source"),
    )

    def __repr__(self):
        return (
            f"<AuditLog {self.id}: "
            f"{self.action} on {self.entity_type}/{self.entity_id} "
            f"at {self.created_at}>"
        )
