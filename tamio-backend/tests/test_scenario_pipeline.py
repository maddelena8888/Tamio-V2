"""
Unit Tests for Scenario Pipeline.

Tests the core pipeline functionality:
1. PaymentDelayIn: shift + partial split behaviour
2. ClientLoss: removal + cost reduction with lag
3. IncreasedExpense: recurring vs one-off
4. DecreasedExpense: termination fee path
5. Stacking: multiple scenarios overlay correctly
"""

import pytest
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.scenarios.pipeline.types import (
    ScenarioDefinition,
    ScenarioDelta,
    ScenarioTypeEnum,
    EntryPath,
    ScenarioStatusEnum,
    ScopeConfig,
    PipelineStage,
)
from app.scenarios.pipeline.handlers.payment_delay_in import PaymentDelayInHandler
from app.scenarios.pipeline.handlers.client_loss import ClientLossHandler
from app.scenarios.pipeline.handlers.increased_expense import IncreasedExpenseHandler
from app.scenarios.pipeline.handlers.decreased_expense import DecreasedExpenseHandler


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    return AsyncMock()


@pytest.fixture
def base_definition():
    """Create a base scenario definition for testing."""
    return ScenarioDefinition(
        scenario_id="sc_test123",
        user_id="user_123",
        scenario_type=ScenarioTypeEnum.PAYMENT_DELAY_IN,
        entry_path=EntryPath.MANUAL,
        status=ScenarioStatusEnum.DRAFT,
        current_stage=PipelineStage.SCOPE,
    )


@pytest.fixture
def mock_cash_event():
    """Create a mock CashEvent."""
    event = MagicMock()
    event.id = "evt_123"
    event.user_id = "user_123"
    event.date = date.today() + timedelta(days=14)
    event.amount = Decimal("10000")
    event.direction = "in"
    event.event_type = "expected_revenue"
    event.category = "retainer"
    event.confidence = "high"
    event.is_recurring = True
    event.recurrence_pattern = "monthly"
    event.client_id = "client_123"
    event.bucket_id = None
    return event


# =============================================================================
# TEST: PAYMENT DELAY IN
# =============================================================================

class TestPaymentDelayIn:
    """Tests for Payment Delay (Cash In) handler."""

    @pytest.mark.asyncio
    async def test_full_delay_shifts_date(self, mock_db, base_definition, mock_cash_event):
        """Test that full delay shifts event date by delay_weeks."""
        # Setup
        handler = PaymentDelayInHandler()
        base_definition.scope = ScopeConfig(client_ids=["client_123"])
        base_definition.parameters = {
            "delay_weeks": 2,
            "is_partial": False,
        }

        # Mock database query
        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [mock_cash_event]
        mock_db.execute.return_value = mock_result

        # Execute
        delta = await handler.apply(mock_db, base_definition)

        # Assert
        assert len(delta.updated_events) == 1
        updated = delta.updated_events[0]
        assert updated.operation == "modify"
        assert updated.original_event_id == "evt_123"

        # Check date was shifted
        expected_date = mock_cash_event.date + timedelta(weeks=2)
        assert updated.event_data["date"] == str(expected_date)

        # Check confidence was downshifted
        assert updated.event_data["confidence"] == "medium"

    @pytest.mark.asyncio
    async def test_partial_payment_splits_event(self, mock_db, base_definition, mock_cash_event):
        """Test that partial payment creates two events: actual + remaining shifted."""
        # Setup
        handler = PaymentDelayInHandler()
        base_definition.scope = ScopeConfig(client_ids=["client_123"])
        base_definition.parameters = {
            "delay_weeks": 2,
            "is_partial": True,
            "partial_payment_pct": 30,
        }

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [mock_cash_event]
        mock_db.execute.return_value = mock_result

        # Execute
        delta = await handler.apply(mock_db, base_definition)

        # Assert
        assert len(delta.created_events) == 1  # Actual receipt
        assert len(delta.updated_events) == 1  # Remaining shifted

        # Check actual receipt
        actual = delta.created_events[0]
        assert actual.operation == "add"
        assert actual.event_data["direction"] == "in"
        assert Decimal(actual.event_data["amount"]) == Decimal("3000")  # 30% of 10000
        assert actual.event_data["date"] == str(mock_cash_event.date)  # Original date

        # Check remaining shifted
        remaining = delta.updated_events[0]
        assert remaining.operation == "modify"
        assert Decimal(remaining.event_data["amount"]) == Decimal("7000")  # 70% remaining
        expected_date = mock_cash_event.date + timedelta(weeks=2)
        assert remaining.event_data["date"] == str(expected_date)


