"""Cash Event API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import date

from app.database import get_db
from app.data import models
from app.data.event_generator import generate_events_from_client, generate_events_from_bucket

router = APIRouter()


@router.post("/regenerate-events")
async def regenerate_all_events(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """Regenerate all cash events for a user's clients and expenses."""
    from app.scenarios.models import ScenarioEvent

    # Verify user exists
    result = await db.execute(
        select(models.User).where(models.User.id == user_id)
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="User not found")

    # Get IDs of events we're about to delete
    result = await db.execute(
        select(models.CashEvent.id).where(
            models.CashEvent.user_id == user_id,
            models.CashEvent.date >= date.today()
        )
    )
    event_ids_to_delete = [row[0] for row in result.fetchall()]

    # Clear references in scenario_events first (set original_event_id to NULL)
    if event_ids_to_delete:
        await db.execute(
            ScenarioEvent.__table__.update()
            .where(ScenarioEvent.original_event_id.in_(event_ids_to_delete))
            .values(original_event_id=None)
        )

    # Delete all future events
    await db.execute(
        delete(models.CashEvent).where(
            models.CashEvent.user_id == user_id,
            models.CashEvent.date >= date.today()
        )
    )
    await db.commit()

    # Get all active clients
    result = await db.execute(
        select(models.Client).where(
            models.Client.user_id == user_id,
            models.Client.status != "deleted"
        )
    )
    clients = result.scalars().all()

    # Get all expense buckets
    result = await db.execute(
        select(models.ExpenseBucket).where(
            models.ExpenseBucket.user_id == user_id
        )
    )
    buckets = result.scalars().all()

    # Regenerate events
    total_events = 0

    for client in clients:
        events = await generate_events_from_client(db, client)
        total_events += len(events)

    for bucket in buckets:
        events = await generate_events_from_bucket(db, bucket)
        total_events += len(events)

    return {
        "message": "Events regenerated successfully",
        "total_events": total_events,
        "clients_processed": len(clients),
        "expenses_processed": len(buckets)
    }
