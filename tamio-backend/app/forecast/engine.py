"""Forecast calculation engine."""
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.data.models import CashAccount, CashEvent


async def calculate_13_week_forecast(db: AsyncSession, user_id: str) -> Dict[str, Any]:
    """
    Calculate a 13-week cash flow forecast for a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        Dictionary containing forecast data
    """
    # Get starting cash (sum of all cash account balances)
    result = await db.execute(
        select(func.sum(CashAccount.balance))
        .where(CashAccount.user_id == user_id)
    )
    starting_cash = result.scalar() or Decimal("0")

    # Get forecast start date (today)
    forecast_start = date.today()

    # Get all future cash events
    result = await db.execute(
        select(CashEvent)
        .where(
            CashEvent.user_id == user_id,
            CashEvent.date >= forecast_start
        )
        .order_by(CashEvent.date)
    )
    events = result.scalars().all()

    # Build 13-week forecast
    weeks = []
    current_balance = starting_cash

    for week_num in range(1, 14):
        week_start = forecast_start + timedelta(days=(week_num - 1) * 7)
        week_end = week_start + timedelta(days=6)

        # Filter events for this week
        week_events = [
            e for e in events
            if week_start <= e.date <= week_end
        ]

        # Calculate cash in/out
        cash_in = sum(
            e.amount for e in week_events if e.direction == "in"
        )
        cash_out = sum(
            e.amount for e in week_events if e.direction == "out"
        )

        net_change = cash_in - cash_out
        ending_balance = current_balance + net_change

        weeks.append({
            "week_number": week_num,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "starting_balance": str(current_balance),
            "cash_in": str(cash_in),
            "cash_out": str(cash_out),
            "net_change": str(net_change),
            "ending_balance": str(ending_balance),
            "events": [
                {
                    "id": e.id,
                    "date": e.date.isoformat(),
                    "amount": str(e.amount),
                    "direction": e.direction,
                    "event_type": e.event_type,
                    "category": e.category,
                    "confidence": e.confidence,
                }
                for e in sorted(week_events, key=lambda x: x.amount, reverse=True)[:10]
            ]
        })

        current_balance = ending_balance

    # Calculate summary statistics
    balances = [Decimal(w["ending_balance"]) for w in weeks]
    lowest_balance = min(balances)
    lowest_week = balances.index(lowest_balance) + 1

    total_cash_in = sum(Decimal(w["cash_in"]) for w in weeks)
    total_cash_out = sum(Decimal(w["cash_out"]) for w in weeks)

    # Calculate runway (weeks until cash hits 0)
    runway_weeks = 13
    for i, balance in enumerate(balances):
        if balance <= 0:
            runway_weeks = i + 1
            break

    return {
        "starting_cash": str(starting_cash),
        "forecast_start_date": forecast_start.isoformat(),
        "weeks": weeks,
        "summary": {
            "lowest_cash_week": lowest_week,
            "lowest_cash_amount": str(lowest_balance),
            "total_cash_in": str(total_cash_in),
            "total_cash_out": str(total_cash_out),
            "runway_weeks": runway_weeks,
        }
    }