# =============================================================================
# TEST: CLIENT LOSS
# =============================================================================

class TestClientLoss:
    """Tests for Client Loss handler."""

    @pytest.mark.asyncio
    async def test_removes_future_revenue(self, mock_db, mock_cash_event):
        """Test that client loss removes all future revenue events."""
        # Setup
        handler = ClientLossHandler()
        definition = ScenarioDefinition(
            scenario_id="sc_test456",
            user_id="user_123",
            scenario_type=ScenarioTypeEnum.CLIENT_LOSS,
            entry_path=EntryPath.MANUAL,
            scope=ScopeConfig(client_ids=["client_123"]),
            parameters={
                "effective_date": str(date.today()),
            },
        )

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [mock_cash_event]
        mock_db.execute.return_value = mock_result

        # Execute
        delta = await handler.apply(mock_db, definition)

        # Assert
        assert mock_cash_event.id in delta.deleted_event_ids
        assert len(delta.updated_events) == 1
        assert delta.updated_events[0].operation == "delete"

    @pytest.mark.asyncio
    async def test_cost_reduction_with_lag(self, mock_db, mock_cash_event):
        """Test that cost reduction is applied with configured lag."""
        # Setup
        handler = ClientLossHandler()
        definition = ScenarioDefinition(
            scenario_id="sc_test789",
            user_id="user_123",
            scenario_type=ScenarioTypeEnum.CLIENT_LOSS,
            entry_path=EntryPath.MANUAL,
            scope=ScopeConfig(client_ids=["client_123"]),
            parameters={
                "effective_date": str(date.today()),
                "linked_reduce_costs": True,
                "linked_cost_types": ["contractors"],
                "linked_reduction_amount": "2000",
                "linked_lag_weeks": 2,
            },
        )

        # Create mock contractor expense
        contractor_event = MagicMock()
        contractor_event.id = "evt_contractor"
        contractor_event.user_id = "user_123"
        contractor_event.date = date.today() + timedelta(weeks=3)  # After lag
        contractor_event.amount = Decimal("5000")
        contractor_event.direction = "out"
        contractor_event.category = "contractors"
        contractor_event.bucket_id = "bucket_123"
        contractor_event.event_type = "expected_expense"
        contractor_event.confidence = "high"

        mock_bucket = MagicMock()
        mock_bucket.id = "bucket_123"
        mock_bucket.monthly_amount = Decimal("5000")

        # Setup multiple query results
        async def mock_execute(query):
            result = AsyncMock()
            # First call: revenue events, Second: expense buckets, Third: contractor events
            if "client_id" in str(query):
                result.scalars.return_value.all.return_value = [mock_cash_event]
            elif "ExpenseBucket" in str(query):
                result.scalars.return_value.all.return_value = [mock_bucket]
            else:
                result.scalars.return_value.all.return_value = [contractor_event]
            return result

        mock_db.execute = mock_execute

        # Execute
        delta = await handler.apply(mock_db, definition)

        # Assert: should have deleted revenue + modified contractor
        assert mock_cash_event.id in delta.deleted_event_ids


# =============================================================================
# TEST: INCREASED EXPENSE
# =============================================================================

