"""
Tests for TAMI operational tools — check_payroll_safety.

Tests cover:
- Happy path (payroll safely covered)
- At-risk (medium-confidence needed)
- Shortfall (even medium can't cover)
- No payroll bucket (graceful handling)
- Result structure (JSON-serializable, success key)
- Layer 2 behavioral downgrade (overdue client → HIGH reclassified to MEDIUM)
- No downgrade for on-time clients
"""

import pytest
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.tami.tools import _check_payroll_safety, _compute_payroll_coverage, dispatch_tool


# =============================================================================
# Helpers
# =============================================================================

def _make_payroll_bucket(
    user_id: str = "test_user",
    monthly_amount: Decimal = Decimal("170000"),
    frequency: str = "bi_weekly",
    employee_count: int = 28,
):
    """Create a mock ExpenseBucket for payroll."""
    bucket = MagicMock()
    bucket.user_id = user_id
    bucket.category = "payroll"
    bucket.monthly_amount = monthly_amount
    bucket.frequency = frequency
    bucket.employee_count = employee_count
    bucket.name = "Payroll"
    return bucket


def _make_forecast_week(
    week_number: int,
    starting_balance: str = "487000.00",
    cash_in: str = "120000.00",
    cash_out: str = "95000.00",
    high_in: str = "80000.00",
    medium_in: str = "30000.00",
    low_in: str = "10000.00",
    events: list = None,
):
    """Create a mock forecast week dict."""
    ending = str(Decimal(starting_balance) + Decimal(cash_in) - Decimal(cash_out))
    week_start = str(date.today() + timedelta(weeks=week_number))
    return {
        "week_number": week_number,
        "week_start": week_start,
        "week_end": str(date.today() + timedelta(weeks=week_number, days=6)),
        "starting_balance": starting_balance,
        "cash_in": cash_in,
        "cash_out": cash_out,
        "net_change": str(Decimal(cash_in) - Decimal(cash_out)),
        "ending_balance": ending,
        "confidence_breakdown": {
            "cash_in": {
                "high": high_in,
                "medium": medium_in,
                "low": low_in,
            },
            "cash_out": {
                "high": cash_out,
                "medium": "0",
                "low": "0",
            },
        },
        "events": events or [],
    }


def _make_forecast(weeks_data: list, starting_cash: str = "487000.00"):
    """Build a full forecast dict from week data list."""
    return {
        "starting_cash": starting_cash,
        "forecast_start_date": str(date.today()),
        "weeks": weeks_data,
        "summary": {
            "lowest_cash_week": 1,
            "lowest_cash_amount": starting_cash,
            "total_cash_in": "0",
            "total_cash_out": "0",
            "runway_weeks": 13,
        },
        "confidence": {
            "overall_score": "0.85",
            "overall_level": "medium",
            "overall_percentage": 85,
            "breakdown": {},
            "improvement_suggestions": [],
        },
    }


def _setup_db_mock(
    payroll_buckets=None,
    overdue_client_ids=None,
    overdue_details=None,
    obligation_mappings=None,
):
    """
    Build a mock db session that returns the right data for each query.

    The mock tracks query order and returns appropriate results based on
    what _compute_payroll_coverage queries in sequence:
    1. ExpenseBucket (payroll)
    2. Overdue client_ids (distinct)
    3. Overdue details (amount, due_date, client_id, name) — only if overdue_client_ids
    4. Obligation-to-client mapping — only if overdue_client_ids
    """
    db = AsyncMock()
    call_count = {"n": 0}

    async def mock_execute(query):
        call_count["n"] += 1
        n = call_count["n"]

        result = MagicMock()

        if n == 1:
            # ExpenseBucket query
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = payroll_buckets or []
            result.scalars.return_value = scalars_mock
        elif n == 2:
            # Overdue client_ids query
            if overdue_client_ids:
                result.all.return_value = [(cid,) for cid in overdue_client_ids]
            else:
                result.all.return_value = []
        elif n == 3:
            # Overdue details query
            if overdue_details:
                result.all.return_value = overdue_details
            else:
                result.all.return_value = []
        elif n == 4:
            # Obligation-to-client mapping
            if obligation_mappings:
                rows = [MagicMock(id=obl_id, client_id=cid) for obl_id, cid in obligation_mappings]
                result.all.return_value = rows
            else:
                result.all.return_value = []

        return result

    db.execute = mock_execute
    return db


