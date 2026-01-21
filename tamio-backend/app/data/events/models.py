"""Cash Event model for tracking generated cash flow events."""
from sqlalchemy import Column, String, DateTime, Date, Numeric, Boolean, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.data.base import generate_id


class CashEvent(Base):
    """Cash Event model - Generated from Clients & Buckets."""

    __tablename__ = "cash_events"

    id = Column(String, primary_key=True, default=lambda: generate_id("evt"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Core Fields
    date = Column(Date, nullable=False, index=True)
    week_number = Column(Integer, nullable=False, default=0)
    amount = Column(Numeric(precision=15, scale=2), nullable=False)
    direction = Column(String, nullable=False)  # "in" | "out"

    # Classification
    event_type = Column(String, nullable=False)  # "expected_revenue" | "expected_expense"
    category = Column(String, nullable=True)

    # Relationships
    client_id = Column(String, ForeignKey("clients.id", ondelete="CASCADE"), nullable=True, index=True)
    bucket_id = Column(String, ForeignKey("expense_buckets.id", ondelete="CASCADE"), nullable=True, index=True)

    # Link to canonical obligation system (new architecture)
    # This enables traceability from CashEvents back to the ObligationSchedule that generated them
    obligation_schedule_id = Column(
        String,
        ForeignKey("obligation_schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Confidence
    confidence = Column(String, nullable=False, default="high")  # "high" | "medium" | "low"
    confidence_reason = Column(String, nullable=True)

    # Recurrence
    is_recurring = Column(Boolean, nullable=False, default=False)
    recurrence_pattern = Column(String, nullable=True)  # "weekly" | "monthly" | "quarterly"

    # Metadata
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="cash_events")
    client = relationship("Client", back_populates="cash_events")
    expense_bucket = relationship("ExpenseBucket", back_populates="cash_events")
    obligation_schedule = relationship("ObligationSchedule", back_populates="cash_events")

    # Indexes
    __table_args__ = (
        Index("ix_cash_events_user_date", "user_id", "date"),
        Index("ix_cash_events_client_id", "client_id"),
        Index("ix_cash_events_bucket_id", "bucket_id"),
    )
