"""
Tests for TAMI operational tools — check_payroll_safety and analyze_concentration_risk.

Tests cover:
- check_payroll_safety: happy path, at-risk, shortfall, no payroll, Layer 2 downgrade
- analyze_concentration_risk: HHI*, normalization, portfolio size floor, runway impact
"""

import pytest
import json
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from app.tami.tools import (
    _check_payroll_safety,
    _compute_payroll_coverage,
    _analyze_concentration_risk,
    _generate_briefing,
    _query_overdue_invoices,
    _score_overdue_invoice,
    _PAYROLL_RISK_SCORE,
    _BRIEFING_MAX_ITEMS,
    dispatch_tool,
)


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

    @pytest.mark.asyncio
    async def test_dispatch_routes_concentration_risk(self):
        """dispatch_tool routes 'analyze_concentration_risk' without 'Unknown tool' error."""
        clients = [
            _make_client(client_id=f"c{i}", name=f"Client{i}", revenue_percent=Decimal("20"))
            for i in range(5)
        ]
        db = _setup_concentration_db_mock(clients)

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=_make_forecast(
            [_make_forecast_week(0)], starting_cash="487000.00"
        )):
            result = await dispatch_tool(db, "test_user", "analyze_concentration_risk", {"include_runway_impact": False})

        assert "error" not in result or "Unknown tool" not in result.get("error", "")
        assert result["success"] is True


# =============================================================================
# Helpers — analyze_concentration_risk
# =============================================================================

def _make_client(
    client_id: str = "client_startupx",
    name: str = "StartupX",
    relationship_type: str = "managed",
    revenue_percent: Decimal = Decimal("8.0"),
    billing_config: dict = None,
    status: str = "active",
):
    """Create a mock Client for concentration risk tests."""
    client = MagicMock()
    client.id = client_id
    client.name = name
    client.relationship_type = relationship_type
    client.revenue_percent = revenue_percent
    client.billing_config = billing_config or {"frequency": "monthly", "amount": "55000"}
    client.status = status
    return client


def _setup_concentration_db_mock(clients=None):
    """
    Build a mock db session for analyze_concentration_risk.

    Single query: select(Client).where(...) → scalars().all()
    """
    db = AsyncMock()

    async def mock_execute(query):
        result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = clients or []
        result.scalars.return_value = scalars_mock
        return result

    db.execute = mock_execute
    return db


# =============================================================================
# Tests — analyze_concentration_risk
# =============================================================================

