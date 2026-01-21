"""Exchange rate service for fetching and converting currencies."""
import httpx
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.data.exchange_rates.models import ExchangeRate


# ECB provides rates relative to EUR
ECB_RATES_URL = "https://data.ecb.europa.eu/data-api/v1/data/EXR/D..EUR.SP00.A?format=csvdata&startPeriod={start_date}&endPeriod={end_date}"

# Supported currencies
SUPPORTED_CURRENCIES = ['USD', 'EUR', 'GBP', 'AED', 'AUD', 'CAD', 'CHF', 'SGD', 'JPY', 'NZD']


async def fetch_rates_from_ecb(target_date: Optional[date] = None) -> dict[str, Decimal]:
    """
    Fetch exchange rates from ECB API.
    Returns rates relative to EUR (base currency for ECB).

    Returns:
        Dict mapping currency codes to their EUR exchange rate
        e.g., {'USD': 1.08, 'GBP': 0.86, ...}
    """
    if target_date is None:
        target_date = date.today()

    # ECB API format
    date_str = target_date.isoformat()

    # Use a simpler ECB endpoint that returns JSON
    url = f"https://data-api.ecb.europa.eu/service/data/EXR/D.{'+'.join(c for c in SUPPORTED_CURRENCIES if c != 'EUR')}.EUR.SP00.A"

    rates = {}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                params={
                    'format': 'jsondata',
                    'startPeriod': date_str,
                    'endPeriod': date_str,
                },
                headers={'Accept': 'application/json'}
            )

            if response.status_code == 200:
                data = response.json()

                # Parse ECB JSON response structure
                if 'dataSets' in data and data['dataSets']:
                    dataset = data['dataSets'][0]
                    series = dataset.get('series', {})
                    structure = data.get('structure', {})
                    dimensions = structure.get('dimensions', {}).get('series', [])

                    # Find currency dimension
                    currency_dim = None
                    for dim in dimensions:
                        if dim.get('id') == 'CURRENCY':
                            currency_dim = dim
                            break

                    if currency_dim and 'values' in currency_dim:
                        currencies = [v['id'] for v in currency_dim['values']]

                        for key, series_data in series.items():
                            # Key format is like "0:0:0:0:0" - first index is currency
                            parts = key.split(':')
                            if parts:
                                currency_idx = int(parts[0])
                                if currency_idx < len(currencies):
                                    currency = currencies[currency_idx]
                                    observations = series_data.get('observations', {})
                                    if observations:
                                        # Get latest observation
                                        latest_key = max(observations.keys())
                                        rate_value = observations[latest_key][0]
                                        if rate_value is not None:
                                            rates[currency] = Decimal(str(rate_value))

                # EUR to EUR is always 1
                rates['EUR'] = Decimal('1.0')

    except Exception as e:
        print(f"Error fetching rates from ECB: {e}")
        # Return fallback rates if ECB fails
        rates = get_fallback_rates()

    return rates


def get_fallback_rates() -> dict[str, Decimal]:
    """Return fallback exchange rates (approximate) if ECB API fails."""
    return {
        'EUR': Decimal('1.0'),
        'USD': Decimal('1.08'),
        'GBP': Decimal('0.86'),
        'AED': Decimal('3.97'),
        'AUD': Decimal('1.65'),
        'CAD': Decimal('1.47'),
        'CHF': Decimal('0.94'),
        'SGD': Decimal('1.45'),
        'JPY': Decimal('160.50'),
        'NZD': Decimal('1.78'),
    }


