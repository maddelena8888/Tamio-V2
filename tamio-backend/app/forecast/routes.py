"""Forecast API routes."""
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.database import get_db
from app.forecast.engine_v2 import calculate_forecast_v2
from app.forecast.schemas import (
    ForecastResponse,
    ScenarioBarResponse,
    ScenarioBarMetrics,
    MetricValue,
    TransactionsResponse,
    TransactionItem,
)
from app.data.clients.models import Client
from app.data.expenses.models import ExpenseBucket

router = APIRouter()


@router.get("", response_model=ForecastResponse)
async def get_forecast(
    user_id: str = Query(..., description="User ID"),
    weeks: int = Query(13, description="Number of weeks to forecast", ge=1, le=52),
    db: AsyncSession = Depends(get_db)
):
    """
    Get cash flow forecast for a user.

    This endpoint computes the forecast on-the-fly from clients and expenses,
    ensuring it's always aligned with current data. It also includes confidence
    scoring based on integration status:

    - HIGH confidence: Linked to accounting software with recurring invoice/bill
    - MEDIUM confidence: Synced as contact but no invoice/bill
    - LOW confidence: Manual entry, not linked to accounting software

    Args:
        user_id: User ID
        weeks: Number of weeks to forecast (default 13, max 52)
        db: Database session

    Returns:
        Forecast with weekly breakdowns, summary, and confidence metrics
    """
    try:
        forecast = await calculate_forecast_v2(db, user_id, weeks=weeks)
        return forecast
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating forecast: {str(e)}")


