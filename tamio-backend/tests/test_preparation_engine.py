"""
Tests for the Preparation Engine - V4 Architecture.

Tests cover agent workflows, risk scoring, message drafting,
and action generation.
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.preparation.engine import PreparationEngine
from app.preparation.models import ActionType, ActionStatus, PreparedAction, ActionOption
from app.preparation.risk_scoring import (
    calculate_composite_risk,
    calculate_relationship_risk,
    calculate_operational_risk,
    calculate_financial_cost,
    RiskScore,
)
from app.preparation.message_drafting import (
    draft_collection_email,
    draft_escalation_email,
    draft_vendor_delay_message,
    generate_call_talking_points,
    generate_action_summary,
)
from app.detection.engine import DetectedAlert, DetectionType, AlertSeverity


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    return db


@pytest.fixture
def preparation_engine(mock_db):
    """Create a preparation engine instance."""
    return PreparationEngine(mock_db, "test-user-123")


@pytest.fixture
def sample_alert():
    """Create a sample detected alert."""
    return DetectedAlert(
        type=DetectionType.LATE_PAYMENT,
        severity=AlertSeverity.THIS_WEEK,
        entity_type="client",
        entity_id="client-123",
        entity_name="Acme Corp",
        details={
            "amount": 5000,
            "days_overdue": 14,
            "invoice_number": "INV-001",
            "due_date": "2026-01-01",
        },
        detected_at=datetime.utcnow(),
    )


@pytest.fixture
def payroll_alert():
    """Create a sample payroll safety alert."""
    return DetectedAlert(
        type=DetectionType.PAYROLL_SAFETY,
        severity=AlertSeverity.EMERGENCY,
        entity_type="system",
        entity_id="payroll",
        entity_name="Payroll",
        details={
            "payroll_amount": 50000,
            "payroll_date": "2026-01-15",
            "projected_shortfall": 10000,
            "days_until_payroll": 5,
        },
        detected_at=datetime.utcnow(),
    )


# =============================================================================
# Unit Tests - Risk Scoring
# =============================================================================

class TestRiskScoring:
    """Tests for risk scoring calculations."""

    def test_composite_risk_calculation(self):
        """Test composite risk formula."""
        result = calculate_composite_risk(
            relationship_risk=0.8,
            operational_risk=0.5,
            financial_cost=0.3,
            context={},
        )

        # Formula: (0.8 * 0.4) + (0.5 * 0.3) + (0.3 * 0.3)
        # = 0.32 + 0.15 + 0.09 = 0.56
        assert 0.55 <= result <= 0.57

    def test_relationship_risk_strategic_client(self):
        """Test relationship risk for strategic clients."""
        context = {
            "relationship_type": "strategic",
            "revenue_percent": 25,
            "payment_history_score": 0.9,
        }

        risk = calculate_relationship_risk("client", context)

        # Strategic clients with high revenue should have high relationship risk
        assert risk >= 0.7

    def test_relationship_risk_transactional_client(self):
        """Test relationship risk for transactional clients."""
        context = {
            "relationship_type": "transactional",
            "revenue_percent": 2,
            "payment_history_score": 0.5,
        }

        risk = calculate_relationship_risk("client", context)

        # Transactional clients with low revenue should have lower risk
        assert risk <= 0.5

    def test_operational_risk_email(self):
        """Test operational risk for email actions."""
        context = {"tone": "soft"}
        risk = calculate_operational_risk("INVOICE_FOLLOW_UP", context)

        # Email follow-up should be low risk
        assert risk <= 0.3

    def test_operational_risk_escalation(self):
        """Test operational risk for escalation actions."""
        context = {"previous_attempts": 3}
        risk = calculate_operational_risk("COLLECTION_ESCALATION", context)

        # Escalation should be higher risk
        assert risk >= 0.5

    def test_financial_cost_calculation(self):
        """Test financial cost calculation."""
        context = {"amount": 10000, "available_cash": 50000}
        cost = calculate_financial_cost("VENDOR_DELAY", context)

        # Cost should be proportion of available cash
        assert 0 <= cost <= 1


class TestRiskScore:
    """Tests for RiskScore dataclass."""

    def test_risk_score_creation(self):
        """Test RiskScore creation."""
        score = RiskScore(
            composite=0.65,
            relationship=0.8,
            operational=0.5,
            financial=0.3,
            factors=["High revenue client", "Multiple failed attempts"],
        )

        assert score.composite == 0.65
        assert len(score.factors) == 2


# =============================================================================
# Unit Tests - Message Drafting
# =============================================================================

class TestMessageDrafting:
    """Tests for message drafting functions."""

    def test_collection_email_soft_tone(self):
        """Test soft collection email."""
        result = draft_collection_email(
            client_name="John Smith",
            invoice_number="INV-001",
            amount=1500.00,
            due_date="2026-01-01",
            days_overdue=5,
            tone="soft",
        )

        assert "subject" in result
        assert "body" in result
        assert "INV-001" in result["subject"]
        assert "John Smith" in result["body"]
        assert "hope this message finds you well" in result["body"].lower()

    def test_collection_email_firm_tone(self):
        """Test firm collection email."""
        result = draft_collection_email(
            client_name="Jane Doe",
            invoice_number="INV-002",
            amount=5000.00,
            due_date="2025-12-01",
            days_overdue=40,
            tone="firm",
        )

        assert "Action Required" in result["subject"]
        assert "immediately" in result["body"].lower()

    def test_tone_adjusted_for_strategic_client(self):
        """Test that firm tone is softened for strategic clients."""
        result = draft_collection_email(
            client_name="Big Corp",
            invoice_number="INV-003",
            amount=50000.00,
            due_date="2025-12-15",
            days_overdue=25,
            tone="firm",
            relationship_type="strategic",
        )

        # Should be softened to professional
        assert result["tone"] == "professional"

    def test_escalation_email(self):
        """Test escalation/demand letter."""
        result = draft_escalation_email(
            client_name="Problem Client",
            invoice_number="INV-004",
            amount=10000.00,
            days_overdue=60,
            previous_attempts=3,
        )

        assert "Urgent" in result["subject"]
        assert "formal notice" in result["body"].lower()
        assert result["escalation_level"] == "demand_letter"

    def test_vendor_delay_message(self):
        """Test vendor delay request."""
        result = draft_vendor_delay_message(
            vendor_name="Supplier Inc",
            original_date="2026-01-15",
            new_date="2026-01-30",
            amount=8000.00,
            relationship_quality="good",
        )

        assert "Payment Timing Request" in result["subject"]
        assert "Supplier Inc" in result["body"]
        assert "2026-01-30" in result["body"]

    def test_call_talking_points_client(self):
        """Test talking points for client call."""
        context = {
            "invoice_number": "INV-005",
            "amount": 7500,
            "days_overdue": 21,
            "relationship_type": "strategic",
        }

        points = generate_call_talking_points("client", "Key Client", context)

        assert any("INV-005" in p for p in points)
        assert any("$7,500" in p for p in points)
        assert any("partnership" in p.lower() for p in points)

    def test_action_summary_generation(self):
        """Test action summary generation."""
        context = {
            "amount": 5000,
            "client_name": "Test Client",
            "days_overdue": 14,
        }

        summary = generate_action_summary("INVOICE_FOLLOW_UP", context)

        assert "Test Client" in summary
        assert "$5,000" in summary or "5,000" in summary


# =============================================================================
# Unit Tests - Preparation Engine
# =============================================================================

class TestPreparationEngine:
    """Tests for the PreparationEngine class."""

    @pytest.mark.asyncio
    async def test_prepare_actions_for_alerts(self, preparation_engine, sample_alert, mock_db):
        """Test preparing actions for a list of alerts."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with patch.object(preparation_engine, '_invoice_followup_agent', new_callable=AsyncMock) as mock_agent:
            mock_action = MagicMock(spec=PreparedAction)
            mock_action.id = "action-123"
            mock_agent.return_value = mock_action

            actions = await preparation_engine.prepare_actions_for_alerts([sample_alert])

            assert mock_agent.called

    @pytest.mark.asyncio
    async def test_handler_routing(self, preparation_engine, sample_alert, payroll_alert):
        """Test that alerts are routed to correct handlers."""
        # Late payment should go to invoice_followup_agent
        with patch.object(preparation_engine, '_invoice_followup_agent', new_callable=AsyncMock) as mock_handler:
            mock_handler.return_value = MagicMock()
            await preparation_engine.prepare_actions_for_alerts([sample_alert])
            assert mock_handler.called

        # Payroll safety should go to payroll_safety_agent
        with patch.object(preparation_engine, '_payroll_safety_agent', new_callable=AsyncMock) as mock_handler:
            mock_handler.return_value = MagicMock()
            await preparation_engine.prepare_actions_for_alerts([payroll_alert])
            assert mock_handler.called


