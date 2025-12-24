"""Forecast API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.forecast.engine import calculate_13_week_forecast
from app.forecast.schemas import ForecastResponse

router = APIRouter()


@router.get("", response_model=ForecastResponse)
async def get_forecast(
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get 13-week cash flow forecast for a user.

    Args:
        user_id: User ID
        db: Database session

    Returns:
        13-week forecast with weekly breakdowns and summary
    """
    try:
        forecast = await calculate_13_week_forecast(db, user_id)
        return forecast
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating forecast: {str(e)}")
