"""Client model for revenue sources."""
from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Boolean, Integer, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.data.base import generate_id


class Client(Base):
    """Client model - Page 2: Cash In (Revenue Sources)."""

    __tablename__ = "clients"

    id = Column(String, primary_key=True, default=lambda: generate_id("client"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Core Info
    name = Column(String, nullable=False)
    client_type = Column(String, nullable=False)  # "retainer" | "project" | "usage" | "mixed"
    currency = Column(String, nullable=False, default="USD")
    status = Column(String, nullable=False, default="active")  # "active" | "paused" | "deleted"

    # Risk Indicators
    payment_behavior = Column(String, nullable=True)  # "on_time" | "delayed" | "unknown"
    churn_risk = Column(String, nullable=True)  # "low" | "medium" | "high"
    scope_risk = Column(String, nullable=True)  # "low" | "medium" | "high"

    # V4 Required Fields
    # Payment pattern: average days late (0 = on time, positive = days late)
    avg_payment_delay_days = Column(Integer, nullable=True, default=0)

    # Relationship type: strategic clients get softer tone, transactional get firmer
    relationship_type = Column(String, nullable=True)  # "strategic" | "transactional" | "managed"

    # Revenue concentration: what % of total revenue does this client represent?
    revenue_percent = Column(Numeric(precision=5, scale=2), nullable=True)  # e.g., 15.50 = 15.5%

    # Unified risk level for detection/preparation decisions
    risk_level = Column(String, nullable=True)  # "low" | "medium" | "high" | "critical"

    # Billing Configuration (JSONB - adapts by client_type)
    billing_config = Column(JSONB, nullable=False, default=dict)

    # ==========================================================================
    # Bi-directional Sync Fields
    # ==========================================================================
    # Data source: where did this record originate?
    source = Column(String, nullable=False, default="manual")  # "manual" | "xero" | "quickbooks"

    # Xero integration
    xero_contact_id = Column(String, nullable=True, unique=True, index=True)  # Xero Contact UUID
    xero_repeating_invoice_id = Column(String, nullable=True)  # For retainer billing

    # QuickBooks integration (future)
    quickbooks_customer_id = Column(String, nullable=True, unique=True, index=True)

    # Sync state
    sync_status = Column(String, nullable=True)  # "synced" | "pending_push" | "pending_pull" | "conflict" | "error"
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    sync_error = Column(Text, nullable=True)

    # Field-level locking: which fields are controlled by the external system?
    # If source="xero", these fields are read-only in Tamio UI
    locked_fields = Column(JSONB, nullable=False, default=list)  # e.g., ["name", "currency"]

    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="clients")
    cash_events = relationship("CashEvent", back_populates="client", cascade="all, delete-orphan")

    # One-to-Many: Client -> ObligationAgreement
    # Each client can have multiple obligations (retainer, project milestones, usage fees, etc.)
    obligations = relationship(
        "ObligationAgreement",
        back_populates="client",
        cascade="all, delete-orphan",
        foreign_keys="[ObligationAgreement.client_id]"
    )