# =============================================================================
# Tests — check_payroll_safety
# =============================================================================

class TestCheckPayrollSafety:
    """Tests for the check_payroll_safety tool."""

    @pytest.mark.asyncio
    async def test_happy_path_safe(self):
        """Payroll safely covered when high-conf inflows + balance exceed outflows."""
        payroll = _make_payroll_bucket()
        # Week 0 (current) + 4 forecast weeks — all well-covered
        weeks = [
            _make_forecast_week(0, starting_balance="487000.00"),
        ]
        for i in range(1, 5):
            weeks.append(_make_forecast_week(
                i,
                starting_balance="487000.00",
                cash_out="95000.00",
                high_in="120000.00",
                medium_in="30000.00",
            ))

        forecast = _make_forecast(weeks)
        db = _setup_db_mock(payroll_buckets=[payroll])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast):
            result = await _check_payroll_safety(db, "test_user", {})

        assert result["success"] is True
        assert result["overall_status"] == "safe"
        assert result["first_risk_week"] is None
        assert result["has_payroll"] is True
        for week in result["coverage_by_week"]:
            assert week["definitely_covered"] is True
            assert week["probably_covered"] is True

    @pytest.mark.asyncio
    async def test_at_risk_medium_conf_needed(self):
        """At risk when high-conf alone is insufficient but medium closes the gap."""
        payroll = _make_payroll_bucket()
        weeks = [_make_forecast_week(0)]
        # Week 3: high-conf inflows too low, but medium helps
        for i in range(1, 5):
            if i == 3:
                weeks.append(_make_forecast_week(
                    i,
                    starting_balance="50000.00",
                    cash_out="95000.00",
                    high_in="30000.00",     # 50K + 30K - 95K = -15K → not definitely covered
                    medium_in="40000.00",   # -15K + 40K = 25K → probably covered
                ))
            else:
                weeks.append(_make_forecast_week(
                    i,
                    starting_balance="487000.00",
                    cash_out="95000.00",
                    high_in="120000.00",
                ))

        forecast = _make_forecast(weeks)
        db = _setup_db_mock(payroll_buckets=[payroll])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast):
            result = await _check_payroll_safety(db, "test_user", {})

        assert result["success"] is True
        assert result["overall_status"] == "at_risk"
        assert result["first_risk_week"] == 3
        # Week 3 specifically
        week3 = result["coverage_by_week"][2]  # 0-indexed
        assert week3["definitely_covered"] is False
        assert week3["probably_covered"] is True

    @pytest.mark.asyncio
    async def test_shortfall(self):
        """Shortfall when even medium-conf can't cover outflows."""
        payroll = _make_payroll_bucket()
        weeks = [_make_forecast_week(0)]
        # Week 2: massive shortfall
        for i in range(1, 5):
            if i == 2:
                weeks.append(_make_forecast_week(
                    i,
                    starting_balance="10000.00",
                    cash_out="95000.00",
                    high_in="5000.00",      # 10K + 5K - 95K = -80K
                    medium_in="20000.00",   # -80K + 20K = -60K → still negative
                ))
            else:
                weeks.append(_make_forecast_week(
                    i,
                    starting_balance="487000.00",
                    cash_out="95000.00",
                    high_in="120000.00",
                ))

        forecast = _make_forecast(weeks)
        db = _setup_db_mock(payroll_buckets=[payroll])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast):
            result = await _check_payroll_safety(db, "test_user", {})

        assert result["success"] is True
        assert result["overall_status"] == "shortfall"
        assert result["first_risk_week"] == 2
        week2 = result["coverage_by_week"][1]
        assert week2["definitely_covered"] is False
        assert week2["probably_covered"] is False

    @pytest.mark.asyncio
    async def test_no_payroll_bucket(self):
        """Graceful message when no payroll expense bucket exists."""
        db = _setup_db_mock(payroll_buckets=[])

        result = await _check_payroll_safety(db, "test_user", {})

        assert result["success"] is True
        assert result["has_payroll"] is False
        assert "No payroll expense bucket found" in result["message"]

    @pytest.mark.asyncio
    async def test_result_structure_json_serializable(self):
        """Tool result must be JSON-serializable with success key."""
        payroll = _make_payroll_bucket()
        weeks = [_make_forecast_week(0)]
        for i in range(1, 5):
            weeks.append(_make_forecast_week(i, starting_balance="487000.00"))
        forecast = _make_forecast(weeks)
        db = _setup_db_mock(payroll_buckets=[payroll])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast):
            result = await _check_payroll_safety(db, "test_user", {})

        # Must be JSON-serializable
        serialized = json.dumps(result)
        assert serialized is not None

        # Required keys
        assert "success" in result
        assert "message" in result
        assert "payroll_summary" in result
        assert "coverage_by_week" in result
        assert "overall_status" in result

        # Payroll summary structure
        summary = result["payroll_summary"]
        assert "frequency" in summary
        assert "per_period_amount" in summary
        assert "employee_count" in summary
        assert "monthly_total" in summary

    @pytest.mark.asyncio
    async def test_layer2_overdue_client_downgraded(self):
        """HIGH-conf inflows from clients with overdue invoices get reclassified to MEDIUM."""
        payroll = _make_payroll_bucket()
        overdue_client_id = "client_retailco"
        overdue_amount = Decimal("52500")
        overdue_due_date = date.today() - timedelta(days=14)

        # Event from overdue client in week 1
        events_week1 = [
            {
                "id": "evt_1",
                "date": str(date.today() + timedelta(days=7)),
                "amount": "37500.00",
                "direction": "in",
                "event_type": "expected_revenue",
                "category": "revenue",
                "confidence": "high",
                "confidence_reason": "Linked to Xero with repeating invoice",
                "source_id": overdue_client_id,
                "source_name": "RetailCo Rebrand",
                "source_type": "client",
            },
            {
                "id": "evt_2",
                "date": str(date.today() + timedelta(days=8)),
                "amount": "50000.00",
                "direction": "in",
                "event_type": "expected_revenue",
                "category": "revenue",
                "confidence": "high",
                "confidence_reason": "Linked to Xero",
                "source_id": "client_techventures",
                "source_name": "TechVentures Inc",
                "source_type": "client",
            },
        ]

        weeks = [_make_forecast_week(0)]
        weeks.append(_make_forecast_week(
            1,
            starting_balance="100000.00",
            cash_out="95000.00",
            high_in="87500.00",   # 37500 (RetailCo) + 50000 (TechVentures)
            medium_in="20000.00",
            events=events_week1,
        ))
        for i in range(2, 5):
            weeks.append(_make_forecast_week(i, starting_balance="487000.00"))

        forecast = _make_forecast(weeks)

        db = _setup_db_mock(
            payroll_buckets=[payroll],
            overdue_client_ids=[overdue_client_id],
            overdue_details=[
                (overdue_amount, overdue_due_date, overdue_client_id, "RetailCo Rebrand"),
            ],
            obligation_mappings=[("obl_retailco_1", overdue_client_id)],
        )

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast):
            result = await _check_payroll_safety(db, "test_user", {})

        assert result["success"] is True

        # Week 1 should have the downgrade
        week1 = result["coverage_by_week"][0]

        # RetailCo's $37,500 should have moved from high to medium
        # Original: high=87500, medium=20000
        # After downgrade: high=50000, medium=57500
        assert Decimal(week1["high_conf_inflows"]) == Decimal("50000.00")
        assert Decimal(week1["medium_conf_inflows"]) == Decimal("57500.00")

        # downgraded_clients list should explain why
        assert "downgraded_clients" in week1
        assert len(week1["downgraded_clients"]) == 1
        downgraded = week1["downgraded_clients"][0]
        assert downgraded["client_name"] == "RetailCo Rebrand"
        assert "52,500" in downgraded["reason"]
        assert "14 days" in downgraded["reason"]

    @pytest.mark.asyncio
    async def test_no_downgrade_for_on_time_clients(self):
        """HIGH-conf inflows from clients without overdue invoices remain HIGH."""
        payroll = _make_payroll_bucket()

        events_week1 = [
            {
                "id": "evt_1",
                "date": str(date.today() + timedelta(days=7)),
                "amount": "50000.00",
                "direction": "in",
                "event_type": "expected_revenue",
                "category": "revenue",
                "confidence": "high",
                "confidence_reason": "Linked to Xero",
                "source_id": "client_techventures",
                "source_name": "TechVentures Inc",
                "source_type": "client",
            },
        ]

        weeks = [_make_forecast_week(0)]
        weeks.append(_make_forecast_week(
            1,
            starting_balance="487000.00",
            cash_out="95000.00",
            high_in="50000.00",
            medium_in="20000.00",
            events=events_week1,
        ))
        for i in range(2, 5):
            weeks.append(_make_forecast_week(i, starting_balance="487000.00"))

        forecast = _make_forecast(weeks)

        # No overdue clients
        db = _setup_db_mock(payroll_buckets=[payroll])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast):
            result = await _check_payroll_safety(db, "test_user", {})

        assert result["success"] is True
        week1 = result["coverage_by_week"][0]

        # HIGH should be unchanged — no downgrade
        assert Decimal(week1["high_conf_inflows"]) == Decimal("50000.00")
        assert Decimal(week1["medium_conf_inflows"]) == Decimal("20000.00")
        assert "downgraded_clients" not in week1


