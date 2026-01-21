"""
Detection → Preparation Pipeline - V4 Architecture

Orchestrates the flow from detection to preparation:
1. Run detection engine to find problems
2. Run preparation engine to generate solutions
3. Return combined results for action queue

This module provides the main entry points for running the
detection-preparation cycle, either on-demand or scheduled.
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession

from app.detection import DetectionEngine, DetectedAlert
from app.preparation import PreparationEngine, PreparedAction, EscalationEngine


class PipelineMode(str, Enum):
    """Pipeline execution modes."""
    FULL = "full"           # Run all detections
    CRITICAL = "critical"   # Only critical/emergency detections
    TARGETED = "targeted"   # Specific detection types only


@dataclass
class PipelineConfig:
    """Configuration for pipeline execution."""
    mode: PipelineMode = PipelineMode.FULL
    detection_types: Optional[List[str]] = None  # For targeted mode
    skip_preparation: bool = False  # Detection only
    max_alerts_to_prepare: int = 50  # Limit for preparation
    include_low_severity: bool = True  # Include UPCOMING severity


@dataclass
class PipelineResult:
    """Result of a pipeline execution."""
    user_id: str
    run_at: datetime
    mode: PipelineMode

    # Detection results
    alerts_detected: int = 0
    alerts_by_severity: Dict[str, int] = field(default_factory=dict)
    alerts_by_type: Dict[str, int] = field(default_factory=dict)

    # Preparation results
    actions_prepared: int = 0
    actions_by_type: Dict[str, int] = field(default_factory=dict)
    linked_action_groups: int = 0

    # Escalation results
    escalations_applied: int = 0
    escalation_details: List[Dict[str, Any]] = field(default_factory=list)

    # Performance
    detection_duration_ms: int = 0
    preparation_duration_ms: int = 0
    escalation_duration_ms: int = 0
    total_duration_ms: int = 0

    # Errors
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "user_id": self.user_id,
            "run_at": self.run_at.isoformat(),
            "mode": self.mode.value,
            "detection": {
                "alerts_detected": self.alerts_detected,
                "by_severity": self.alerts_by_severity,
                "by_type": self.alerts_by_type,
            },
            "preparation": {
                "actions_prepared": self.actions_prepared,
                "by_type": self.actions_by_type,
                "linked_groups": self.linked_action_groups,
            },
            "escalation": {
                "escalations_applied": self.escalations_applied,
                "details": self.escalation_details,
            },
            "performance": {
                "detection_ms": self.detection_duration_ms,
                "preparation_ms": self.preparation_duration_ms,
                "escalation_ms": self.escalation_duration_ms,
                "total_ms": self.total_duration_ms,
            },
            "errors": self.errors,
        }


async def run_detection_preparation_cycle(
    db: AsyncSession,
    user_id: str,
    config: Optional[PipelineConfig] = None,
) -> PipelineResult:
    """
    Run the complete detection → preparation cycle.

    This is the main entry point for the pipeline:
    1. Runs detection engine to identify problems
    2. Filters and prioritizes alerts
    3. Runs preparation engine to generate actions
    4. Links related actions
    5. Returns comprehensive result

    Args:
        db: Database session
        user_id: User ID to run pipeline for
        config: Optional pipeline configuration

    Returns:
        PipelineResult with detection and preparation metrics
    """
    config = config or PipelineConfig()
    start_time = datetime.utcnow()

    result = PipelineResult(
        user_id=user_id,
        run_at=start_time,
        mode=config.mode,
    )

    # Initialize engines
    detection_engine = DetectionEngine(db, user_id)
    preparation_engine = PreparationEngine(db, user_id)

    # ==========================================================================
    # Phase 1: Detection
    # ==========================================================================
    detection_start = datetime.utcnow()

    try:
        if config.mode == PipelineMode.CRITICAL:
            alerts = await detection_engine.run_critical_detections()
        elif config.mode == PipelineMode.TARGETED and config.detection_types:
            alerts = await _run_targeted_detections(
                detection_engine,
                config.detection_types
            )
        else:
            alerts = await detection_engine.run_all_detections()

    except Exception as e:
        result.errors.append(f"Detection error: {str(e)}")
        alerts = []

    detection_end = datetime.utcnow()
    result.detection_duration_ms = int(
        (detection_end - detection_start).total_seconds() * 1000
    )

    # Aggregate detection metrics
    result.alerts_detected = len(alerts)
    for alert in alerts:
        severity = alert.severity.value if hasattr(alert.severity, 'value') else str(alert.severity)
        result.alerts_by_severity[severity] = result.alerts_by_severity.get(severity, 0) + 1

        alert_type = alert.type.value if hasattr(alert.type, 'value') else str(alert.type)
        result.alerts_by_type[alert_type] = result.alerts_by_type.get(alert_type, 0) + 1

    # ==========================================================================
    # Phase 2: Filter & Prioritize Alerts
    # ==========================================================================
    if not config.include_low_severity:
        alerts = [a for a in alerts if a.severity.value != "upcoming"]

    # Limit alerts for preparation
    alerts = alerts[:config.max_alerts_to_prepare]

    # ==========================================================================
    # Phase 3: Preparation
    # ==========================================================================
    if config.skip_preparation or not alerts:
        result.total_duration_ms = int(
            (datetime.utcnow() - start_time).total_seconds() * 1000
        )
        return result

    preparation_start = datetime.utcnow()

    try:
        actions = await preparation_engine.prepare_actions_for_alerts(alerts)
    except Exception as e:
        result.errors.append(f"Preparation error: {str(e)}")
        actions = []

    preparation_end = datetime.utcnow()
    result.preparation_duration_ms = int(
        (preparation_end - preparation_start).total_seconds() * 1000
    )

    # Aggregate preparation metrics
    result.actions_prepared = len(actions)
    for action in actions:
        action_type = action.action_type.value if hasattr(action.action_type, 'value') else str(action.action_type)
        result.actions_by_type[action_type] = result.actions_by_type.get(action_type, 0) + 1

    # ==========================================================================
    # Phase 4: Detect Linked Actions
    # ==========================================================================
    try:
        result.linked_action_groups = await preparation_engine._detect_linked_actions(actions)
    except Exception as e:
        result.errors.append(f"Linking error: {str(e)}")

    # ==========================================================================
    # Phase 5: Escalation Check
    # ==========================================================================
    escalation_start = datetime.utcnow()

    try:
        escalation_engine = EscalationEngine(db, user_id)
        escalation_result = await escalation_engine.run_escalation_check(actions)

        result.escalations_applied = escalation_result.get("escalations_applied", 0)
        result.escalation_details = escalation_result.get("escalations", [])

    except Exception as e:
        result.errors.append(f"Escalation error: {str(e)}")

    escalation_end = datetime.utcnow()
    result.escalation_duration_ms = int(
        (escalation_end - escalation_start).total_seconds() * 1000
    )

    # Calculate total duration
    result.total_duration_ms = int(
        (datetime.utcnow() - start_time).total_seconds() * 1000
    )

    # ==========================================================================
    # Phase 6: Log Pipeline Run
    # ==========================================================================
    try:
        await log_pipeline_run(db, user_id, result)
    except Exception as e:
        # Don't fail the pipeline if logging fails
        result.errors.append(f"Logging error: {str(e)}")

    return result


async def _run_targeted_detections(
    engine: DetectionEngine,
    detection_types: List[str],
) -> List[DetectedAlert]:
    """Run specific detection types only."""
    all_alerts = []

    # Map detection type names to engine methods
    detection_methods = {
        "late_payment": engine._detect_late_payments,
        "unexpected_revenue": engine._detect_unexpected_revenue,
        "unexpected_expense": engine._detect_unexpected_expenses,
        "client_churn": engine._detect_client_churn,
        "revenue_variance": engine._detect_revenue_variance,
        "payment_timing_conflict": engine._detect_payment_timing_conflicts,
        "vendor_terms_expiring": engine._detect_vendor_terms_expiring,
        "statutory_deadline": engine._detect_statutory_deadlines,
        "buffer_breach": engine._detect_buffer_breach,
        "runway_threshold": engine._detect_runway_threshold,
        "payroll_safety": engine._detect_payroll_safety,
        "headcount_change": engine._detect_headcount_change,
    }

    for detection_type in detection_types:
        method = detection_methods.get(detection_type.lower())
        if method:
            try:
                alerts = await method()
                all_alerts.extend(alerts)
            except Exception:
                # Skip failed detections, continue with others
                pass

    return all_alerts


async def run_full_pipeline(
    db: AsyncSession,
    user_id: str,
    include_execution: bool = False,
) -> PipelineResult:
    """
    Run the full pipeline including optional execution preview.

    This is a convenience wrapper for run_detection_preparation_cycle
    with full mode enabled.

    Args:
        db: Database session
        user_id: User ID to run pipeline for
        include_execution: If True, also preview execution steps

    Returns:
        PipelineResult with all metrics
    """
    config = PipelineConfig(
        mode=PipelineMode.FULL,
        include_low_severity=True,
    )

    result = await run_detection_preparation_cycle(db, user_id, config)

    # Future: Add execution preview if requested
    # if include_execution:
    #     result = await _add_execution_preview(db, user_id, result)

    return result


# =============================================================================
# Pipeline Status & History
# =============================================================================

from sqlalchemy import select, func, and_, desc
from app.audit.models import AuditLog
from app.preparation.models import PreparedAction, ActionStatus


async def log_pipeline_run(
    db: AsyncSession,
    user_id: str,
    result: PipelineResult,
) -> None:
    """
    Log a pipeline run to the audit system.

    This creates an audit log entry for tracking pipeline execution history.
    """
    log = AuditLog(
        entity_type="pipeline",
        entity_id=f"run_{result.run_at.strftime('%Y%m%d_%H%M%S')}",
        action="create",
        user_id=user_id,
        source="system",
        new_value=result.to_dict(),
        metadata={
            "mode": result.mode.value,
            "alerts_detected": result.alerts_detected,
            "actions_prepared": result.actions_prepared,
            "escalations_applied": result.escalations_applied,
            "total_duration_ms": result.total_duration_ms,
            "has_errors": len(result.errors) > 0,
        },
        notes=f"Pipeline run: {result.alerts_detected} alerts, {result.actions_prepared} actions, {result.escalations_applied} escalations" if not result.errors else f"Pipeline run with errors: {result.errors}",
    )
    db.add(log)


async def get_last_pipeline_run(
    db: AsyncSession,
    user_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Get information about the last pipeline run.

    Queries the audit log for the most recent pipeline execution.
    """
    query = (
        select(AuditLog)
        .where(
            and_(
                AuditLog.entity_type == "pipeline",
                AuditLog.user_id == user_id,
                AuditLog.action == "create",
            )
        )
        .order_by(desc(AuditLog.created_at))
        .limit(1)
    )
    result = await db.execute(query)
    log = result.scalar_one_or_none()

    if not log:
        return None

    return {
        "run_id": log.entity_id,
        "run_at": log.created_at.isoformat() if log.created_at else None,
        "result": log.new_value,
        "metadata": log.metadata,
        "notes": log.notes,
    }