class TestAnalyzeConcentrationRisk:
    """Tests for the analyze_concentration_risk tool."""

    @pytest.mark.asyncio
    async def test_low_risk_equal_split(self):
        """5 clients at 20% each → HHI*=0, risk_level=low."""
        clients = [
            _make_client(client_id=f"c{i}", name=f"Client{i}", revenue_percent=Decimal("20"))
            for i in range(5)
        ]
        db = _setup_concentration_db_mock(clients)

        result = await _analyze_concentration_risk(db, "test_user", {"include_runway_impact": False})

        assert result["success"] is True
        assert result["risk_level"] == "low"
        assert result["portfolio_size"] == 5
        # 5 clients at 20% each: raw HHI = 5 * 400 = 2000
        assert result["raw_hhi"] == 2000.0
        # HHI* = (2000 - 2000) / (10000 - 2000) = 0.0
        assert result["normalized_hhi"] == 0.0

    @pytest.mark.asyncio
    async def test_high_risk_dominant_client(self):
        """3 clients: 80/10/10 → high concentration."""
        clients = [
            _make_client(client_id="c0", name="BigCo", revenue_percent=Decimal("80")),
            _make_client(client_id="c1", name="SmallA", revenue_percent=Decimal("10")),
            _make_client(client_id="c2", name="SmallB", revenue_percent=Decimal("10")),
        ]
        db = _setup_concentration_db_mock(clients)

        result = await _analyze_concentration_risk(db, "test_user", {"include_runway_impact": False})

        assert result["success"] is True
        assert result["risk_level"] == "high"
        assert result["normalized_hhi"] > 0.35
        assert result["top_clients"][0]["name"] == "BigCo"

    @pytest.mark.asyncio
    async def test_moderate_risk(self):
        """4 clients: 60/20/10/10 → moderate concentration (HHI*≈0.23)."""
        clients = [
            _make_client(client_id="c0", name="BigCo", revenue_percent=Decimal("60")),
            _make_client(client_id="c1", name="MidA", revenue_percent=Decimal("20")),
            _make_client(client_id="c2", name="SmallA", revenue_percent=Decimal("10")),
            _make_client(client_id="c3", name="SmallB", revenue_percent=Decimal("10")),
        ]
        db = _setup_concentration_db_mock(clients)

        result = await _analyze_concentration_risk(db, "test_user", {"include_runway_impact": False})

        assert result["success"] is True
        assert result["risk_level"] == "moderate"
        assert 0.15 <= result["normalized_hhi"] < 0.35

    @pytest.mark.asyncio
    async def test_single_client_high_risk(self):
        """Single-client portfolio → high risk with dependency note."""
        clients = [_make_client(client_id="c0", name="OnlyCo", revenue_percent=Decimal("100"))]
        db = _setup_concentration_db_mock(clients)

        result = await _analyze_concentration_risk(db, "test_user", {"include_runway_impact": False})

        assert result["success"] is True
        assert result["risk_level"] == "high"
        assert result["raw_hhi"] == 10000
        assert "total dependency" in result["message"].lower() or "single" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_no_clients(self):
        """No active clients → graceful return."""
        db = _setup_concentration_db_mock([])

        result = await _analyze_concentration_risk(db, "test_user", {"include_runway_impact": False})

        assert result["success"] is True
        assert result["risk_level"] == "unknown"
        assert result["portfolio_size"] == 0

    @pytest.mark.asyncio
    async def test_runway_impact(self):
        """Runway impact shows weeks lost when excluding top client."""
        clients = [
            _make_client(client_id="c0", name="BigCo", revenue_percent=Decimal("60")),
            _make_client(client_id="c1", name="SmallCo", revenue_percent=Decimal("40")),
        ]
        db = _setup_concentration_db_mock(clients)

        base_forecast = _make_forecast([_make_forecast_week(0)], starting_cash="487000.00")
        base_forecast["summary"]["runway_weeks"] = 13

        excluded_forecast = _make_forecast([_make_forecast_week(0)], starting_cash="200000.00")
        excluded_forecast["summary"]["runway_weeks"] = 9

        call_count = {"n": 0}

        async def mock_forecast(db, user_id, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return base_forecast  # base call
            return excluded_forecast  # excluded call

        with patch("app.tami.tools.calculate_13_week_forecast", side_effect=mock_forecast):
            result = await _analyze_concentration_risk(db, "test_user", {"include_runway_impact": True})

        assert result["success"] is True
        top = result["top_clients"][0]
        assert top["name"] == "BigCo"
        assert "runway_impact" in top
        assert top["runway_impact"]["base_runway_weeks"] == 13
        assert top["runway_impact"]["without_client_weeks"] == 9
        assert top["runway_impact"]["weeks_lost"] == 4

    @pytest.mark.asyncio
    async def test_json_serializable(self):
        """Result must be fully JSON-serializable."""
        clients = [
            _make_client(client_id=f"c{i}", name=f"Client{i}", revenue_percent=Decimal("20"))
            for i in range(5)
        ]
        db = _setup_concentration_db_mock(clients)

        result = await _analyze_concentration_risk(db, "test_user", {"include_runway_impact": False})

        serialized = json.dumps(result)
        assert serialized is not None
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_normalization_non_100_sum(self):
        """Revenue percents that don't sum to 100 are normalized before HHI."""
        # 30 + 30 + 60 = 120, normalized to 25/25/50
        clients = [
            _make_client(client_id="c0", name="A", revenue_percent=Decimal("30")),
            _make_client(client_id="c1", name="B", revenue_percent=Decimal("30")),
            _make_client(client_id="c2", name="C", revenue_percent=Decimal("60")),
        ]
        db = _setup_concentration_db_mock(clients)

        result = await _analyze_concentration_risk(db, "test_user", {"include_runway_impact": False})

        assert result["success"] is True
        # Normalized: 25, 25, 50 → raw HHI = 625 + 625 + 2500 = 3750
        assert result["raw_hhi"] == 3750.0
        # NOT 5400 (which would be 30² + 30² + 60² without normalization)
        assert result["raw_hhi"] != 5400.0

    @pytest.mark.asyncio
    async def test_portfolio_size_floor(self):
        """2 clients at 50/50 → HHI*=0 but risk bumped to moderate due to small portfolio."""
        clients = [
            _make_client(client_id="c0", name="HalfA", revenue_percent=Decimal("50")),
            _make_client(client_id="c1", name="HalfB", revenue_percent=Decimal("50")),
        ]
        db = _setup_concentration_db_mock(clients)

        result = await _analyze_concentration_risk(db, "test_user", {"include_runway_impact": False})

        assert result["success"] is True
        # HHI* = 0.0 (perfectly even), but small portfolio floor kicks in
        assert result["normalized_hhi"] == 0.0
        assert result["risk_level"] == "moderate"  # bumped from "low"
        assert "small portfolio" in result["message"].lower() or str(result["portfolio_size"]) in result["message"]


# =============================================================================
# Helpers — generate_briefing
# =============================================================================

def _make_overdue_client(
    name: str = "RetailCo Rebrand",
    days: int = 14,
    amount: float = 52500.0,
    relationship: str = "transactional",
):
    """Create an overdue client dict matching _query_overdue_invoices output."""
    return {
        "client_id": f"client_{name.lower().replace(' ', '_')}",
        "client_name": name,
        "relationship_type": relationship,
        "total_overdue_amount": amount,
        "days_overdue": days,
        "invoice_count": 1,
    }


def _make_payroll_result(
    status: str = "safe",
    risk_week: int = None,
    has_payroll: bool = True,
):
    """Create a payroll coverage result dict matching _compute_payroll_coverage output."""
    return {
        "has_payroll": has_payroll,
        "overall_status": status,
        "first_risk_week": risk_week,
        "payroll_summary": {
            "frequency": "bi_weekly",
            "per_period_amount": "85000.00",
            "employee_count": 28,
            "monthly_total": "170000",
        },
        "coverage_by_week": [],
    }


def _make_rule_eval(
    name: str = "Minimum Cash Buffer",
    is_breached: bool = True,
    severity: str = "red",
    breach_week: int = 5,
    action_window_weeks: int = 3,
):
    """Create a mock rule evaluation."""
    ev = MagicMock()
    ev.name = name
    ev.is_breached = is_breached
    ev.severity = severity
    ev.breach_week = breach_week
    ev.action_window_weeks = action_window_weeks
    return ev


def _make_concentration_result(
    risk_level: str = "low",
    top_share: float = 17.5,
    hhi_star: float = 0.036,
):
    """Create a concentration risk result dict."""
    return {
        "success": True,
        "risk_level": risk_level,
        "normalized_hhi": hhi_star,
        "top_client_share_pct": top_share,
        "top_3_share_pct": top_share * 2.5,
        "top_clients": [{"name": "TechVentures", "revenue_share_pct": top_share}],
    }


# =============================================================================
# Tests — generate_briefing
# =============================================================================

class TestGenerateBriefing:
    """Tests for the generate_briefing tool."""

    @pytest.mark.asyncio
    async def test_payroll_always_first(self):
        """Payroll at-risk sorts above all other items regardless of their scores."""
        db = AsyncMock()
        forecast = _make_forecast([_make_forecast_week(0)])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("at_risk", risk_week=2)), \
             patch("app.tami.tools._query_overdue_invoices", return_value=[
                 _make_overdue_client("RetailCo", 14, 52500.0),
                 _make_overdue_client("StartupX", 12, 55000.0, "managed"),
             ]), \
             patch("app.tami.tools.evaluate_rules", return_value=[]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result()):
            result = await _generate_briefing(db, "test_user", {})

        assert result["success"] is True
        assert len(result["items"]) == 3
        assert result["items"][0]["category"] == "payroll_risk"
        assert result["items"][0]["priority_score"] == _PAYROLL_RISK_SCORE

    @pytest.mark.asyncio
    async def test_hard_cap_at_3(self):
        """Never returns more than 3 items even with 6+ candidates."""
        db = AsyncMock()
        forecast = _make_forecast([_make_forecast_week(0)])
        forecast["summary"]["runway_weeks"] = 5  # adds runway warning candidate

        overdue = [
            _make_overdue_client(f"Client{i}", days=10 + i, amount=20000.0 + i * 5000)
            for i in range(5)
        ]

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("at_risk", risk_week=3)), \
             patch("app.tami.tools._query_overdue_invoices", return_value=overdue), \
             patch("app.tami.tools.evaluate_rules", return_value=[_make_rule_eval()]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result("high", 35.0)):
            result = await _generate_briefing(db, "test_user", {})

        assert result["success"] is True
        assert len(result["items"]) == _BRIEFING_MAX_ITEMS

    @pytest.mark.asyncio
    async def test_all_clear(self):
        """Everything safe → empty items list with positive message."""
        db = AsyncMock()
        forecast = _make_forecast([_make_forecast_week(0)])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("safe")), \
             patch("app.tami.tools._query_overdue_invoices", return_value=[]), \
             patch("app.tami.tools.evaluate_rules", return_value=[]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result()):
            result = await _generate_briefing(db, "test_user", {})

        assert result["success"] is True
        assert result["items"] == []
        assert "no urgent items" in result["message"].lower()

    @pytest.mark.asyncio
    async def test_overdue_sorted_by_score(self):
        """Higher days+amount client ranks above lower when no payroll risk."""
        db = AsyncMock()
        forecast = _make_forecast([_make_forecast_week(0)])

        overdue = [
            _make_overdue_client("SmallOld", 20, 10000.0, "managed"),    # 200+200+10 = 410
            _make_overdue_client("BigRecent", 3, 80000.0, "managed"),    # 200+30+80 = 310
        ]

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("safe")), \
             patch("app.tami.tools._query_overdue_invoices", return_value=overdue), \
             patch("app.tami.tools.evaluate_rules", return_value=[]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result()):
            result = await _generate_briefing(db, "test_user", {})

        assert result["items"][0]["category"] == "overdue_invoice"
        assert "SmallOld" in result["items"][0]["headline"]  # higher days wins

    @pytest.mark.asyncio
    async def test_next_action_has_tool_name(self):
        """Every item has a next_action with a tool_name field."""
        db = AsyncMock()
        forecast = _make_forecast([_make_forecast_week(0)])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("at_risk", risk_week=2)), \
             patch("app.tami.tools._query_overdue_invoices", return_value=[_make_overdue_client()]), \
             patch("app.tami.tools.evaluate_rules", return_value=[]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result()):
            result = await _generate_briefing(db, "test_user", {})

        for item in result["items"]:
            assert "next_action" in item
            assert "tool_name" in item["next_action"]
            assert isinstance(item["next_action"]["tool_name"], str)
            assert len(item["next_action"]["tool_name"]) > 0

    @pytest.mark.asyncio
    async def test_overdue_headline_includes_specifics(self):
        """Overdue headlines contain client name, days late, and dollar amount."""
        db = AsyncMock()
        forecast = _make_forecast([_make_forecast_week(0)])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("safe")), \
             patch("app.tami.tools._query_overdue_invoices", return_value=[
                 _make_overdue_client("RetailCo Rebrand", 14, 52500.0),
             ]), \
             patch("app.tami.tools.evaluate_rules", return_value=[]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result()):
            result = await _generate_briefing(db, "test_user", {})

        headline = result["items"][0]["headline"]
        assert "RetailCo Rebrand" in headline
        assert "14" in headline
        assert "52,500" in headline

    @pytest.mark.asyncio
    async def test_json_serializable(self):
        """Full result must be JSON-serializable."""
        db = AsyncMock()
        forecast = _make_forecast([_make_forecast_week(0)])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("at_risk", risk_week=2)), \
             patch("app.tami.tools._query_overdue_invoices", return_value=[_make_overdue_client()]), \
             patch("app.tami.tools.evaluate_rules", return_value=[_make_rule_eval()]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result("moderate", 25.0)):
            result = await _generate_briefing(db, "test_user", {})

        serialized = json.dumps(result)
        assert serialized is not None
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_payroll_safe_excluded(self):
        """When payroll status is 'safe', no payroll item appears."""
        db = AsyncMock()
        forecast = _make_forecast([_make_forecast_week(0)])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("safe")), \
             patch("app.tami.tools._query_overdue_invoices", return_value=[_make_overdue_client()]), \
             patch("app.tami.tools.evaluate_rules", return_value=[]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result()):
            result = await _generate_briefing(db, "test_user", {})

        categories = [item["category"] for item in result["items"]]
        assert "payroll_risk" not in categories

    @pytest.mark.asyncio
    async def test_red_breach_above_amber(self):
        """Red rule breach scores higher than amber."""
        db = AsyncMock()
        forecast = _make_forecast([_make_forecast_week(0)])

        red_eval = _make_rule_eval("Buffer Rule", True, "red", 3, 1)
        amber_eval = _make_rule_eval("Buffer Rule 2", True, "amber", 6, 4)

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("safe")), \
             patch("app.tami.tools._query_overdue_invoices", return_value=[]), \
             patch("app.tami.tools.evaluate_rules", return_value=[amber_eval, red_eval]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result()):
            result = await _generate_briefing(db, "test_user", {})

        # Red breach should sort before amber
        assert len(result["items"]) == 2
        assert result["items"][0]["severity"] == "red"
        assert result["items"][1]["severity"] == "amber"

    @pytest.mark.asyncio
    async def test_concentration_only_moderate_or_high(self):
        """Low concentration risk does not generate a briefing item."""
        db = AsyncMock()
        forecast = _make_forecast([_make_forecast_week(0)])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("safe")), \
             patch("app.tami.tools._query_overdue_invoices", return_value=[]), \
             patch("app.tami.tools.evaluate_rules", return_value=[]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result("low")):
            result = await _generate_briefing(db, "test_user", {})

        categories = [item["category"] for item in result["items"]]
        assert "concentration_risk" not in categories

    @pytest.mark.asyncio
    async def test_runway_warning_threshold(self):
        """Runway >= 8 weeks produces no item; < 8 does."""
        db = AsyncMock()

        # 13 weeks — no warning
        forecast_safe = _make_forecast([_make_forecast_week(0)])
        forecast_safe["summary"]["runway_weeks"] = 13

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast_safe), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("safe")), \
             patch("app.tami.tools._query_overdue_invoices", return_value=[]), \
             patch("app.tami.tools.evaluate_rules", return_value=[]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result()):
            result_safe = await _generate_briefing(db, "test_user", {})

        assert all(item["category"] != "runway_warning" for item in result_safe["items"])

        # 5 weeks — warning should appear
        forecast_danger = _make_forecast([_make_forecast_week(0)])
        forecast_danger["summary"]["runway_weeks"] = 5

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast_danger), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("safe")), \
             patch("app.tami.tools._query_overdue_invoices", return_value=[]), \
             patch("app.tami.tools.evaluate_rules", return_value=[]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result()):
            result_danger = await _generate_briefing(db, "test_user", {})

        categories = [item["category"] for item in result_danger["items"]]
        assert "runway_warning" in categories

    @pytest.mark.asyncio
    async def test_runway_existential_above_overdue(self):
        """Runway <= 4 weeks scores above any overdue invoice."""
        db = AsyncMock()
        forecast = _make_forecast([_make_forecast_week(0)])
        forecast["summary"]["runway_weeks"] = 3

        overdue = [_make_overdue_client("BigClient", 30, 200000.0, "transactional")]

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("safe")), \
             patch("app.tami.tools._query_overdue_invoices", return_value=overdue), \
             patch("app.tami.tools.evaluate_rules", return_value=[]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result()):
            result = await _generate_briefing(db, "test_user", {})

        # Runway (3w → score 1000) should beat any overdue (max 999)
        assert result["items"][0]["category"] == "runway_warning"

    @pytest.mark.asyncio
    async def test_summary_fields_present(self):
        """Summary snapshot contains all expected keys."""
        db = AsyncMock()
        forecast = _make_forecast([_make_forecast_week(0)])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("safe")), \
             patch("app.tami.tools._query_overdue_invoices", return_value=[]), \
             patch("app.tami.tools.evaluate_rules", return_value=[]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result()):
            result = await _generate_briefing(db, "test_user", {})

        expected_keys = {
            "as_of_date", "starting_cash", "runway_weeks",
            "total_overdue", "overdue_count", "payroll_status",
            "concentration_risk",
        }
        assert expected_keys.issubset(result["summary"].keys())

    @pytest.mark.asyncio
    async def test_dispatch_routes_briefing(self):
        """dispatch_tool routes 'generate_briefing' without 'Unknown tool' error."""
        db = AsyncMock()
        forecast = _make_forecast([_make_forecast_week(0)])

        with patch("app.tami.tools.calculate_13_week_forecast", return_value=forecast), \
             patch("app.tami.tools._compute_payroll_coverage", return_value=_make_payroll_result("safe")), \
             patch("app.tami.tools._query_overdue_invoices", return_value=[]), \
             patch("app.tami.tools.evaluate_rules", return_value=[]), \
             patch("app.tami.tools._analyze_concentration_risk", return_value=_make_concentration_result()):
            result = await dispatch_tool(db, "test_user", "generate_briefing", {})

        assert "error" not in result or "Unknown tool" not in result.get("error", "")
        assert result["success"] is True