class TestCheckPayrollSafetyWeeksAhead:
    """Tests for weeks_ahead parameter handling."""

    @pytest.mark.asyncio
    async def test_custom_weeks_ahead(self):
        """Respects weeks_ahead parameter."""
        payroll = _make_payroll_bucket()
        weeks = [_make_forecast_week(0)]
        for i in range(1, 14):
            weeks.append(_make_forecast_week(i, starting_balance="487000.00"))
        forecast = _make_forecast(weeks)
        db = _setup_db_mock(payroll_buckets=[payroll])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast):
            result = await _check_payroll_safety(db, "test_user", {"weeks_ahead": 8})

        assert len(result["coverage_by_week"]) == 8

    @pytest.mark.asyncio
    async def test_weeks_ahead_capped_at_13(self):
        """weeks_ahead is capped at 13 even if larger value provided."""
        payroll = _make_payroll_bucket()
        weeks = [_make_forecast_week(0)]
        for i in range(1, 14):
            weeks.append(_make_forecast_week(i, starting_balance="487000.00"))
        forecast = _make_forecast(weeks)
        db = _setup_db_mock(payroll_buckets=[payroll])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast):
            result = await _check_payroll_safety(db, "test_user", {"weeks_ahead": 52})

        assert len(result["coverage_by_week"]) == 13


class TestDispatchRouting:
    """Test that check_payroll_safety is routed correctly by dispatch_tool."""

    @pytest.mark.asyncio
    async def test_dispatch_routes_to_handler(self):
        """dispatch_tool routes 'check_payroll_safety' without 'Unknown tool' error."""
        payroll = _make_payroll_bucket()
        weeks = [_make_forecast_week(0)]
        for i in range(1, 5):
            weeks.append(_make_forecast_week(i, starting_balance="487000.00"))
        forecast = _make_forecast(weeks)
        db = _setup_db_mock(payroll_buckets=[payroll])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast):
            result = await dispatch_tool(db, "test_user", "check_payroll_safety", {})

        assert "error" not in result or "Unknown tool" not in result.get("error", "")
        assert result["success"] is True
