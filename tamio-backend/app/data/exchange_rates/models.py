"""Exchange rate model."""
from sqlalchemy import Column, String, Date, DateTime, Numeric, UniqueConstraint, Index
from sqlalchemy.sql import func

from app.database import Base
from app.data.base import generate_id


class ExchangeRate(Base):
    """Exchange rate model - stores currency conversion rates."""

    __tablename__ = "exchange_rates"

    id = Column(String, primary_key=True, default=lambda: generate_id("xrate"))
    from_currency = Column(String, nullable=False, index=True)
    to_currency = Column(String, nullable=False, index=True)
    rate = Column(Numeric(precision=18, scale=8), nullable=False)
    effective_date = Column(Date, nullable=False, index=True)
    source = Column(String, nullable=False, default="ecb")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint('from_currency', 'to_currency', 'effective_date', name='uq_exchange_rate_currency_date'),
    )
