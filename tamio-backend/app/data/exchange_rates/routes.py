"""Exchange rate routes."""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.database import get_db
from app.services.exchange_rates import get_rate, get_latest_rates, SUPPORTED_CURRENCIES

router = APIRouter()


class ExchangeRateResponse(BaseModel):
    """Response for exchange rate query."""
    from_currency: str
    to_currency: str
    rate: str
    effective_date: str


class LatestRatesResponse(BaseModel):
    """Response for latest rates query."""
    base_currency: str
    rates: dict[str, dict]


@router.get("/latest", response_model=LatestRatesResponse)
async def get_latest_exchange_rates(
    base_currency: str = Query(default="USD", description="Base currency"),
    db: AsyncSession = Depends(get_db)
):
    """Get latest exchange rates for all currencies relative to base currency."""
    if base_currency not in SUPPORTED_CURRENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported currency: {base_currency}. Supported: {', '.join(SUPPORTED_CURRENCIES)}"
        )

    rates = await get_latest_rates(db, base_currency)
    return LatestRatesResponse(
        base_currency=base_currency,
        rates=rates
    )


@router.get("/rate", response_model=ExchangeRateResponse)
async def get_exchange_rate(
    from_currency: str = Query(..., description="Source currency"),
    to_currency: str = Query(..., description="Target currency"),
    target_date: date | None = Query(default=None, description="Date for rate (defaults to today)"),
    db: AsyncSession = Depends(get_db)
):
    """Get exchange rate between two currencies."""
    if from_currency not in SUPPORTED_CURRENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported source currency: {from_currency}"
        )

    if to_currency not in SUPPORTED_CURRENCIES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target currency: {to_currency}"
        )

    rate = await get_rate(db, from_currency, to_currency, target_date)

    if rate is None:
        raise HTTPException(
            status_code=404,
            detail=f"No exchange rate found for {from_currency} to {to_currency}"
        )

    return ExchangeRateResponse(
        from_currency=from_currency,
        to_currency=to_currency,
        rate=str(rate.rate),
        effective_date=rate.effective_date.isoformat()
    )