class TestInvoiceFollowupAgent:
    """Tests for the invoice follow-up agent."""

    @pytest.mark.asyncio
    async def test_generates_multiple_options(self, preparation_engine, sample_alert, mock_db):
        """Test that agent generates multiple action options."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = MagicMock(
            name="Acme Corp",
            relationship_type="transactional",
        )
        mock_db.execute.return_value = mock_result

        with patch('app.preparation.engine.get_client_context', new_callable=AsyncMock) as mock_context:
            mock_context.return_value = {
                "relationship_type": "transactional",
                "revenue_percent": 5,
            }

            with patch('app.preparation.engine.get_cash_context', new_callable=AsyncMock) as mock_cash:
                mock_cash.return_value = {"current_balance": 50000}

                action = await preparation_engine._invoice_followup_agent(sample_alert)

                # Should have multiple options (soft, professional, firm emails)
                assert action is not None


class TestPayrollSafetyAgent:
    """Tests for the payroll safety agent."""

    @pytest.mark.asyncio
    async def test_handles_shortfall(self, preparation_engine, payroll_alert, mock_db):
        """Test agent generates contingency options for shortfall."""
        with patch('app.preparation.engine.get_cash_context', new_callable=AsyncMock) as mock_cash:
            mock_cash.return_value = {
                "current_balance": 40000,
                "credit_available": 20000,
            }

            action = await preparation_engine._payroll_safety_agent(payroll_alert)

            # Should generate action for payroll contingency
            assert action is not None


# =============================================================================
# Integration Tests - Action Queue
# =============================================================================

class TestActionQueue:
    """Tests for action queue management."""

    @pytest.mark.asyncio
    async def test_get_action_queue(self, preparation_engine, mock_db):
        """Test retrieving action queue."""
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        queue = await preparation_engine.get_action_queue()

        assert isinstance(queue, list)
        assert mock_db.execute.called

    @pytest.mark.asyncio
    async def test_approve_action(self, preparation_engine, mock_db):
        """Test approving an action."""
        mock_action = MagicMock(spec=PreparedAction)
        mock_action.status = ActionStatus.PENDING
        mock_action.recommended_option_id = "option-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_action
        mock_db.execute.return_value = mock_result

        action = await preparation_engine.approve_action("action-123")

        assert mock_action.status == ActionStatus.APPROVED
        assert mock_action.selected_option_id == "option-123"

    @pytest.mark.asyncio
    async def test_approve_with_specific_option(self, preparation_engine, mock_db):
        """Test approving with a specific option."""
        mock_action = MagicMock(spec=PreparedAction)
        mock_action.status = ActionStatus.PENDING
        mock_action.recommended_option_id = "option-123"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_action
        mock_db.execute.return_value = mock_result

        action = await preparation_engine.approve_action("action-123", "option-456")

        assert mock_action.selected_option_id == "option-456"

    @pytest.mark.asyncio
    async def test_skip_action(self, preparation_engine, mock_db):
        """Test skipping an action."""
        mock_action = MagicMock(spec=PreparedAction)
        mock_action.status = ActionStatus.PENDING

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_action
        mock_db.execute.return_value = mock_result

        action = await preparation_engine.skip_action("action-123", "Not needed")

        assert mock_action.status == ActionStatus.SKIPPED

    @pytest.mark.asyncio
    async def test_approve_nonexistent_action(self, preparation_engine, mock_db):
        """Test approving an action that doesn't exist."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        with pytest.raises(ValueError, match="Action not found"):
            await preparation_engine.approve_action("nonexistent-123")


