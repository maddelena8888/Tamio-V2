"""
Confidence scoring system for forecast data.

Confidence levels are determined by how well the data is backed by
accounting software integrations:

- HIGH: Full sync with recurring invoice/bill (strongest certainty)
- MEDIUM: Synced as contact but no invoice/bill link
- LOW: Manual entry, not linked to any accounting software

This module provides functions to calculate confidence for clients
and expenses, which is then used in forecast calculations.
"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, TYPE_CHECKING
from decimal import Decimal

if TYPE_CHECKING:
    from app.data.clients.models import Client
    from app.data.expenses.models import ExpenseBucket


class ConfidenceLevel(str, Enum):
    """Confidence levels for forecast data."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


# Confidence weights for financial calculations
CONFIDENCE_WEIGHTS = {
    ConfidenceLevel.HIGH: Decimal("1.0"),    # 100% weight
    ConfidenceLevel.MEDIUM: Decimal("0.8"),  # 80% weight
    ConfidenceLevel.LOW: Decimal("0.5"),     # 50% weight
}


@dataclass
class ConfidenceScore:
    """
    Detailed confidence score for a forecast item.

    Includes the level, reason, and suggestions for improvement.
    """
    level: ConfidenceLevel
    reason: str
    weight: Decimal
    improvement_suggestion: Optional[str] = None

    @property
    def level_str(self) -> str:
        return self.level.value


def calculate_client_confidence(client: "Client") -> ConfidenceScore:
    """
    Calculate confidence score for a client's revenue forecast.

    Confidence hierarchy:
    1. HIGH: Has xero_repeating_invoice_id or quickbooks equivalent
    2. MEDIUM: Has xero_contact_id or quickbooks_customer_id (synced contact)
    3. LOW: Manual entry, no integration link

    Args:
        client: Client model instance

    Returns:
        ConfidenceScore with level, reason, and suggestions
    """
    # Check for full sync (repeating invoice)
    if client.xero_repeating_invoice_id:
        return ConfidenceScore(
            level=ConfidenceLevel.HIGH,
            reason="Linked to Xero with repeating invoice",
            weight=CONFIDENCE_WEIGHTS[ConfidenceLevel.HIGH],
            improvement_suggestion=None
        )

    # Future: Check QuickBooks repeating invoice
    # if client.quickbooks_recurring_invoice_id:
    #     return ConfidenceScore(...)

    # Check for partial sync (contact linked)
    if client.xero_contact_id:
        return ConfidenceScore(
            level=ConfidenceLevel.MEDIUM,
            reason="Synced to Xero as contact",
            weight=CONFIDENCE_WEIGHTS[ConfidenceLevel.MEDIUM],
            improvement_suggestion="Create a repeating invoice in Xero for this client to increase forecast accuracy"
        )

    if client.quickbooks_customer_id:
        return ConfidenceScore(
            level=ConfidenceLevel.MEDIUM,
            reason="Synced to QuickBooks as customer",
            weight=CONFIDENCE_WEIGHTS[ConfidenceLevel.MEDIUM],
            improvement_suggestion="Create a recurring invoice in QuickBooks for this client to increase forecast accuracy"
        )

    # Check if source is from integration but no link (shouldn't happen, but handle it)
    if client.source in ("xero", "quickbooks"):
        return ConfidenceScore(
            level=ConfidenceLevel.MEDIUM,
            reason=f"Imported from {client.source.title()}",
            weight=CONFIDENCE_WEIGHTS[ConfidenceLevel.MEDIUM],
            improvement_suggestion="Re-sync to link this client to your accounting software"
        )

    # Manual entry - lowest confidence
    return ConfidenceScore(
        level=ConfidenceLevel.LOW,
        reason="Manual entry, not linked to accounting software",
        weight=CONFIDENCE_WEIGHTS[ConfidenceLevel.LOW],
        improvement_suggestion="Connect to Xero or QuickBooks and create an invoice for this client"
    )