async def get_pipeline_history(
    db: AsyncSession,
    user_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Get recent pipeline run history.

    Returns the last N pipeline runs with summary info.
    """
    query = (
        select(AuditLog)
        .where(
            and_(
                AuditLog.entity_type == "pipeline",
                AuditLog.user_id == user_id,
                AuditLog.action == "create",
            )
        )
        .order_by(desc(AuditLog.created_at))
        .limit(limit)
    )
    result = await db.execute(query)
    logs = result.scalars().all()

    return [
        {
            "run_id": log.entity_id,
            "run_at": log.created_at.isoformat() if log.created_at else None,
            "mode": log.metadata.get("mode") if log.metadata else None,
            "alerts_detected": log.metadata.get("alerts_detected", 0) if log.metadata else 0,
            "actions_prepared": log.metadata.get("actions_prepared", 0) if log.metadata else 0,
            "escalations_applied": log.metadata.get("escalations_applied", 0) if log.metadata else 0,
            "duration_ms": log.metadata.get("total_duration_ms", 0) if log.metadata else 0,
            "has_errors": log.metadata.get("has_errors", False) if log.metadata else False,
        }
        for log in logs
    ]


async def get_pipeline_health(
    db: AsyncSession,
    user_id: str,
) -> Dict[str, Any]:
    """
    Get overall pipeline health metrics.

    Returns stats about recent pipeline runs, success rate,
    average processing time, and pending actions.
    """
    # Get recent pipeline runs (last 7 days)
    from datetime import datetime, timedelta

    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    query = (
        select(AuditLog)
        .where(
            and_(
                AuditLog.entity_type == "pipeline",
                AuditLog.user_id == user_id,
                AuditLog.action == "create",
                AuditLog.created_at >= seven_days_ago,
            )
        )
        .order_by(desc(AuditLog.created_at))
    )
    result = await db.execute(query)
    recent_runs = result.scalars().all()

    # Calculate metrics
    total_runs = len(recent_runs)
    successful_runs = sum(
        1 for run in recent_runs
        if run.metadata and not run.metadata.get("has_errors", False)
    )
    total_duration = sum(
        run.metadata.get("total_duration_ms", 0)
        for run in recent_runs
        if run.metadata
    )
    total_alerts = sum(
        run.metadata.get("alerts_detected", 0)
        for run in recent_runs
        if run.metadata
    )
    total_actions = sum(
        run.metadata.get("actions_prepared", 0)
        for run in recent_runs
        if run.metadata
    )
    total_escalations = sum(
        run.metadata.get("escalations_applied", 0)
        for run in recent_runs
        if run.metadata
    )

    # Get pending actions count
    pending_query = (
        select(func.count(PreparedAction.id))
        .where(
            and_(
                PreparedAction.user_id == user_id,
                PreparedAction.status == ActionStatus.PENDING_APPROVAL,
            )
        )
    )
    pending_result = await db.execute(pending_query)
    pending_actions = pending_result.scalar() or 0

    # Get approved but not executed actions
    approved_query = (
        select(func.count(PreparedAction.id))
        .where(
            and_(
                PreparedAction.user_id == user_id,
                PreparedAction.status == ActionStatus.APPROVED,
            )
        )
    )
    approved_result = await db.execute(approved_query)
    approved_actions = approved_result.scalar() or 0

    # Determine health status
    success_rate = successful_runs / total_runs if total_runs > 0 else 1.0
    avg_duration = total_duration / total_runs if total_runs > 0 else 0

    if success_rate >= 0.95 and pending_actions < 20:
        status = "healthy"
    elif success_rate >= 0.8 and pending_actions < 50:
        status = "warning"
    else:
        status = "degraded"

    # Get last run info
    last_run = recent_runs[0] if recent_runs else None

    return {
        "status": status,
        "last_run": {
            "run_id": last_run.entity_id if last_run else None,
            "run_at": last_run.created_at.isoformat() if last_run and last_run.created_at else None,
            "alerts_detected": last_run.metadata.get("alerts_detected", 0) if last_run and last_run.metadata else 0,
            "actions_prepared": last_run.metadata.get("actions_prepared", 0) if last_run and last_run.metadata else 0,
            "had_errors": last_run.metadata.get("has_errors", False) if last_run and last_run.metadata else False,
        } if last_run else None,
        "metrics": {
            "runs_last_7_days": total_runs,
            "success_rate": round(success_rate, 3),
            "avg_duration_ms": round(avg_duration, 1),
            "total_alerts_detected": total_alerts,
            "total_actions_prepared": total_actions,
            "total_escalations_applied": total_escalations,
        },
        "action_queue": {
            "pending_approval": pending_actions,
            "approved_pending_execution": approved_actions,
        },
    }


async def get_pipeline_stats_by_type(
    db: AsyncSession,
    user_id: str,
    days: int = 30,
) -> Dict[str, Any]:
    """
    Get pipeline statistics broken down by detection/action type.

    Useful for understanding what types of issues are being detected most.
    """
    from datetime import datetime, timedelta

    since = datetime.utcnow() - timedelta(days=days)

    query = (
        select(AuditLog)
        .where(
            and_(
                AuditLog.entity_type == "pipeline",
                AuditLog.user_id == user_id,
                AuditLog.action == "create",
                AuditLog.created_at >= since,
            )
        )
    )
    result = await db.execute(query)
    runs = result.scalars().all()

    # Aggregate by detection type
    alerts_by_type: Dict[str, int] = {}
    actions_by_type: Dict[str, int] = {}

    for run in runs:
        if not run.new_value:
            continue

        run_data = run.new_value
        detection = run_data.get("detection", {})
        preparation = run_data.get("preparation", {})

        # Aggregate alerts by type
        for alert_type, count in detection.get("by_type", {}).items():
            alerts_by_type[alert_type] = alerts_by_type.get(alert_type, 0) + count

        # Aggregate actions by type
        for action_type, count in preparation.get("by_type", {}).items():
            actions_by_type[action_type] = actions_by_type.get(action_type, 0) + count

    return {
        "period_days": days,
        "total_runs": len(runs),
        "alerts_by_type": dict(sorted(alerts_by_type.items(), key=lambda x: -x[1])),
        "actions_by_type": dict(sorted(actions_by_type.items(), key=lambda x: -x[1])),
    }
