"""Forecast response schemas."""
from pydantic import BaseModel
from typing import List
from decimal import Decimal


class ForecastEventSummary(BaseModel):
    """Summary of a cash event in the forecast."""
    id: str
    date: str
    amount: str
    direction: str
    event_type: str
    category: str | None
    confidence: str


class WeekForecast(BaseModel):
    """Forecast for a single week."""
    week_number: int
    week_start: str
    week_end: str
    starting_balance: str
    cash_in: str
    cash_out: str
    net_change: str
    ending_balance: str
    events: List[ForecastEventSummary]


class ForecastSummary(BaseModel):
    """Summary statistics for the forecast."""
    lowest_cash_week: int
    lowest_cash_amount: str
    total_cash_in: str
    total_cash_out: str
    runway_weeks: int


class ForecastResponse(BaseModel):
    """Complete 13-week forecast response."""
    starting_cash: str
    forecast_start_date: str
    weeks: List[WeekForecast]
    summary: ForecastSummary
