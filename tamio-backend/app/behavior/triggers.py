"""
Trigger System - Phase 2: Monitor metrics and fire triggers.

This module implements:
1. Trigger evaluation against current metrics
2. Condition checking with configurable rules
3. Cooldown management to prevent trigger spam
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_

from app.behavior.models import (
    BehaviorMetric,
    BehaviorTrigger,
    TriggeredScenario,
    TriggerStatus,
    TriggerSeverity,
    MetricType,
)
from app.behavior.schemas import TriggeredScenarioResponse


# =============================================================================
# Default Trigger Definitions
# =============================================================================

DEFAULT_TRIGGERS = [
    # Client Behavior Triggers
    {
        "name": "Payment Reliability Drop",
        "description": "Top client's payment reliability has worsened",
        "conditions": {
            "metric_type": MetricType.PAYMENT_RELIABILITY.value,
            "operator": "less_than",
            "threshold": 70,
            "additional": {
                "trend": "worsening",
                "entity_concentration_min": 15,  # Only for clients >15% revenue
            }
        },
        "scenario_template": {
            "scenario_type": "payment_delay",
            "name_template": "{client_name} pays 21 days late for 2 cycles",
            "parameters": {
                "delay_weeks": 3,
                "cycles": 2,
            }
        },
        "recommended_actions": [
            "Draft chase sequence",
            "Adjust forecast confidence",
            "Recommend buffer hold",
            "Propose AP delay plan",
        ],
        "severity": TriggerSeverity.HIGH.value,
        "priority": 80,
        "cooldown_hours": 168,  # 1 week
    },
    {
        "name": "High Revenue Concentration",
        "description": "Single client represents too much of revenue",
        "conditions": {
            "metric_type": MetricType.CLIENT_CONCENTRATION.value,
            "operator": "greater_than",
            "threshold": 40,
        },
        "scenario_template": {
            "scenario_type": "client_loss",
            "name_template": "What if {client_name} churns?",
            "parameters": {
                "churn_probability": 0.3,
            }
        },
        "recommended_actions": [
            "Run client loss scenario",
            "Identify diversification opportunities",
            "Review contract terms",
        ],
        "severity": TriggerSeverity.MEDIUM.value,
        "priority": 60,
        "cooldown_hours": 336,  # 2 weeks
    },
    {
        "name": "Revenue at Risk Elevated",
        "description": "Significant revenue is at risk due to payment patterns",
        "conditions": {
            "metric_type": MetricType.REVENUE_AT_RISK.value,
            "operator": "greater_than",
            "threshold": 20,
        },
        "scenario_template": {
            "scenario_type": "payment_delay",
            "name_template": "Multiple clients pay late",
            "parameters": {
                "delay_weeks": 2,
                "affected_percentage": 0.2,
            }
        },
        "recommended_actions": [
            "AR escalation campaign",
            "Review payment terms",
            "Consider early payment incentives",
        ],
        "severity": TriggerSeverity.HIGH.value,
        "priority": 75,
        "cooldown_hours": 168,
    },

    # Expense Behavior Triggers
    {
        "name": "Expense Category Drift",
        "description": "An expense category is drifting above baseline",
        "conditions": {
            "metric_type": MetricType.EXPENSE_VOLATILITY.value,
            "operator": "greater_than",
            "threshold": 50,
            "additional": {
                "drift_min": 10,  # At least 10% drift
            }
        },
        "scenario_template": {
            "scenario_type": "increased_expense",
            "name_template": "{category} spend +{drift}% for 6 weeks",
            "parameters": {
                "duration_weeks": 6,
            }
        },
        "recommended_actions": [
            "Flag approvals in category",
            "Cap category spending",
            "Suggest staffing alternatives",
            "Recommend timing changes",
        ],
        "severity": TriggerSeverity.MEDIUM.value,
        "priority": 55,
        "cooldown_hours": 168,
    },
    {
        "name": "High Discretionary Spending",
        "description": "Discretionary spending ratio is elevated",
        "conditions": {
            "metric_type": MetricType.DISCRETIONARY_RATIO.value,
            "operator": "greater_than",
            "threshold": 45,
        },
        "scenario_template": {
            "scenario_type": "decreased_expense",
            "name_template": "Reduce discretionary spending by 20%",
            "parameters": {
                "reduction_percentage": 0.2,
            }
        },
        "recommended_actions": [
            "Review discretionary expenses",
            "Identify deferrable items",
            "Run expense reduction scenario",
        ],
        "severity": TriggerSeverity.LOW.value,
        "priority": 40,
        "cooldown_hours": 336,
    },

    # Cash Discipline Triggers
    {
        "name": "Buffer Integrity Breach",
        "description": "Cash buffer is below target",
        "conditions": {
            "metric_type": MetricType.BUFFER_INTEGRITY.value,
            "operator": "less_than",
            "threshold": 100,
        },
        "scenario_template": {
            "scenario_type": "payment_delay_out",
            "name_template": "Buffer below target for {days} days",
            "parameters": {
                "delay_strategies": ["ar_acceleration", "ap_delay", "expense_freeze"],
            }
        },
        "recommended_actions": [
            "AR escalation",
            "AP reprioritization",
            "Spending freeze proposals",
            "Runway update",
        ],
        "severity": TriggerSeverity.HIGH.value,
        "priority": 90,
        "cooldown_hours": 72,  # 3 days
    },
    {
        "name": "Buffer Critical",
        "description": "Cash buffer is critically low",
        "conditions": {
            "metric_type": MetricType.BUFFER_INTEGRITY.value,
            "operator": "less_than",
            "threshold": 70,
        },
        "scenario_template": {
            "scenario_type": "payment_delay_out",
            "name_template": "Emergency buffer recovery",
            "parameters": {
                "urgency": "critical",
            }
        },
        "recommended_actions": [
            "Immediate AR collection",
            "Defer all non-essential expenses",
            "Negotiate payment extensions",
            "Consider emergency funding",
        ],
        "severity": TriggerSeverity.CRITICAL.value,
        "priority": 100,
        "cooldown_hours": 24,
    },
    {
        "name": "Negative Burn Momentum",
        "description": "Buffer is consistently depleting",
        "conditions": {
            "metric_type": MetricType.BURN_MOMENTUM.value,
            "operator": "less_than",
            "threshold": -5,  # Burning >5% per week
        },
        "scenario_template": {
            "scenario_type": "decreased_expense",
            "name_template": "Stop buffer depletion",
            "parameters": {
                "target_momentum": 0,
            }
        },
        "recommended_actions": [
            "Identify expense reduction opportunities",
            "Accelerate receivables",
            "Review recurring commitments",
        ],
        "severity": TriggerSeverity.MEDIUM.value,
        "priority": 65,
        "cooldown_hours": 168,
    },
    {
        "name": "High Reactive Decision Rate",
        "description": "Too many decisions made under buffer stress",
        "conditions": {
            "metric_type": MetricType.REACTIVE_DECISION_RATE.value,
            "operator": "greater_than",
            "threshold": 30,
        },
        "scenario_template": {
            "scenario_type": "client_gain",  # Focus on building buffer
            "name_template": "Improve decision quality through buffer building",
            "parameters": {
                "target_buffer_increase": 0.2,
            }
        },
        "recommended_actions": [
            "Pre-plan larger expenses",
            "Build buffer to reduce stress",
            "Implement approval workflows",
        ],
        "severity": TriggerSeverity.LOW.value,
        "priority": 35,
        "cooldown_hours": 336,
    },
]


# =============================================================================
# Trigger Evaluation
# =============================================================================

def _check_condition(
    metric: BehaviorMetric,
    operator: str,
    threshold: float,
    additional: Optional[Dict[str, Any]] = None
) -> bool:
    """Check if a metric meets a trigger condition."""
    value = metric.current_value

    # Basic comparison
    if operator == "less_than":
        basic_met = value < threshold
    elif operator == "greater_than":
        basic_met = value > threshold
    elif operator == "equals":
        basic_met = abs(value - threshold) < 0.01
    elif operator == "not_equals":
        basic_met = abs(value - threshold) >= 0.01
    else:
        basic_met = False

    if not basic_met:
        return False

    # Additional conditions
    if additional:
        # Check trend
        if "trend" in additional:
            if metric.trend != additional["trend"]:
                return False

        # Check drift minimum
        if "drift_min" in additional:
            drift = metric.trend_velocity or 0
            if drift < additional["drift_min"]:
                return False

        # Check entity concentration (needs context data)
        if "entity_concentration_min" in additional:
            concentration = metric.context_data.get("cash_weighted_share", 0)
            if concentration < additional["entity_concentration_min"]:
                return False

    return True


def _is_in_cooldown(trigger: BehaviorTrigger) -> bool:
    """Check if trigger is in cooldown period."""
    if not trigger.last_triggered_at:
        return False

    cooldown_end = trigger.last_triggered_at + timedelta(hours=trigger.cooldown_hours)
    return datetime.utcnow() < cooldown_end


async def evaluate_triggers(
    db: AsyncSession,
    user_id: str,
    metrics: List[BehaviorMetric]
) -> List[TriggeredScenario]:
    """
    Evaluate all triggers against current metrics.

    Returns list of newly triggered scenarios.
    """
    # Get user's triggers (or use defaults)
    result = await db.execute(
        select(BehaviorTrigger)
        .where(
            and_(
                BehaviorTrigger.user_id == user_id,
                BehaviorTrigger.is_active == True
            )
        )
        .order_by(BehaviorTrigger.priority.desc())
    )
    user_triggers = list(result.scalars().all())

    # If no custom triggers, create defaults
    if not user_triggers:
        user_triggers = await _create_default_triggers(db, user_id)

    triggered_scenarios: List[TriggeredScenario] = []

    for trigger in user_triggers:
        # Skip if in cooldown
        if _is_in_cooldown(trigger):
            continue

        conditions = trigger.conditions
        metric_type = conditions.get("metric_type")
        operator = conditions.get("operator")
        threshold = conditions.get("threshold")
        additional = conditions.get("additional")

        # Find matching metrics
        matching_metrics = [
            m for m in metrics
            if m.metric_type == metric_type
        ]

        for metric in matching_metrics:
            if _check_condition(metric, operator, threshold, additional):
                # Trigger fired!
                scenario = _create_triggered_scenario(
                    trigger=trigger,
                    metric=metric,
                    user_id=user_id,
                )
                triggered_scenarios.append(scenario)

                # Update trigger's last fired time
                trigger.last_triggered_at = datetime.utcnow()

                # Only fire once per trigger per evaluation
                break

    # Save all new triggered scenarios
    for scenario in triggered_scenarios:
        db.add(scenario)

    await db.commit()

    return triggered_scenarios


def _create_triggered_scenario(
    trigger: BehaviorTrigger,
    metric: BehaviorMetric,
    user_id: str,
) -> TriggeredScenario:
    """Create a TriggeredScenario from a fired trigger."""
    template = trigger.scenario_template
    context = metric.context_data

    # Format scenario name with context
    name_template = template.get("name_template", trigger.name)
    scenario_name = name_template.format(
        client_name=context.get("client_name", "Client"),
        category=context.get("category", "Category"),
        drift=context.get("drift_percentage", 0),
        days=context.get("days_below_target", 0),
        **context
    )

    # Build estimated impact
    estimated_impact = {
        "metric_value": metric.current_value,
        "threshold": trigger.conditions.get("threshold"),
        "breach_amount": abs(metric.current_value - trigger.conditions.get("threshold", 0)),
    }

    # Add cash impact estimate based on context
    if "monthly_amount" in context:
        estimated_impact["monthly_amount"] = context["monthly_amount"]

    return TriggeredScenario(
        trigger_id=trigger.id,
        user_id=user_id,
        trigger_context={
            "metric_type": metric.metric_type,
            "metric_value": metric.current_value,
            "metric_trend": metric.trend,
            "entity_type": metric.entity_type,
            "entity_id": metric.entity_id,
            "context_data": context,
        },
        scenario_name=scenario_name,
        scenario_description=trigger.description,
        scenario_type=template.get("scenario_type", "payment_delay"),
        scenario_parameters=template.get("parameters", {}),
        recommended_actions=trigger.recommended_actions,
        severity=trigger.severity,
        estimated_impact=estimated_impact,
        status=TriggerStatus.PENDING.value,
        expires_at=datetime.utcnow() + timedelta(days=7),  # Expire after 1 week
    )


async def _create_default_triggers(
    db: AsyncSession,
    user_id: str
) -> List[BehaviorTrigger]:
    """Create default triggers for a user."""
    triggers = []

    for trigger_def in DEFAULT_TRIGGERS:
        trigger = BehaviorTrigger(
            user_id=user_id,
            name=trigger_def["name"],
            description=trigger_def["description"],
            conditions=trigger_def["conditions"],
            scenario_template=trigger_def["scenario_template"],
            recommended_actions=trigger_def["recommended_actions"],
            severity=trigger_def["severity"],
            priority=trigger_def["priority"],
            cooldown_hours=trigger_def["cooldown_hours"],
            is_active=True,
        )
        db.add(trigger)
        triggers.append(trigger)

    await db.commit()
    return triggers


# =============================================================================
# Query Functions
# =============================================================================

async def get_active_triggers(
    db: AsyncSession,
    user_id: str
) -> List[BehaviorTrigger]:
    """Get all active triggers for a user."""
    result = await db.execute(
        select(BehaviorTrigger)
        .where(
            and_(
                BehaviorTrigger.user_id == user_id,
                BehaviorTrigger.is_active == True
            )
        )
        .order_by(BehaviorTrigger.priority.desc())
    )
    return list(result.scalars().all())


async def get_pending_triggered_scenarios(
    db: AsyncSession,
    user_id: str
) -> List[TriggeredScenario]:
    """Get all pending triggered scenarios for a user."""
    result = await db.execute(
        select(TriggeredScenario)
        .where(
            and_(
                TriggeredScenario.user_id == user_id,
                TriggeredScenario.status == TriggerStatus.PENDING.value,
                or_(
                    TriggeredScenario.expires_at.is_(None),
                    TriggeredScenario.expires_at > datetime.utcnow()
                )
            )
        )
        .order_by(TriggeredScenario.triggered_at.desc())
    )
    return list(result.scalars().all())


async def respond_to_triggered_scenario(
    db: AsyncSession,
    triggered_scenario_id: str,
    user_response: str,
    notes: Optional[str] = None,
    scenario_id: Optional[str] = None
) -> TriggeredScenario:
    """Record user's response to a triggered scenario."""
    result = await db.execute(
        select(TriggeredScenario)
        .where(TriggeredScenario.id == triggered_scenario_id)
    )
    ts = result.scalar_one_or_none()

    if not ts:
        raise ValueError(f"Triggered scenario {triggered_scenario_id} not found")

    ts.user_response = user_response
    ts.response_notes = notes
    ts.responded_at = datetime.utcnow()

    if user_response == "ran_scenario" and scenario_id:
        ts.scenario_id = scenario_id
        ts.status = TriggerStatus.ACTIVE.value
    elif user_response == "dismissed":
        ts.status = TriggerStatus.DISMISSED.value
    elif user_response == "deferred":
        # Extend expiration
        ts.expires_at = datetime.utcnow() + timedelta(days=3)

    await db.commit()
    return ts