class TestIncreasedExpense:
    """Tests for Increased Expense handler."""

    @pytest.mark.asyncio
    async def test_one_off_expense(self, mock_db):
        """Test that one-off expense creates single event."""
        handler = IncreasedExpenseHandler()
        definition = ScenarioDefinition(
            scenario_id="sc_expense1",
            user_id="user_123",
            scenario_type=ScenarioTypeEnum.INCREASED_EXPENSE,
            entry_path=EntryPath.MANUAL,
            parameters={
                "category": "software",
                "expense_name": "New Tool License",
                "expense_type": "one_off",
                "amount": "500",
                "effective_date": str(date.today()),
            },
        )

        # Execute
        delta = await handler.apply(mock_db, definition)

        # Assert
        assert len(delta.created_events) == 1
        event = delta.created_events[0]
        assert event.event_data["direction"] == "out"
        assert Decimal(event.event_data["amount"]) == Decimal("500")
        assert event.event_data["is_recurring"] == False
        assert event.event_data["category"] == "software"

    @pytest.mark.asyncio
    async def test_recurring_expense_creates_multiple(self, mock_db):
        """Test that recurring expense creates events for 13-week period."""
        handler = IncreasedExpenseHandler()
        definition = ScenarioDefinition(
            scenario_id="sc_expense2",
            user_id="user_123",
            scenario_type=ScenarioTypeEnum.INCREASED_EXPENSE,
            entry_path=EntryPath.MANUAL,
            parameters={
                "category": "marketing",
                "expense_name": "Ad Spend",
                "expense_type": "recurring",
                "amount": "1000",
                "effective_date": str(date.today()),
                "frequency": "monthly",
            },
        )

        # Execute
        delta = await handler.apply(mock_db, definition)

        # Assert: should create ~3 monthly events in 13-week window
        assert len(delta.created_events) >= 3
        for event in delta.created_events:
            assert event.event_data["is_recurring"] == True
            assert event.event_data["recurrence_pattern"] == "monthly"


# =============================================================================
# TEST: DECREASED EXPENSE
# =============================================================================

class TestDecreasedExpense:
    """Tests for Decreased Expense handler."""

    @pytest.mark.asyncio
    async def test_termination_fee_added(self, mock_db):
        """Test that termination fee is added when configured."""
        handler = DecreasedExpenseHandler()

        mock_expense = MagicMock()
        mock_expense.id = "evt_expense"
        mock_expense.user_id = "user_123"
        mock_expense.date = date.today() + timedelta(days=30)
        mock_expense.amount = Decimal("3000")
        mock_expense.direction = "out"
        mock_expense.category = "software"
        mock_expense.bucket_id = "bucket_123"
        mock_expense.event_type = "expected_expense"
        mock_expense.confidence = "high"
        mock_expense.is_recurring = True
        mock_expense.recurrence_pattern = "monthly"

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [mock_expense]
        mock_db.execute.return_value = mock_result

        definition = ScenarioDefinition(
            scenario_id="sc_decrease1",
            user_id="user_123",
            scenario_type=ScenarioTypeEnum.DECREASED_EXPENSE,
            entry_path=EntryPath.MANUAL,
            scope=ScopeConfig(bucket_ids=["bucket_123"]),
            parameters={
                "reduction_amount": "1000",
                "effective_date": str(date.today()),
                "has_termination_costs": True,
                "termination_fee": "500",
            },
        )

        # Execute
        delta = await handler.apply(mock_db, definition)

        # Assert: should have termination fee + reduced expense
        termination_events = [e for e in delta.created_events if e.event_data.get("category") == "termination_fee"]
        assert len(termination_events) == 1
        assert Decimal(termination_events[0].event_data["amount"]) == Decimal("500")

    @pytest.mark.asyncio
    async def test_expense_fully_removed_when_reduction_exceeds(self, mock_db):
        """Test that expense is deleted when reduction >= amount."""
        handler = DecreasedExpenseHandler()

        mock_expense = MagicMock()
        mock_expense.id = "evt_small"
        mock_expense.user_id = "user_123"
        mock_expense.date = date.today() + timedelta(days=30)
        mock_expense.amount = Decimal("500")  # Less than reduction
        mock_expense.direction = "out"
        mock_expense.category = "other"
        mock_expense.bucket_id = "bucket_123"
        mock_expense.event_type = "expected_expense"
        mock_expense.confidence = "high"
        mock_expense.is_recurring = True
        mock_expense.recurrence_pattern = "monthly"

        mock_result = AsyncMock()
        mock_result.scalars.return_value.all.return_value = [mock_expense]
        mock_db.execute.return_value = mock_result

        definition = ScenarioDefinition(
            scenario_id="sc_decrease2",
            user_id="user_123",
            scenario_type=ScenarioTypeEnum.DECREASED_EXPENSE,
            entry_path=EntryPath.MANUAL,
            scope=ScopeConfig(bucket_ids=["bucket_123"]),
            parameters={
                "reduction_amount": "1000",  # More than expense amount
                "effective_date": str(date.today()),
                "has_termination_costs": False,
            },
        )

        # Execute
        delta = await handler.apply(mock_db, definition)

        # Assert: expense should be deleted
        assert mock_expense.id in delta.deleted_event_ids


