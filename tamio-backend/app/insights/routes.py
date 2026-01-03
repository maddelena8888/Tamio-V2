"""Insights API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.insights.engine import calculate_insights
from app.insights.schemas import InsightsResponse

router = APIRouter()


@router.get("", response_model=InsightsResponse)
async def get_insights(
    user_id: str = Query(..., description="User ID"),
    buffer_months: int = Query(3, description="Target buffer months", ge=1, le=12),
    db: AsyncSession = Depends(get_db)
):
    """
    Get comprehensive behavioural insights for a user.

    This endpoint analyzes:
    - Income Behaviour: Client payment patterns, revenue concentration
    - Expense Behaviour: Budget compliance, expense trends by category
    - Cash Discipline: Buffer health, upcoming risk windows

    All insights are computed on-the-fly from the current data state.

    Args:
        user_id: User ID
        buffer_months: Target cash buffer in months (default 3)
        db: Database session

    Returns:
        Complete insights with health scores and recommendations
    """
    try:
        insights = await calculate_insights(db, user_id, buffer_months)
        return insights
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating insights: {str(e)}"
        )


@router.get("/income")
async def get_income_insights(
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get income behaviour insights only.

    Analyzes client payment patterns and revenue concentration.
    """
    try:
        insights = await calculate_insights(db, user_id)
        return insights.income_behaviour
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating income insights: {str(e)}"
        )


@router.get("/expenses")
async def get_expense_insights(
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get expense behaviour insights only.

    Analyzes budget compliance and expense trends.
    """
    try:
        insights = await calculate_insights(db, user_id)
        return insights.expense_behaviour
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating expense insights: {str(e)}"
        )


@router.get("/cash-discipline")
async def get_cash_discipline_insights(
    user_id: str = Query(..., description="User ID"),
    buffer_months: int = Query(3, description="Target buffer months", ge=1, le=12),
    db: AsyncSession = Depends(get_db)
):
    """
    Get cash discipline insights only.

    Analyzes buffer health and upcoming risk windows.
    """
    try:
        insights = await calculate_insights(db, user_id, buffer_months)
        return insights.cash_discipline
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating cash discipline insights: {str(e)}"
        )


@router.get("/summary")
async def get_insights_summary(
    user_id: str = Query(..., description="User ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get insights summary with health scores only.

    Returns overall health scores and top alerts/recommendations
    without the detailed breakdowns.
    """
    try:
        insights = await calculate_insights(db, user_id)
        return insights.summary
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating insights summary: {str(e)}"
        )
