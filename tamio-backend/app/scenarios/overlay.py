"""
Scenario Overlay Service - Computes forecast with virtual schedule overlays.

Key principle: NEVER modify canonical data. All changes are virtual overlays
that are applied on-the-fly during forecast computation.

Architecture:
1. Get base ObligationSchedules from canonical data
2. Apply ScenarioDelta as immutable overlay
3. Convert overlaid schedules to ForecastEvents
4. Return combined events for forecast computation
"""

from typing import List, Dict, Any, Tuple, Optional
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from dataclasses import dataclass
from enum import Enum

from app.data.obligations.models import ObligationAgreement, ObligationSchedule
from app.scenarios.pipeline.types import ScenarioDelta, ScheduleDelta


class ConfidenceLevel(str, Enum):
    """Confidence levels for forecast events."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class OverlayForecastEvent:
    """
    A forecast event derived from schedule overlay.

    Similar to ForecastEvent but includes overlay attribution.
    """
    id: str
    date: date
    amount: Decimal
    direction: str  # "in" or "out"
    event_type: str  # "expected_revenue", "expected_expense", "scenario_projection"
    category: str
    confidence: ConfidenceLevel
    confidence_reason: str
    source_id: str
    source_name: str
    source_type: str  # "obligation", "scenario", "client", "expense"
    is_recurring: bool
    recurrence_pattern: Optional[str] = None

    # Overlay attribution
    is_virtual: bool = False
    scenario_id: Optional[str] = None
    original_schedule_id: Optional[str] = None


class ScenarioOverlayService:
    """
    Service for applying scenario overlays to forecasts.

    This service computes forecast events by:
    1. Reading base ObligationSchedules from canonical data
    2. Applying ScenarioDelta overlays (immutable operation)
    3. Converting to ForecastEvents for weekly aggregation
    """

    def __init__(self, db: AsyncSession, user_id: str):
        self.db = db
        self.user_id = user_id

    async def compute_overlay_forecast(
        self,
        delta: ScenarioDelta,
        start_date: date,
        end_date: date,
    ) -> Tuple[List[OverlayForecastEvent], Dict[str, Any]]:
        """
        Compute forecast events with scenario overlay applied.

        Args:
            delta: The ScenarioDelta containing virtual schedule changes
            start_date: Start of forecast window
            end_date: End of forecast window

        Returns:
            Tuple of (overlaid_events, overlay_summary)
        """
        # Step 1: Get base schedules from canonical data
        base_schedules = await self._get_base_schedules(start_date, end_date)

        # Step 2: Apply delta as overlay (immutable)
        overlaid_schedule_dicts = self._apply_overlay(base_schedules, delta)

        # Step 3: Convert base schedules to events
        base_events = await self._schedules_to_events(overlaid_schedule_dicts)

        # Step 4: Add virtual schedules from delta (new ones)
        virtual_events = self._virtual_schedules_to_events(delta, start_date, end_date)
        all_events = base_events + virtual_events

        # Sort by date
        all_events.sort(key=lambda e: e.date)

        # Build summary
        summary = self._build_overlay_summary(delta, all_events)

        return all_events, summary

    async def _get_base_schedules(
        self,
        start_date: date,
        end_date: date,
    ) -> List[ObligationSchedule]:
        """Get all canonical ObligationSchedules in date range."""
        query = (
            select(ObligationSchedule)
            .join(ObligationAgreement)
            .options(selectinload(ObligationSchedule.obligation))  # Eagerly load obligation
            .where(
                and_(
                    ObligationAgreement.user_id == self.user_id,
                    ObligationSchedule.due_date >= start_date,
                    ObligationSchedule.due_date <= end_date,
                    ObligationSchedule.status.in_(["scheduled", "due"])
                )
            )
            .order_by(ObligationSchedule.due_date)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    def _apply_overlay(
        self,
        base_schedules: List[ObligationSchedule],
        delta: ScenarioDelta,
    ) -> List[Dict[str, Any]]:
        """
        Apply delta overlay to base schedules (immutable operation).

        Returns list of schedule dictionaries with overlay applied.
        Does NOT modify the original base_schedules.
        """
        # Convert to dicts for manipulation (creates copies)
        schedules_dict = {
            s.id: self._schedule_to_dict(s)
            for s in base_schedules
        }

        # Track deleted IDs
        deleted_ids = set(delta.deleted_schedule_ids)

        # Apply modifications
        for update in delta.updated_schedules:
            if update.operation == "modify" and update.original_schedule_id:
                if update.original_schedule_id in schedules_dict:
                    # Merge update data into schedule dict
                    updated_data = schedules_dict[update.original_schedule_id].copy()
                    if update.schedule_data:
                        updated_data.update(update.schedule_data)
                    updated_data["_scenario_modified"] = True
                    updated_data["_scenario_id"] = update.scenario_id
                    updated_data["_change_reason"] = update.change_reason
                    schedules_dict[update.original_schedule_id] = updated_data

            elif update.operation == "defer" and update.original_schedule_id:
                # Defer = move due_date forward
                if update.original_schedule_id in schedules_dict:
                    updated_data = schedules_dict[update.original_schedule_id].copy()
                    new_data = update.schedule_data or {}
                    if "due_date" in new_data:
                        updated_data["due_date"] = new_data["due_date"]
                    updated_data["_scenario_deferred"] = True
                    updated_data["_scenario_id"] = update.scenario_id
                    updated_data["confidence"] = update.confidence  # Usually lowered
                    schedules_dict[update.original_schedule_id] = updated_data

            elif update.operation == "delete" and update.original_schedule_id:
                # Mark for deletion (already in deleted_schedule_ids, but track reason)
                if update.original_schedule_id in schedules_dict:
                    schedules_dict[update.original_schedule_id]["_deleted"] = True
                    schedules_dict[update.original_schedule_id]["_scenario_id"] = update.scenario_id

        # Remove deleted schedules from result
        result = [
            sched for sched_id, sched in schedules_dict.items()
            if sched_id not in deleted_ids and not sched.get("_deleted")
        ]

        return result

    def _virtual_schedules_to_events(
        self,
        delta: ScenarioDelta,
        start_date: date,
        end_date: date,
    ) -> List[OverlayForecastEvent]:
        """Convert virtual (new) schedules from delta to OverlayForecastEvents."""
        events = []

        for created in delta.created_schedules:
            data = created.schedule_data or {}

            # Parse due date
            due_date = data.get("due_date")
            if isinstance(due_date, str):
                due_date = date.fromisoformat(due_date)
            elif due_date is None:
                continue  # Skip if no date

            # Filter to forecast window
            if due_date < start_date or due_date > end_date:
                continue

            # Determine direction from category/type
            category = data.get("category", "other")
            direction = self._infer_direction(category, data)

            # Map confidence
            conf_str = created.confidence or data.get("confidence", "medium")
            confidence = ConfidenceLevel(conf_str) if conf_str in ["high", "medium", "low"] else ConfidenceLevel.MEDIUM

            # Parse amount
            amount_str = data.get("estimated_amount", "0")
            amount = Decimal(str(amount_str)) if amount_str else Decimal("0")

            events.append(OverlayForecastEvent(
                id=f"scenario_{created.schedule_id}",
                date=due_date,
                amount=amount,
                direction=direction,
                event_type="scenario_projection",
                category=category,
                confidence=confidence,
                confidence_reason=f"Scenario: {created.change_reason}",
                source_id=created.obligation_id or created.scenario_id,
                source_name=data.get("source_name", data.get("vendor_name", "Scenario")),
                source_type="scenario",
                is_recurring=data.get("is_recurring", False),
                recurrence_pattern=data.get("recurrence_pattern"),
                is_virtual=True,
                scenario_id=created.scenario_id,
                original_schedule_id=None,
            ))

        return events

    async def _schedules_to_events(
        self,
        schedule_dicts: List[Dict[str, Any]],
    ) -> List[OverlayForecastEvent]:
        """Convert schedule dictionaries to OverlayForecastEvents."""
        events = []

        for sched in schedule_dicts:
            # Parse due date
            due_date = sched.get("due_date")
            if isinstance(due_date, str):
                due_date = date.fromisoformat(due_date)

            # Get obligation for direction/category info
            obligation = sched.get("_obligation")
            if obligation:
                direction = "in" if obligation.client_id else "out"
                category = obligation.category or sched.get("category", "other")
                source_name = obligation.vendor_name or "Unknown"
            else:
                category = sched.get("category", "other")
                direction = self._infer_direction(category, sched)
                source_name = sched.get("source_name", "Unknown")

            # Map confidence
            conf_str = sched.get("confidence", "medium")
            confidence = ConfidenceLevel(conf_str) if conf_str in ["high", "medium", "low"] else ConfidenceLevel.MEDIUM

            # Parse amount
            amount_str = sched.get("estimated_amount", "0")
            amount = Decimal(str(amount_str)) if amount_str else Decimal("0")

            # Determine event type
            if sched.get("_scenario_modified") or sched.get("_scenario_deferred"):
                event_type = "scenario_modified"
            else:
                event_type = "expected_revenue" if direction == "in" else "expected_expense"

            events.append(OverlayForecastEvent(
                id=f"sched_{sched['id']}",
                date=due_date,
                amount=amount,
                direction=direction,
                event_type=event_type,
                category=category,
                confidence=confidence,
                confidence_reason=sched.get("_change_reason", sched.get("estimate_source", "")),
                source_id=sched.get("obligation_id", sched["id"]),
                source_name=source_name,
                source_type="obligation",
                is_recurring=sched.get("is_recurring", False),
                recurrence_pattern=sched.get("recurrence_pattern"),
                is_virtual=sched.get("_scenario_modified", False) or sched.get("_scenario_deferred", False),
                scenario_id=sched.get("_scenario_id"),
                original_schedule_id=sched["id"] if sched.get("_scenario_modified") else None,
            ))

        return events

    def _schedule_to_dict(self, schedule: ObligationSchedule) -> Dict[str, Any]:
        """Convert ObligationSchedule ORM object to dictionary for overlay processing."""
        return {
            "id": schedule.id,
            "obligation_id": schedule.obligation_id,
            "due_date": schedule.due_date.isoformat() if schedule.due_date else None,
            "estimated_amount": str(schedule.estimated_amount) if schedule.estimated_amount else "0",
            "confidence": schedule.confidence or "medium",
            "status": schedule.status,
            "estimate_source": schedule.estimate_source,
            "notes": schedule.notes,
            "is_recurring": False,  # Would need to check obligation.frequency
            "_obligation": schedule.obligation,  # Keep reference for direction inference
        }

    def _infer_direction(self, category: str, data: Dict[str, Any]) -> str:
        """Infer cash direction from category and data."""
        # Revenue categories
        revenue_categories = {"revenue", "retainer", "project", "milestone", "invoice"}
        if category.lower() in revenue_categories:
            return "in"

        # Check for explicit direction
        if data.get("direction"):
            return data["direction"]

        # Default to out (expense)
        return "out"

    def _build_overlay_summary(
        self,
        delta: ScenarioDelta,
        events: List[OverlayForecastEvent],
    ) -> Dict[str, Any]:
        """Build summary statistics for the overlay."""
        virtual_events = [e for e in events if e.is_virtual]
        modified_events = [e for e in events if e.original_schedule_id]

        total_virtual_cash_in = sum(e.amount for e in virtual_events if e.direction == "in")
        total_virtual_cash_out = sum(e.amount for e in virtual_events if e.direction == "out")

        # Confidence breakdown
        confidence_counts = {"high": 0, "medium": 0, "low": 0}
        for e in events:
            confidence_counts[e.confidence.value] += 1

        return {
            "total_events": len(events),
            "virtual_events_count": len(virtual_events),
            "modified_events_count": len(modified_events),
            "deleted_schedules_count": len(delta.deleted_schedule_ids),
            "virtual_cash_in": str(total_virtual_cash_in),
            "virtual_cash_out": str(total_virtual_cash_out),
            "net_virtual_impact": str(total_virtual_cash_in - total_virtual_cash_out),
            "confidence_breakdown": confidence_counts,
            "created_agreements_count": len(delta.created_agreements),
            "deactivated_agreements_count": len(delta.deactivated_agreement_ids),
        }


def compute_weekly_forecast_from_events(
    events: List[OverlayForecastEvent],
    starting_cash: Decimal,
    start_date: date,
    num_weeks: int = 13,
) -> Dict[str, Any]:
    """
    Compute 13-week forecast from overlay events.

    This mirrors the structure of calculate_forecast_v2:
    - Week 0: Current position (starting balance, no events)
    - Weeks 1-13: Forecast weeks with events

    Total of 14 entries (week 0 + weeks 1-13) to match base forecast.
    """
    weeks = []
    current_balance = starting_cash

    # Week 0 - Current cash position (no events, just starting balance)
    # This matches calculate_forecast_v2 which adds Week 0 as current position
    weeks.append({
        "week_number": 0,
        "week_start": start_date.isoformat(),
        "week_end": start_date.isoformat(),
        "starting_balance": str(starting_cash),
        "cash_in": "0",
        "cash_out": "0",
        "net_change": "0",
        "ending_balance": str(starting_cash),
        "confidence_breakdown": {
            "cash_in": {"high": "0", "medium": "0", "low": "0"},
            "cash_out": {"high": "0", "medium": "0", "low": "0"},
        },
        "events": [],
    })

    # Weeks 1 through num_weeks (e.g., 1-13)
    for week_num in range(1, num_weeks + 1):
        week_start = start_date + timedelta(days=(week_num - 1) * 7)
        week_end = week_start + timedelta(days=6)

        # Filter events for this week
        week_events = [
            e for e in events
            if week_start <= e.date <= week_end
        ]

        cash_in = sum(e.amount for e in week_events if e.direction == "in")
        cash_out = sum(e.amount for e in week_events if e.direction == "out")
        net_change = cash_in - cash_out
        ending_balance = current_balance + net_change

        # Confidence breakdown for the week
        week_confidence = {
            "cash_in": {"high": Decimal("0"), "medium": Decimal("0"), "low": Decimal("0")},
            "cash_out": {"high": Decimal("0"), "medium": Decimal("0"), "low": Decimal("0")},
        }
        for e in week_events:
            key = "cash_in" if e.direction == "in" else "cash_out"
            week_confidence[key][e.confidence.value] += e.amount

        weeks.append({
            "week_number": week_num,
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "starting_balance": str(current_balance),
            "cash_in": str(cash_in),
            "cash_out": str(cash_out),
            "net_change": str(net_change),
            "ending_balance": str(ending_balance),
            "confidence_breakdown": {
                "cash_in": {k: str(v) for k, v in week_confidence["cash_in"].items()},
                "cash_out": {k: str(v) for k, v in week_confidence["cash_out"].items()},
            },
            "events": [
                {
                    "id": e.id,
                    "date": e.date.isoformat(),
                    "amount": str(e.amount),
                    "direction": e.direction,
                    "category": e.category,
                    "confidence": e.confidence.value,
                    "source_name": e.source_name,
                    "is_virtual": e.is_virtual,
                }
                for e in week_events
            ],
        })

        current_balance = ending_balance

    # Calculate summary (exclude Week 0 from min calculation since it's just starting position)
    forecast_weeks = [w for w in weeks if w["week_number"] > 0]
    balances = [Decimal(w["ending_balance"]) for w in forecast_weeks]
    lowest_balance = min(balances) if balances else starting_cash
    lowest_week_idx = balances.index(lowest_balance) if balances else 0
    lowest_week = forecast_weeks[lowest_week_idx]["week_number"] if forecast_weeks else 1

    total_cash_in = sum(Decimal(w["cash_in"]) for w in forecast_weeks)
    total_cash_out = sum(Decimal(w["cash_out"]) for w in forecast_weeks)

    # Runway calculation (based on forecast weeks, not Week 0)
    runway_weeks = num_weeks
    for i, balance in enumerate(balances):
        if balance <= 0:
            runway_weeks = i + 1
            break

    return {
        "starting_cash": str(starting_cash),
        "forecast_start_date": start_date.isoformat(),
        "weeks": weeks,
        "summary": {
            "lowest_cash_week": lowest_week,
            "lowest_cash_amount": str(lowest_balance),
            "total_cash_in": str(total_cash_in),
            "total_cash_out": str(total_cash_out),
            "runway_weeks": runway_weeks,
        },
    }