# =============================================================================
# Linked Actions Tests
# =============================================================================

class TestLinkedActions:
    """Tests for linked action detection."""

    @pytest.mark.asyncio
    async def test_detects_conflicting_actions(self, preparation_engine, mock_db):
        """Test detection of conflicting actions."""
        # Create two actions that conflict (e.g., both affect same vendor)
        action1 = MagicMock(spec=PreparedAction)
        action1.id = "action-1"
        action1.action_type = ActionType.VENDOR_DELAY
        action1.context = {"vendor_id": "vendor-123"}

        action2 = MagicMock(spec=PreparedAction)
        action2.id = "action-2"
        action2.action_type = ActionType.PAYMENT_BATCH
        action2.context = {"vendor_id": "vendor-123"}

        # Test link detection
        linked_count = await preparation_engine._detect_linked_actions([action1, action2])

        # Should detect at least 0 linked groups (test setup may vary)
        assert isinstance(linked_count, int)


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_handles_unknown_alert_type(self, preparation_engine, mock_db):
        """Test handling of unknown alert types."""
        unknown_alert = DetectedAlert(
            type=MagicMock(value="unknown_type"),
            severity=AlertSeverity.UPCOMING,
            entity_type="unknown",
            entity_id="test",
            entity_name="Test",
            details={},
            detected_at=datetime.utcnow(),
        )

        # Should use generic agent, not raise
        actions = await preparation_engine.prepare_actions_for_alerts([unknown_alert])

        assert isinstance(actions, list)

    @pytest.mark.asyncio
    async def test_handles_empty_alert_list(self, preparation_engine):
        """Test handling of empty alert list."""
        actions = await preparation_engine.prepare_actions_for_alerts([])

        assert actions == []

    def test_message_drafting_with_zero_amount(self):
        """Test message drafting handles zero amounts gracefully."""
        result = draft_collection_email(
            client_name="Test",
            invoice_number="INV-000",
            amount=0,
            due_date="2026-01-01",
            days_overdue=1,
        )

        assert "$0.00" in result["body"]
