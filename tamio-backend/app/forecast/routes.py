"""Forecast API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.forecast.engine_v2 import calculate_forecast_v2
from app.forecast.schemas import ForecastResponse

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