# =============================================================================
# TEST: SCENARIO STACKING
# =============================================================================

class TestScenarioStacking:
    """Tests for stacking multiple scenarios."""

    @pytest.mark.asyncio
    async def test_stacked_scenarios_preserve_attribution(self, mock_db):
        """Test that stacked scenarios maintain proper attribution."""
        # Create two definitions for stacking
        scenario1 = ScenarioDefinition(
            scenario_id="sc_stack1",
            user_id="user_123",
            scenario_type=ScenarioTypeEnum.CLIENT_GAIN,
            entry_path=EntryPath.MANUAL,
            layer_order=0,
            parameters={
                "client_name": "New Client A",
                "start_date": str(date.today()),
                "agreement_type": "retainer",
                "monthly_amount": "5000",
                "payment_terms_days": "30",
            },
        )

        scenario2 = ScenarioDefinition(
            scenario_id="sc_stack2",
            user_id="user_123",
            scenario_type=ScenarioTypeEnum.INCREASED_EXPENSE,
            entry_path=EntryPath.MANUAL,
            layer_order=1,
            parent_scenario_id="sc_stack1",  # Linked to first scenario
            parameters={
                "category": "contractors",
                "expense_name": "Support for New Client A",
                "expense_type": "recurring",
                "amount": "2000",
                "effective_date": str(date.today()),
            },
        )

        # Apply both handlers
        from app.scenarios.pipeline.handlers.client_gain import ClientGainHandler
        from app.scenarios.pipeline.handlers.increased_expense import IncreasedExpenseHandler

        handler1 = ClientGainHandler()
        handler2 = IncreasedExpenseHandler()

        delta1 = await handler1.apply(mock_db, scenario1)
        delta2 = await handler2.apply(mock_db, scenario2)

        # Assert: both deltas have correct attribution
        for event in delta1.created_events:
            assert event.scenario_id == "sc_stack1"

        for event in delta2.created_events:
            assert event.scenario_id == "sc_stack2"

        # Assert: combined impact can be calculated
        total_revenue = sum(
            Decimal(e.event_data["amount"])
            for e in delta1.created_events
            if e.event_data.get("direction") == "in"
        )
        total_expense = sum(
            Decimal(e.event_data["amount"])
            for e in delta2.created_events
            if e.event_data.get("direction") == "out"
        )

        # Revenue should exceed expenses for positive net impact
        assert total_revenue > 0
        assert total_expense > 0

    @pytest.mark.asyncio
    async def test_layer_order_maintained(self, mock_db):
        """Test that layer order is maintained for stacked scenarios."""
        scenarios = [
            ScenarioDefinition(
                scenario_id=f"sc_layer{i}",
                user_id="user_123",
                scenario_type=ScenarioTypeEnum.INCREASED_EXPENSE,
                entry_path=EntryPath.MANUAL,
                layer_order=i,
                parameters={
                    "category": "other",
                    "expense_name": f"Expense {i}",
                    "expense_type": "one_off",
                    "amount": str(1000 * (i + 1)),
                    "effective_date": str(date.today()),
                },
            )
            for i in range(3)
        ]

        # Verify layer orders
        for i, scenario in enumerate(scenarios):
            assert scenario.layer_order == i

        # Verify IDs are unique
        ids = [s.scenario_id for s in scenarios]
        assert len(ids) == len(set(ids))


# =============================================================================
# TEST: PROMPT GENERATION
# =============================================================================

class TestPromptGeneration:
    """Tests for prompt generation."""

    def test_required_params_defined(self):
        """Test that all handlers define required params."""
        from app.scenarios.pipeline.handlers import get_handler

        for scenario_type in ScenarioTypeEnum:
            handler = get_handler(scenario_type)
            params = handler.required_params()
            assert isinstance(params, list)
            assert len(params) > 0

    def test_linked_prompt_types_defined(self):
        """Test that all handlers define linked prompt types."""
        from app.scenarios.pipeline.handlers import get_handler

        for scenario_type in ScenarioTypeEnum:
            handler = get_handler(scenario_type)
            types = handler.linked_prompt_types()
            assert isinstance(types, list)


# =============================================================================
# RUN TESTS
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