@router.get("/confidence")
async def get_forecast_confidence(
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get detailed confidence breakdown for a user's forecast.

    Returns the confidence metrics without the full forecast data,
    useful for displaying confidence indicators in the UI.

    Args:
        user_id: User ID
        db: Database session

    Returns:
        Confidence breakdown with suggestions for improvement
    """
    try:
        forecast = await calculate_forecast_v2(db, user_id, weeks=13)
        return {
            "confidence": forecast["confidence"],
            "summary": {
                "total_clients": forecast["confidence"]["breakdown"]["high_confidence_count"] +
                                 forecast["confidence"]["breakdown"]["medium_confidence_count"] +
                                 forecast["confidence"]["breakdown"]["low_confidence_count"],
                "total_cash_in": forecast["summary"]["total_cash_in"],
                "total_cash_out": forecast["summary"]["total_cash_out"],
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating confidence: {str(e)}")


@router.get("/scenario-bar", response_model=ScenarioBarResponse)
async def get_scenario_bar_metrics(
    user_id: str = Query(..., description="User ID"),
    scenario_id: Optional[str] = Query(None, description="Optional scenario ID for scenario metrics"),
    time_range: str = Query("13w", description="Time range: 13w, 26w, or 52w"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get metrics for the scenario bar (runway, payroll safety, VAT reserve).

    Returns key metrics that help users understand their cash flow health at a glance.
    When a scenario_id is provided, returns metrics for that scenario instead of baseline.

    Args:
        user_id: User ID
        scenario_id: Optional scenario ID to get scenario-specific metrics
        time_range: Time range for forecast (13w, 26w, 52w)
        db: Database session

    Returns:
        ScenarioBarResponse with metrics and scenario status
    """
    try:
        # Parse weeks from time_range
        weeks_map = {"13w": 13, "26w": 26, "52w": 52}
        weeks = weeks_map.get(time_range, 13)

        # Get forecast data
        forecast = await calculate_forecast_v2(db, user_id, weeks=weeks)

        # Default buffer calculation (3 months)
        target_months = 3

        # Calculate metrics from forecast
        runway_weeks = forecast["summary"]["runway_weeks"]
        total_cash_out = Decimal(forecast["summary"]["total_cash_out"])
        monthly_burn = total_cash_out / 3 if weeks >= 12 else total_cash_out

        # Runway status
        if runway_weeks >= 12:
            runway_status = "good"
            runway_icon = "circle-check"
        elif runway_weeks >= 6:
            runway_status = "warning"
            runway_icon = "alert-triangle"
        else:
            runway_status = "critical"
            runway_icon = "circle-x"

        # Find next payroll in expense buckets
        expenses_result = await db.execute(
            select(ExpenseBucket)
            .where(ExpenseBucket.user_id == user_id)
            .where(ExpenseBucket.category == "payroll")
        )
        payroll_expenses = expenses_result.scalars().all()

        # Check if next payroll is safe (within first 2 weeks of forecast)
        payroll_amount = sum(Decimal(exp.monthly_amount or "0") for exp in payroll_expenses) / 2  # bi-weekly
        starting_cash = Decimal(forecast["starting_cash"])
        week_1_balance = Decimal(forecast["weeks"][0]["ending_balance"]) if forecast["weeks"] else starting_cash
        week_2_balance = Decimal(forecast["weeks"][1]["ending_balance"]) if len(forecast["weeks"]) > 1 else week_1_balance

        # Payroll safety: check if we can cover payroll in the next 2 weeks
        min_balance = min(week_1_balance, week_2_balance)
        if min_balance >= payroll_amount * 1.5:
            payroll_status = "good"
            payroll_value = "Safe"
            payroll_icon = "check"
        elif min_balance >= payroll_amount:
            payroll_status = "warning"
            payroll_value = "At Risk"
            payroll_icon = "alert-triangle"
        else:
            payroll_status = "critical"
            payroll_value = "Critical"
            payroll_icon = "circle-x"

        # Calculate VAT/Tax reserve from expense buckets
        tax_expenses_result = await db.execute(
            select(ExpenseBucket)
            .where(ExpenseBucket.user_id == user_id)
            .where(
                ExpenseBucket.name.ilike("%vat%") |
                ExpenseBucket.name.ilike("%tax%") |
                ExpenseBucket.name.ilike("%gst%")
            )
        )
        tax_expenses = tax_expenses_result.scalars().all()
        vat_reserve_total = sum(Decimal(exp.monthly_amount or "0") for exp in tax_expenses) * 3  # 3 months reserve

        # VAT reserve status
        if vat_reserve_total > 0:
            # Check if we have enough buffer for VAT
            lowest_balance = Decimal(forecast["summary"]["lowest_cash_amount"])
            if lowest_balance >= vat_reserve_total * 1.2:
                vat_status = "good"
                vat_icon = "check"
            elif lowest_balance >= vat_reserve_total:
                vat_status = "warning"
                vat_icon = "alert-triangle"
            else:
                vat_status = "critical"
                vat_icon = "triangle"
        else:
            # No VAT expenses tracked, neutral status
            vat_status = "good"
            vat_icon = "check"

        # Format VAT reserve amount
        vat_formatted = f"${int(vat_reserve_total / 1000)}k" if vat_reserve_total >= 1000 else f"${int(vat_reserve_total)}"

        # Build response
        return ScenarioBarResponse(
            scenario_active=scenario_id is not None,
            scenario_name=None,  # TODO: Fetch scenario name if scenario_id provided
            impact_statement=None,  # TODO: Calculate impact if scenario active
            metrics=ScenarioBarMetrics(
                runway=MetricValue(
                    value=f"{runway_weeks}",
                    raw_value=float(runway_weeks),
                    unit="w",
                    status=runway_status,
                    icon=runway_icon
                ),
                next_payroll=MetricValue(
                    value=payroll_value,
                    raw_value=float(min_balance),
                    unit=None,
                    status=payroll_status,
                    icon=payroll_icon
                ),
                vat_reserve=MetricValue(
                    value=vat_formatted,
                    raw_value=float(vat_reserve_total),
                    unit="$",
                    status=vat_status,
                    icon=vat_icon
                )
            ),
            time_range=time_range
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating scenario bar metrics: {str(e)}")


@router.get("/transactions", response_model=TransactionsResponse)
async def get_forecast_transactions(
    user_id: str = Query(..., description="User ID"),
    type: str = Query(..., description="Transaction type: 'inflows' or 'outflows'"),
    time_range: str = Query("13w", description="Time range: 13w, 26w, or 52w"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get forecast transactions (inflows or outflows) for display in tables.

    Returns transaction items that can be toggled on/off to create custom scenarios.

    Args:
        user_id: User ID
        type: "inflows" or "outflows"
        time_range: Time range for forecast (13w, 26w, 52w)
        db: Database session

    Returns:
        TransactionsResponse with list of transactions
    """
    try:
        # Parse weeks from time_range
        weeks_map = {"13w": 13, "26w": 26, "52w": 52}
        weeks = weeks_map.get(time_range, 13)

        # Get forecast with events
        forecast = await calculate_forecast_v2(db, user_id, weeks=weeks)

        # Collect all events from all weeks
        transactions: List[TransactionItem] = []
        today = date.today()

        for week in forecast["weeks"]:
            for event in week.get("events", []):
                # Filter by direction
                if type == "inflows" and event["direction"] != "in":
                    continue
                if type == "outflows" and event["direction"] != "out":
                    continue

                # Determine status based on date
                event_date = date.fromisoformat(event["date"])
                if event_date < today:
                    status = "overdue" if type == "inflows" else "paid"
                elif event_date <= today + timedelta(days=7):
                    status = "due"
                else:
                    status = "expected"

                transactions.append(TransactionItem(
                    id=event["id"],
                    date=event["date"],
                    amount=float(event["amount"]),
                    name=event.get("source_name", "Unknown"),
                    entity_id=event.get("source_id", ""),
                    entity_type=event.get("source_type", "client" if type == "inflows" else "expense"),
                    status=status,
                    included=True  # All transactions included by default
                ))

        # Sort by date
        transactions.sort(key=lambda t: t.date)

        # Calculate total amount
        total_amount = sum(t.amount for t in transactions)

        return TransactionsResponse(
            transactions=transactions,
            total_amount=total_amount,
            time_range=time_range
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching transactions: {str(e)}")
