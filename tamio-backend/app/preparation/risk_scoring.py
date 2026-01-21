"""
Risk Scoring - V4 Architecture

Implements risk scoring from the product brief:
- Composite risk = (relationship_risk × 0.4) + (operational_risk × 0.3) + (financial_cost × 0.3)

Each component is calculated based on entity attributes and context.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class RiskScore:
    """Container for risk score components."""
    composite_risk: float  # 0-100 overall risk score
    relationship_risk: float  # 0-1 risk to client/vendor relationship
    operational_risk: float  # 0-1 risk to business operations
    financial_cost: float  # Absolute cost in base currency

    def to_dict(self) -> Dict[str, Any]:
        return {
            "composite_risk": self.composite_risk,
            "relationship_risk": self.relationship_risk,
            "operational_risk": self.operational_risk,
            "financial_cost": self.financial_cost,
        }


def calculate_composite_risk(
    relationship_risk: float,
    operational_risk: float,
    financial_cost: float,
    context: Optional[Dict[str, Any]] = None
) -> float:
    """
    Calculate composite risk score from components.

    Formula: (relationship_risk × 0.4) + (operational_risk × 0.3) + (normalized_financial × 0.3)

    Args:
        relationship_risk: 0-1 score for relationship damage risk
        operational_risk: 0-1 score for operational disruption risk
        financial_cost: Absolute cost in currency units
        context: Optional context for normalization (e.g., monthly revenue for scaling)

    Returns:
        Composite risk score 0-100
    """
    # Normalize financial cost to 0-1 scale
    # Use context for scaling if provided, otherwise use sensible default
    monthly_revenue = 100000  # Default assumption
    if context and "monthly_revenue" in context:
        monthly_revenue = max(1, context["monthly_revenue"])

    # Normalize: $0 = 0, monthly_revenue = 0.5, 2x monthly_revenue = 1.0
    normalized_financial = min(1.0, financial_cost / (2 * monthly_revenue))

    # Calculate composite
    composite = (
        (relationship_risk * 0.4) +
        (operational_risk * 0.3) +
        (normalized_financial * 0.3)
    )

    # Scale to 0-100
    return round(composite * 100, 1)


def calculate_relationship_risk(
    entity_type: str,
    context: Dict[str, Any]
) -> float:
    """
    Calculate relationship risk for an action.

    Args:
        entity_type: "client" or "vendor"
        context: Entity context from context.py functions

    Returns:
        Risk score 0-1
    """
    risk = 0.2  # Base risk

    if entity_type == "client":
        # Strategic clients have higher relationship risk
        if context.get("relationship_type") == "strategic":
            risk += 0.3
        elif context.get("relationship_type") == "managed":
            risk += 0.15

        # High revenue concentration increases risk
        revenue_pct = context.get("revenue_percent", 0)
        if revenue_pct >= 20:
            risk += 0.3
        elif revenue_pct >= 10:
            risk += 0.15
        elif revenue_pct >= 5:
            risk += 0.05

        # Good payers are more valuable
        if context.get("payment_behavior") == "on_time":
            risk += 0.1

        # High churn risk means we should be careful
        if context.get("churn_risk") == "high":
            risk += 0.2
        elif context.get("churn_risk") == "medium":
            risk += 0.1

    elif entity_type == "vendor":
        # Critical vendors have higher relationship risk
        if context.get("criticality") == "critical":
            risk += 0.3
        elif context.get("criticality") == "important":
            risk += 0.15

        # Past delays affect relationship
        delay_count = context.get("delay_history_count", 0)
        if delay_count >= 3:
            risk += 0.2  # Already strained
        elif delay_count >= 1:
            risk += 0.1

        # Flexibility matters
        if context.get("flexibility_level") == "cannot_delay":
            risk += 0.2
        elif context.get("flexibility_level") == "negotiable":
            risk += 0.05

    return min(1.0, risk)


def calculate_operational_risk(
    action_type: str,
    context: Dict[str, Any]
) -> float:
    """
    Calculate operational risk for an action.

    Args:
        action_type: Type of action being considered
        context: Combined context including cash, entity info

    Returns:
        Risk score 0-1
    """
    risk = 0.1  # Base risk

    # Invoice follow-up has low operational risk
    if action_type in ["INVOICE_FOLLOW_UP", "PAYMENT_REMINDER"]:
        risk = 0.05

    # Collection escalation has medium risk
    elif action_type == "COLLECTION_ESCALATION":
        risk = 0.3

    # Vendor delay has operational implications
    elif action_type == "VENDOR_DELAY":
        criticality = context.get("criticality", "important")
        if criticality == "critical":
            risk = 0.6
        elif criticality == "important":
            risk = 0.3
        else:
            risk = 0.1

        # Category matters
        category = context.get("category", "other")
        if category == "payroll":
            risk = 0.9  # Never delay payroll
        elif category == "rent":
            risk = max(risk, 0.5)
        elif category == "software":
            risk = min(risk, 0.3)  # Usually can manage

    # Payment prioritization affects multiple parties
    elif action_type == "PAYMENT_PRIORITIZATION":
        risk = 0.4

    # Payroll contingency is high stakes
    elif action_type in ["PAYROLL_CONTINGENCY", "PAYROLL_CONFIRMATION"]:
        cash_after_payroll = context.get("cash_after_payroll", 0)
        if cash_after_payroll < 0:
            risk = 0.9
        elif cash_after_payroll < context.get("buffer_needed", 0):
            risk = 0.6
        else:
            risk = 0.2

    # Credit line draw has financial but low operational risk
    elif action_type == "CREDIT_LINE_DRAW":
        risk = 0.1

    return min(1.0, risk)


def calculate_financial_cost(
    action_type: str,
    context: Dict[str, Any]
) -> float:
    """
    Calculate financial cost of an action.

    Args:
        action_type: Type of action being considered
        context: Context including amounts, rates, etc.

    Returns:
        Estimated cost in base currency
    """
    cost = 0.0

    if action_type == "CREDIT_LINE_DRAW":
        # Interest cost
        amount = context.get("amount", 0)
        annual_rate = context.get("interest_rate", 0.08)
        months = context.get("expected_months", 1)
        cost = amount * (annual_rate / 12) * months

    elif action_type == "VENDOR_DELAY":
        # Potential late fee
        amount = context.get("amount", 0)
        late_fee_pct = context.get("late_fee_percent", 0.015)  # 1.5% default
        cost = amount * late_fee_pct

        # Relationship cost (harder to quantify)
        # Could add premium to future negotiations
        if context.get("delay_history_count", 0) >= 2:
            cost += amount * 0.02  # 2% premium risk

    elif action_type == "COLLECTION_ESCALATION":
        # Risk of losing client
        revenue_pct = context.get("revenue_percent", 0)
        monthly_revenue = context.get("monthly_revenue", 100000)
        churn_probability = 0.1 if revenue_pct < 5 else 0.05
        cost = monthly_revenue * (revenue_pct / 100) * 12 * churn_probability

    elif action_type in ["INVOICE_FOLLOW_UP", "PAYMENT_REMINDER"]:
        # Minimal direct cost
        cost = 0

    elif action_type == "PAYMENT_PRIORITIZATION":
        # Late fees on delayed items
        delayed_amount = context.get("delayed_amount", 0)
        cost = delayed_amount * 0.015

    return cost


def score_action_option(
    action_type: str,
    entity_type: str,
    entity_context: Dict[str, Any],
    cash_context: Dict[str, Any],
    option_specific: Optional[Dict[str, Any]] = None
) -> RiskScore:
    """
    Calculate complete risk score for an action option.

    This is the main function to call when scoring options.

    Args:
        action_type: ActionType enum value as string
        entity_type: "client" or "vendor"
        entity_context: Context from get_client_context or get_vendor_context
        cash_context: Context from get_cash_context
        option_specific: Additional option-specific parameters

    Returns:
        RiskScore with all components
    """
    option_specific = option_specific or {}

    # Merge contexts
    combined_context = {
        **entity_context,
        **cash_context,
        **option_specific,
    }

    # Calculate components
    relationship_risk = calculate_relationship_risk(entity_type, entity_context)
    operational_risk = calculate_operational_risk(action_type, combined_context)
    financial_cost = calculate_financial_cost(action_type, combined_context)

    # Calculate composite
    composite = calculate_composite_risk(
        relationship_risk,
        operational_risk,
        financial_cost,
        context={"monthly_revenue": cash_context.get("monthly_revenue", 100000)}
    )

    return RiskScore(
        composite_risk=composite,
        relationship_risk=relationship_risk,
        operational_risk=operational_risk,
        financial_cost=financial_cost,
    )


def rank_options_by_risk(options: list[Dict[str, Any]]) -> list[Dict[str, Any]]:
    """
    Sort action options by risk score (lowest first).

    Each option dict should have a 'risk_score' key with a RiskScore object.

    Returns sorted list with display_order updated.
    """
    # Sort by composite risk
    sorted_options = sorted(
        options,
        key=lambda x: x.get("risk_score", RiskScore(100, 1, 1, 0)).composite_risk
    )

    # Update display order
    for i, option in enumerate(sorted_options):
        option["display_order"] = i

    return sorted_options