def calculate_expense_confidence(bucket: "ExpenseBucket") -> ConfidenceScore:
    """
    Calculate confidence score for an expense bucket's forecast.

    Confidence hierarchy:
    1. HIGH: Has xero_repeating_bill_id or quickbooks equivalent
    2. MEDIUM: Has xero_contact_id or quickbooks_vendor_id (synced supplier)
    3. LOW: Manual entry, no integration link

    Args:
        bucket: ExpenseBucket model instance

    Returns:
        ConfidenceScore with level, reason, and suggestions
    """
    # Check for full sync (repeating bill)
    if bucket.xero_repeating_bill_id:
        return ConfidenceScore(
            level=ConfidenceLevel.HIGH,
            reason="Linked to Xero with repeating bill",
            weight=CONFIDENCE_WEIGHTS[ConfidenceLevel.HIGH],
            improvement_suggestion=None
        )

    # Future: Check QuickBooks recurring bill
    # if bucket.quickbooks_recurring_bill_id:
    #     return ConfidenceScore(...)

    # Check for partial sync (supplier linked)
    if bucket.xero_contact_id:
        return ConfidenceScore(
            level=ConfidenceLevel.MEDIUM,
            reason="Synced to Xero as supplier",
            weight=CONFIDENCE_WEIGHTS[ConfidenceLevel.MEDIUM],
            improvement_suggestion="Create a repeating bill in Xero for this expense to increase forecast accuracy"
        )

    if bucket.quickbooks_vendor_id:
        return ConfidenceScore(
            level=ConfidenceLevel.MEDIUM,
            reason="Synced to QuickBooks as vendor",
            weight=CONFIDENCE_WEIGHTS[ConfidenceLevel.MEDIUM],
            improvement_suggestion="Create a recurring bill in QuickBooks for this expense to increase forecast accuracy"
        )

    # Check if source is from integration but no link
    if bucket.source in ("xero", "quickbooks"):
        return ConfidenceScore(
            level=ConfidenceLevel.MEDIUM,
            reason=f"Imported from {bucket.source.title()}",
            weight=CONFIDENCE_WEIGHTS[ConfidenceLevel.MEDIUM],
            improvement_suggestion="Re-sync to link this expense to your accounting software"
        )

    # Manual entry - lowest confidence
    return ConfidenceScore(
        level=ConfidenceLevel.LOW,
        reason="Manual entry, not linked to accounting software",
        weight=CONFIDENCE_WEIGHTS[ConfidenceLevel.LOW],
        improvement_suggestion="Connect to Xero or QuickBooks and create a bill for this expense"
    )


@dataclass
class ForecastConfidenceSummary:
    """
    Overall confidence summary for a forecast.

    Aggregates confidence scores across all revenue and expense sources.
    """
    overall_score: Decimal  # 0.0 to 1.0
    overall_level: ConfidenceLevel
    high_confidence_count: int
    medium_confidence_count: int
    low_confidence_count: int
    high_confidence_amount: Decimal
    medium_confidence_amount: Decimal
    low_confidence_amount: Decimal
    total_amount: Decimal
    improvement_suggestions: List[str]

    @property
    def overall_percentage(self) -> int:
        """Return overall score as a percentage (0-100)."""
        return int(self.overall_score * 100)


def calculate_forecast_confidence_summary(
    client_scores: List[tuple],  # List of (Client, ConfidenceScore, monthly_amount)
    expense_scores: List[tuple],  # List of (ExpenseBucket, ConfidenceScore, monthly_amount)
) -> ForecastConfidenceSummary:
    """
    Calculate overall confidence summary for a forecast.

    This aggregates individual confidence scores weighted by their
    financial impact (amount).

    Args:
        client_scores: List of (client, score, amount) tuples
        expense_scores: List of (bucket, score, amount) tuples

    Returns:
        ForecastConfidenceSummary with overall metrics
    """
    high_count = 0
    medium_count = 0
    low_count = 0
    high_amount = Decimal("0")
    medium_amount = Decimal("0")
    low_amount = Decimal("0")
    suggestions = []

    # Process all items
    all_items = list(client_scores) + list(expense_scores)

    for item, score, amount in all_items:
        amount = Decimal(str(amount)) if amount else Decimal("0")

        if score.level == ConfidenceLevel.HIGH:
            high_count += 1
            high_amount += amount
        elif score.level == ConfidenceLevel.MEDIUM:
            medium_count += 1
            medium_amount += amount
            if score.improvement_suggestion:
                suggestions.append(f"{item.name}: {score.improvement_suggestion}")
        else:
            low_count += 1
            low_amount += amount
            if score.improvement_suggestion:
                suggestions.append(f"{item.name}: {score.improvement_suggestion}")

    total_amount = high_amount + medium_amount + low_amount
    total_count = high_count + medium_count + low_count

    # Calculate weighted score based on amounts
    if total_amount > 0:
        weighted_score = (
            (high_amount * CONFIDENCE_WEIGHTS[ConfidenceLevel.HIGH]) +
            (medium_amount * CONFIDENCE_WEIGHTS[ConfidenceLevel.MEDIUM]) +
            (low_amount * CONFIDENCE_WEIGHTS[ConfidenceLevel.LOW])
        ) / total_amount
    elif total_count > 0:
        # Fall back to count-based weighting
        weighted_score = Decimal(str(
            (high_count * 1.0 + medium_count * 0.8 + low_count * 0.5) / total_count
        ))
    else:
        weighted_score = Decimal("0")

    # Determine overall level
    if weighted_score >= Decimal("0.9"):
        overall_level = ConfidenceLevel.HIGH
    elif weighted_score >= Decimal("0.7"):
        overall_level = ConfidenceLevel.MEDIUM
    else:
        overall_level = ConfidenceLevel.LOW

    return ForecastConfidenceSummary(
        overall_score=weighted_score,
        overall_level=overall_level,
        high_confidence_count=high_count,
        medium_confidence_count=medium_count,
        low_confidence_count=low_count,
        high_confidence_amount=high_amount,
        medium_confidence_amount=medium_amount,
        low_confidence_amount=low_amount,
        total_amount=total_amount,
        improvement_suggestions=suggestions[:10]  # Limit to top 10
    )