async def store_exchange_rates(
    db: AsyncSession,
    rates: dict[str, Decimal],
    effective_date: date,
    source: str = "ecb"
) -> list[ExchangeRate]:
    """
    Store exchange rates in the database.
    Creates rate pairs for all supported currencies.
    """
    stored_rates = []

    for from_currency in SUPPORTED_CURRENCIES:
        for to_currency in SUPPORTED_CURRENCIES:
            if from_currency == to_currency:
                continue

            # Calculate cross rate via EUR
            from_rate = rates.get(from_currency, Decimal('1.0'))
            to_rate = rates.get(to_currency, Decimal('1.0'))

            # Rate from A to B: if we have EUR/A and EUR/B, then A/B = (EUR/B) / (EUR/A)
            if from_rate > 0:
                cross_rate = to_rate / from_rate
            else:
                continue

            # Check if rate already exists
            existing = await db.execute(
                select(ExchangeRate).where(
                    ExchangeRate.from_currency == from_currency,
                    ExchangeRate.to_currency == to_currency,
                    ExchangeRate.effective_date == effective_date
                )
            )
            existing_rate = existing.scalar_one_or_none()

            if existing_rate:
                # Update existing rate
                existing_rate.rate = cross_rate
                existing_rate.source = source
                stored_rates.append(existing_rate)
            else:
                # Create new rate
                rate = ExchangeRate(
                    from_currency=from_currency,
                    to_currency=to_currency,
                    rate=cross_rate,
                    effective_date=effective_date,
                    source=source
                )
                db.add(rate)
                stored_rates.append(rate)

    await db.commit()
    return stored_rates


async def get_rate(
    db: AsyncSession,
    from_currency: str,
    to_currency: str,
    target_date: Optional[date] = None
) -> Optional[ExchangeRate]:
    """
    Get exchange rate from database.
    Uses the most recent rate on or before the target date.
    """
    if from_currency == to_currency:
        # Return a synthetic rate of 1.0
        return ExchangeRate(
            from_currency=from_currency,
            to_currency=to_currency,
            rate=Decimal('1.0'),
            effective_date=target_date or date.today(),
            source='system'
        )

    if target_date is None:
        target_date = date.today()

    result = await db.execute(
        select(ExchangeRate)
        .where(
            ExchangeRate.from_currency == from_currency,
            ExchangeRate.to_currency == to_currency,
            ExchangeRate.effective_date <= target_date
        )
        .order_by(desc(ExchangeRate.effective_date))
        .limit(1)
    )

    return result.scalar_one_or_none()


async def convert_amount(
    db: AsyncSession,
    amount: Decimal,
    from_currency: str,
    to_currency: str,
    target_date: Optional[date] = None
) -> tuple[Decimal, Decimal, date]:
    """
    Convert an amount from one currency to another.

    Returns:
        Tuple of (converted_amount, exchange_rate, effective_date)
    """
    if from_currency == to_currency:
        return amount, Decimal('1.0'), target_date or date.today()

    rate = await get_rate(db, from_currency, to_currency, target_date)

    if rate is None:
        # Try to fetch and store rates
        rates = await fetch_rates_from_ecb(target_date)
        if rates:
            await store_exchange_rates(db, rates, target_date or date.today())
            rate = await get_rate(db, from_currency, to_currency, target_date)

    if rate is None:
        raise ValueError(f"No exchange rate found for {from_currency} to {to_currency}")

    converted = amount * rate.rate
    return converted, rate.rate, rate.effective_date


async def get_latest_rates(
    db: AsyncSession,
    base_currency: str = 'USD'
) -> dict[str, dict]:
    """
    Get latest exchange rates for all currencies relative to base currency.

    Returns:
        Dict mapping currency codes to rate info
        e.g., {'EUR': {'rate': 0.92, 'effective_date': '2026-01-04'}, ...}
    """
    today = date.today()
    rates = {}

    for currency in SUPPORTED_CURRENCIES:
        if currency == base_currency:
            rates[currency] = {
                'rate': '1.0',
                'effective_date': today.isoformat()
            }
            continue

        rate = await get_rate(db, base_currency, currency, today)
        if rate:
            rates[currency] = {
                'rate': str(rate.rate),
                'effective_date': rate.effective_date.isoformat()
            }

    return rates


async def refresh_exchange_rates(db: AsyncSession) -> int:
    """
    Fetch and store latest exchange rates.
    Should be called periodically (e.g., daily or weekly).

    Returns:
        Number of rates stored
    """
    rates = await fetch_rates_from_ecb()
    if rates:
        stored = await store_exchange_rates(db, rates, date.today())
        return len(stored)
    return 0
