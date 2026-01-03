"""Cash Account model for tracking cash balances."""
from sqlalchemy import Column, String, DateTime, Date, Numeric, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base
from app.data.base import generate_id


class CashAccount(Base):
    """Cash Account model - Page 1: Current Cash Position."""

    __tablename__ = "cash_accounts"

    id = Column(String, primary_key=True, default=lambda: generate_id("acct"))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    account_name = Column(String, nullable=False)
    balance = Column(Numeric(precision=15, scale=2), nullable=False)
    currency = Column(String, nullable=False, default="USD")
    as_of_date = Column(Date, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="cash_accounts")
    payment_events = relationship("PaymentEvent", back_populates="account", cascade="all, delete-orphan")
