"""
AgencyCo Demo Data Seed Script

Creates a realistic demo environment for an $8M ARR marketing agency with:
- 15 active clients (mix of retainers and projects)
- $487K cash across 3 bank accounts
- Bi-weekly payroll ($85K, due Friday)
- 12 vendor obligations due this/next week
- 5 overdue invoices (3-14 days late)
- Upcoming tax payment ($22K, due in 18 days)

Based on PRODUCT_ARCHITECTURE.md demo scenarios.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.data.users.models import User
from app.data.balances.models import CashAccount
from app.data.clients.models import Client
from app.data.expenses.models import ExpenseBucket
from app.data.obligations.models import ObligationAgreement, ObligationSchedule
from app.data.user_config.models import UserConfiguration, SafetyMode
from app.detection.models import DetectionRule, DetectionType, DetectionAlert, AlertSeverity, AlertStatus
from app.preparation.models import PreparedAction, ActionOption, ActionType, ActionStatus, RiskLevel
from app.execution.models import ExecutionAutomationRule, AutomationActionType
from app.auth.utils import get_password_hash
from app.data.base import generate_id

logger = logging.getLogger(__name__)

DEMO_USER_EMAIL = "demo@agencyco.com"
DEMO_USER_PASSWORD = "demo2026"


def get_next_friday() -> date:
    """Get the date of the next Friday."""
    today = date.today()
    days_until_friday = (4 - today.weekday()) % 7
    if days_until_friday == 0:
        days_until_friday = 7
    return today + timedelta(days=days_until_friday)


def get_due_day_this_month(day: int) -> date:
    """Get a specific day in the current month, or next month if passed."""
    today = date.today()
    target = date(today.year, today.month, min(day, 28))
    if target < today:
        # Move to next month
        if today.month == 12:
            target = date(today.year + 1, 1, min(day, 28))
        else:
            target = date(today.year, today.month + 1, min(day, 28))
    return target


async def seed_agencyco_data(db: AsyncSession, force: bool = False) -> dict:
    """
    Seed the database with AgencyCo demo data.

    Args:
        db: Database session
        force: If True, delete existing demo data and reseed

    Returns:
        dict with created entity counts
    """
    # Check if demo user already exists
    existing_user = await db.execute(
        select(User).where(User.email == DEMO_USER_EMAIL)
    )
    existing_user = existing_user.scalar_one_or_none()

    if existing_user and not force:
        logger.info(f"Demo user {DEMO_USER_EMAIL} already exists. Use force=True to reseed.")
        return {"status": "exists", "user_id": existing_user.id}

    if existing_user and force:
        logger.info(f"Deleting existing demo user {DEMO_USER_EMAIL}...")
        # Delete UserConfiguration first (has user_id as primary key, not properly cascaded)
        # Note: UserConfiguration is already imported at top of file
        existing_config = await db.execute(
            select(UserConfiguration).where(UserConfiguration.user_id == existing_user.id)
        )
        existing_config = existing_config.scalar_one_or_none()
        if existing_config:
            await db.delete(existing_config)
            await db.flush()
        await db.delete(existing_user)
        await db.flush()

    # Create demo user
    user = User(
        id=generate_id("user"),
        email=DEMO_USER_EMAIL,
        hashed_password=get_password_hash(DEMO_USER_PASSWORD),
        company_name="AgencyCo",
        has_completed_onboarding=True,
        base_currency="USD",
        industry="Professional Services",
        subcategory="Marketing Agency",
        revenue_range="$5M-$10M",
        business_profile_completed_at=datetime.now(),
        is_demo=True,
    )
    db.add(user)
    await db.flush()

    user_id = user.id
    today = date.today()

    # =========================================================================
    # CASH ACCOUNTS ($487K across 3 accounts)
    # =========================================================================
    cash_accounts = [
        CashAccount(
            id=generate_id("acct"),
            user_id=user_id,
            account_name="Operating Account (Chase)",
            balance=Decimal("325000.00"),
            currency="USD",
            as_of_date=today,
        ),
        CashAccount(
            id=generate_id("acct"),
            user_id=user_id,
            account_name="Payroll Account (Chase)",
            balance=Decimal("112000.00"),
            currency="USD",
            as_of_date=today,
        ),
        CashAccount(
            id=generate_id("acct"),
            user_id=user_id,
            account_name="Tax Reserve (Mercury)",
            balance=Decimal("50000.00"),
            currency="USD",
            as_of_date=today,
        ),
    ]
    for account in cash_accounts:
        db.add(account)

    # =========================================================================
    # CLIENTS (15 active - mix of retainers and projects)
    # =========================================================================
    clients_data = [
        # =======================================================================
        # RETAINER CLIENTS (Predictable recurring revenue)
        # =======================================================================
        # Strategic retainer clients (high value, reliable)
        {
            "name": "TechVentures Inc",
            "client_type": "retainer",
            "relationship_type": "strategic",
            "revenue_percent": Decimal("18.5"),
            "payment_behavior": "on_time",
            "avg_payment_delay_days": 0,
            "risk_level": "low",
            "churn_risk": "low",
            "billing_config": {
                "frequency": "monthly",
                "invoice_day": 15,
                "amount": "85000",
                "payment_terms": "net_15",
                "source": "manual",
            },
        },
        {
            "name": "GlobalBrands Co",
            "client_type": "retainer",
            "relationship_type": "strategic",
            "revenue_percent": Decimal("15.0"),
            "payment_behavior": "on_time",
            "avg_payment_delay_days": 2,
            "risk_level": "low",
            "churn_risk": "low",
            "billing_config": {
                "frequency": "monthly",
                "invoice_day": 1,
                "amount": "72000",
                "payment_terms": "net_30",
                "source": "manual",
            },
        },
        {
            "name": "Apex Industries",
            "client_type": "retainer",
            "relationship_type": "strategic",
            "revenue_percent": Decimal("12.0"),
            "payment_behavior": "on_time",
            "avg_payment_delay_days": 5,
            "risk_level": "low",
            "churn_risk": "low",
            "billing_config": {
                "frequency": "monthly",
                "invoice_day": 5,
                "amount": "65000",
                "payment_terms": "net_45",
                "source": "manual",
            },
        },
        # Managed retainer clients (medium value, some delays)
        {
            "name": "StartupX",
            "client_type": "retainer",
            "relationship_type": "managed",
            "revenue_percent": Decimal("8.0"),
            "payment_behavior": "delayed",
            "avg_payment_delay_days": 12,  # Often late - will trigger detection
            "risk_level": "medium",
            "churn_risk": "medium",
            "billing_config": {
                "frequency": "monthly",
                "invoice_day": 20,
                "amount": "55000",
                "payment_terms": "net_15",
                "source": "manual",
            },
        },
        {
            "name": "MediaGroup LLC",
            "client_type": "retainer",
            "relationship_type": "managed",
            "revenue_percent": Decimal("7.5"),
            "payment_behavior": "on_time",
            "avg_payment_delay_days": 3,
            "risk_level": "low",
            "churn_risk": "low",
            "billing_config": {
                "frequency": "monthly",
                "invoice_day": 8,
                "amount": "48000",
                "payment_terms": "net_30",
                "source": "manual",
            },
        },
        # Smaller retainer clients
        {
            "name": "LocalBiz Network",
            "client_type": "retainer",
            "relationship_type": "transactional",
            "revenue_percent": Decimal("3.5"),
            "payment_behavior": "delayed",
            "avg_payment_delay_days": 10,
            "risk_level": "medium",
            "churn_risk": "high",  # At risk of churning
            "billing_config": {
                "frequency": "monthly",
                "invoice_day": 12,
                "amount": "25000",
                "payment_terms": "net_15",
                "source": "manual",
            },
        },
        {
            "name": "GreenEnergy Co",
            "client_type": "retainer",
            "relationship_type": "managed",
            "revenue_percent": Decimal("3.0"),
            "payment_behavior": "on_time",
            "avg_payment_delay_days": 0,
            "risk_level": "low",
            "churn_risk": "low",
            "billing_config": {
                "frequency": "monthly",
                "invoice_day": 28,
                "amount": "18000",
                "payment_terms": "net_7",
                "source": "manual",
            },
        },

        # =======================================================================
        # PROJECT CLIENTS (Milestone-based, delivery-dependent revenue)
        # =======================================================================
        # Large rebrand project - multi-phase with delivery triggers
        {
            "name": "RetailCo Rebrand",
            "client_type": "project",
            "relationship_type": "transactional",
            "revenue_percent": Decimal("5.5"),
            "payment_behavior": "delayed",
            "avg_payment_delay_days": 14,  # Very late - critical
            "risk_level": "high",
            "churn_risk": "medium",
            "scope_risk": "medium",  # Rebrand scope can creep
            "billing_config": {
                "total_value": "150000",
                "payment_structure": "milestone",
                "milestones": [
                    {"name": "Discovery", "amount": "37500", "expected_date": str(today - timedelta(days=45)), "trigger_type": "delivery", "payment_terms": "net_7", "status": "paid"},
                    {"name": "Design", "amount": "52500", "expected_date": str(today - timedelta(days=14)), "trigger_type": "delivery", "payment_terms": "net_7", "status": "completed"},  # Delivered but not paid!
                    {"name": "Development", "amount": "37500", "expected_date": str(today + timedelta(days=21)), "trigger_type": "delivery", "payment_terms": "net_15", "status": "pending"},
                    {"name": "Launch", "amount": "22500", "expected_date": str(today + timedelta(days=45)), "trigger_type": "delivery", "payment_terms": "net_15", "status": "pending"},
                ],
                "source": "manual",
            },
        },
        # Healthcare campaign - strategy-heavy with date triggers
        {
            "name": "HealthTech Campaign",
            "client_type": "project",
            "relationship_type": "managed",
            "revenue_percent": Decimal("4.5"),
            "payment_behavior": "delayed",
            "avg_payment_delay_days": 8,
            "risk_level": "medium",
            "churn_risk": "low",
            "scope_risk": "low",  # Well-defined scope
            "billing_config": {
                "total_value": "95000",
                "payment_structure": "milestone",
                "milestones": [
                    {"name": "Strategy & Research", "amount": "28500", "expected_date": str(today - timedelta(days=30)), "trigger_type": "date", "payment_terms": "net_15", "status": "paid"},
                    {"name": "Campaign Execution", "amount": "47500", "expected_date": str(today - timedelta(days=8)), "trigger_type": "delivery", "payment_terms": "net_15", "status": "completed"},  # Overdue
                    {"name": "Reporting & Optimization", "amount": "19000", "expected_date": str(today + timedelta(days=30)), "trigger_type": "date", "payment_terms": "net_30", "status": "pending"},
                ],
                "source": "manual",
            },
        },
        # EdTech platform launch - larger project, partially complete
        {
            "name": "EduPlatform Launch",
            "client_type": "project",
            "relationship_type": "transactional",
            "revenue_percent": Decimal("4.0"),
            "payment_behavior": "on_time",
            "avg_payment_delay_days": 0,
            "risk_level": "low",
            "churn_risk": "low",
            "scope_risk": "medium",  # Platform projects can have scope changes
            "billing_config": {
                "total_value": "85000",
                "payment_structure": "milestone",
                "milestones": [
                    {"name": "UX/UI Design", "amount": "25500", "expected_date": str(today - timedelta(days=60)), "trigger_type": "delivery", "payment_terms": "net_15", "status": "paid"},
                    {"name": "Development Phase 1", "amount": "25500", "expected_date": str(today - timedelta(days=20)), "trigger_type": "delivery", "payment_terms": "net_15", "status": "paid"},
                    {"name": "Development Phase 2", "amount": "21250", "expected_date": str(today + timedelta(days=14)), "trigger_type": "delivery", "payment_terms": "net_15", "status": "pending"},
                    {"name": "Launch & QA", "amount": "12750", "expected_date": str(today + timedelta(days=35)), "trigger_type": "date", "payment_terms": "net_7", "status": "pending"},
                ],
                "source": "manual",
            },
        },
        # Small one-off website project
        {
            "name": "CraftBrew Website",
            "client_type": "project",
            "relationship_type": "transactional",
            "revenue_percent": Decimal("1.5"),
            "payment_behavior": "on_time",
            "avg_payment_delay_days": 0,
            "risk_level": "low",
            "churn_risk": "low",
            "scope_risk": "low",
            "billing_config": {
                "total_value": "35000",
                "payment_structure": "milestone",
                "milestones": [
                    {"name": "Deposit", "amount": "10500", "expected_date": str(today - timedelta(days=10)), "trigger_type": "date", "payment_terms": "due_on_receipt", "status": "paid"},
                    {"name": "Final Delivery", "amount": "24500", "expected_date": str(today + timedelta(days=25)), "trigger_type": "delivery", "payment_terms": "net_7", "status": "pending"},
                ],
                "source": "manual",
            },
        },
        # High-risk project with scope creep
        {
            "name": "FinanceApp Redesign",
            "client_type": "project",
            "relationship_type": "managed",
            "revenue_percent": Decimal("3.0"),
            "payment_behavior": "delayed",
            "avg_payment_delay_days": 10,
            "risk_level": "high",
            "churn_risk": "medium",
            "scope_risk": "high",  # Known scope creep issues
            "billing_config": {
                "total_value": "120000",
                "payment_structure": "milestone",
                "milestones": [
                    {"name": "Discovery & Audit", "amount": "24000", "expected_date": str(today - timedelta(days=40)), "trigger_type": "delivery", "payment_terms": "net_15", "status": "paid"},
                    {"name": "Wireframes", "amount": "30000", "expected_date": str(today - timedelta(days=5)), "trigger_type": "delivery", "payment_terms": "net_15", "status": "completed"},  # Just delivered
                    {"name": "UI Design", "amount": "36000", "expected_date": str(today + timedelta(days=28)), "trigger_type": "delivery", "payment_terms": "net_15", "status": "pending"},
                    {"name": "Dev Handoff", "amount": "30000", "expected_date": str(today + timedelta(days=56)), "trigger_type": "delivery", "payment_terms": "net_30", "status": "pending"},
                ],
                "source": "manual",
            },
        },

        # =======================================================================
        # USAGE-BASED CLIENTS (Variable, unpredictable revenue)
        # =======================================================================
        # Ad management - variable based on ad spend
        {
            "name": "AdNetwork Plus",
            "client_type": "usage",
            "relationship_type": "transactional",
            "revenue_percent": Decimal("5.0"),
            "payment_behavior": "on_time",
            "avg_payment_delay_days": 0,
            "risk_level": "medium",  # Variable revenue = medium risk
            "churn_risk": "low",
            "billing_config": {
                "settlement_frequency": "monthly",
                "typical_amount": "35000",  # Can vary 20-50k based on ad spend
                "payment_terms": "net_30",
                "source": "manual",
            },
            "notes": "15% of managed ad spend. Typically $25K-$45K/month based on client campaigns.",
        },
        # Content production - variable hours billed
        {
            "name": "ContentMill Agency",
            "client_type": "usage",
            "relationship_type": "managed",
            "revenue_percent": Decimal("3.0"),
            "payment_behavior": "delayed",
            "avg_payment_delay_days": 7,
            "risk_level": "medium",
            "churn_risk": "medium",
            "billing_config": {
                "settlement_frequency": "bi_weekly",
                "typical_amount": "10500",  # ~$21K/month, billed bi-weekly
                "payment_terms": "net_15",
                "source": "manual",
            },
            "notes": "Content production at $150/hr. Hours vary based on editorial calendar.",
        },
        # Consulting hours - highly variable
        {
            "name": "StrategyFirst Consulting",
            "client_type": "usage",
            "relationship_type": "strategic",
            "revenue_percent": Decimal("4.0"),
            "payment_behavior": "on_time",
            "avg_payment_delay_days": 0,
            "risk_level": "medium",
            "churn_risk": "low",
            "billing_config": {
                "settlement_frequency": "monthly",
                "typical_amount": "28000",  # Senior consulting at $350/hr
                "payment_terms": "net_15",
                "source": "manual",
            },
            "notes": "Executive consulting at $350/hr. Ranges from 40-120 hrs/month based on strategic initiatives.",
        },
        # Weekly API/platform usage fees
        {
            "name": "DataSync Platform",
            "client_type": "usage",
            "relationship_type": "transactional",
            "revenue_percent": Decimal("2.0"),
            "payment_behavior": "on_time",
            "avg_payment_delay_days": 0,
            "risk_level": "medium",
            "churn_risk": "medium",
            "billing_config": {
                "settlement_frequency": "weekly",
                "typical_amount": "4000",  # ~$16K/month, weekly billing
                "payment_terms": "net_7",
                "source": "manual",
            },
            "notes": "Platform usage fees. $0.02/API call + $500 base. Very spiky around month-end.",
        },
        # Commission-based affiliate revenue
        {
            "name": "MarketReach Affiliates",
            "client_type": "usage",
            "relationship_type": "transactional",
            "revenue_percent": Decimal("1.5"),
            "payment_behavior": "delayed",
            "avg_payment_delay_days": 5,
            "risk_level": "high",  # Highly variable
            "churn_risk": "medium",
            "billing_config": {
                "settlement_frequency": "monthly",
                "typical_amount": "12000",  # 10% commission, highly variable
                "payment_terms": "net_45",
                "source": "manual",
            },
            "notes": "10% commission on affiliate sales. Ranges $5K-$25K based on seasonal campaigns.",
        },

        # =======================================================================
        # MIXED CLIENTS (Combination of revenue types)
        # =======================================================================
        # Event agency - retainer for ongoing work + project fees for events
        {
            "name": "EventPro Services",
            "client_type": "mixed",
            "relationship_type": "transactional",
            "revenue_percent": Decimal("2.5"),
            "payment_behavior": "on_time",
            "avg_payment_delay_days": 3,
            "risk_level": "low",
            "churn_risk": "low",
            "billing_config": {
                "composition": {"retainer": 40, "project": 60},
                "dominant_type": "project",
                "retainer": {
                    "frequency": "monthly",
                    "invoice_day": 1,
                    "amount": "8000",
                    "payment_terms": "net_30",
                    "source": "manual",
                },
                "project": {
                    "total_value": "45000",
                    "payment_structure": "milestone",
                    "milestones": [
                        {"name": "Q1 Event - Deposit", "amount": "15000", "expected_date": str(today - timedelta(days=30)), "trigger_type": "date", "payment_terms": "due_on_receipt", "status": "paid"},
                        {"name": "Q1 Event - Final", "amount": "15000", "expected_date": str(today + timedelta(days=15)), "trigger_type": "delivery", "payment_terms": "net_7", "status": "pending"},
                        {"name": "Q2 Event - Deposit", "amount": "15000", "expected_date": str(today + timedelta(days=60)), "trigger_type": "date", "payment_terms": "due_on_receipt", "status": "pending"},
                    ],
                    "source": "manual",
                },
                "source": "manual",
            },
        },
        # PR firm - retainer + usage for media buys
        {
            "name": "PublicVoice PR",
            "client_type": "mixed",
            "relationship_type": "managed",
            "revenue_percent": Decimal("3.5"),
            "payment_behavior": "on_time",
            "avg_payment_delay_days": 0,
            "risk_level": "low",
            "churn_risk": "low",
            "billing_config": {
                "composition": {"retainer": 70, "usage": 30},
                "dominant_type": "retainer",
                "retainer": {
                    "frequency": "monthly",
                    "invoice_day": 15,
                    "amount": "22000",
                    "payment_terms": "net_30",
                    "source": "manual",
                },
                "usage": {
                    "settlement_frequency": "monthly",
                    "typical_amount": "8000",  # Media monitoring + placement fees
                    "payment_terms": "net_30",
                    "source": "manual",
                },
                "source": "manual",
            },
            "notes": "Monthly PR retainer + variable media placement fees (10% of placements).",
        },
    ]

    clients = []
    for data in clients_data:
        client = Client(
            id=generate_id("client"),
            user_id=user_id,
            name=data["name"],
            client_type=data["client_type"],
            currency="USD",
            status="active",
            relationship_type=data["relationship_type"],
            revenue_percent=data["revenue_percent"],
            payment_behavior=data["payment_behavior"],
            avg_payment_delay_days=data["avg_payment_delay_days"],
            risk_level=data["risk_level"],
            churn_risk=data["churn_risk"],
            scope_risk=data.get("scope_risk"),  # Project scope risk
            billing_config=data["billing_config"],
            notes=data.get("notes"),  # Client notes
            source="manual",
        )
        db.add(client)
        clients.append(client)

    await db.flush()

    # =========================================================================
    # EXPENSE BUCKETS (Vendors & Recurring Costs)
    # =========================================================================
    expenses_data = [
        # Payroll (critical, cannot delay)
        {
            "name": "Employee Payroll",
            "category": "payroll",
            "bucket_type": "fixed",
            "monthly_amount": Decimal("170000.00"),  # $85K bi-weekly
            "priority": "essential",
            "due_day": get_next_friday().day,  # Next Friday
            "frequency": "bi_weekly",
            "flexibility_level": "cannot_delay",
            "criticality": "critical",
            "employee_count": 28,
            "notes": "Bi-weekly payroll, 28 employees",
        },
        {
            "name": "Contractor Payments",
            "category": "contractors",
            "bucket_type": "variable",
            "monthly_amount": Decimal("45000.00"),
            "priority": "important",
            "due_day": 15,
            "frequency": "monthly",
            "flexibility_level": "negotiable",
            "criticality": "important",
            "notes": "Freelance designers and developers",
        },
        # Office & Operations
        {
            "name": "Office Lease - HQ",
            "category": "rent",
            "bucket_type": "fixed",
            "monthly_amount": Decimal("28000.00"),
            "priority": "essential",
            "due_day": 1,
            "frequency": "monthly",
            "flexibility_level": "cannot_delay",
            "criticality": "critical",
            "payment_terms": "due_on_receipt",
        },
        {
            "name": "Office Lease - Satellite",
            "category": "rent",
            "bucket_type": "fixed",
            "monthly_amount": Decimal("8500.00"),
            "priority": "important",
            "due_day": 1,
            "frequency": "monthly",
            "flexibility_level": "can_delay",  # Can negotiate
            "criticality": "important",
            "payment_terms": "net_15",
        },
        # Software & Tools
        {
            "name": "Adobe Creative Cloud",
            "category": "software",
            "bucket_type": "fixed",
            "monthly_amount": Decimal("4200.00"),
            "priority": "essential",
            "due_day": 10,
            "frequency": "monthly",
            "flexibility_level": "cannot_delay",
            "criticality": "critical",
            "payment_terms": "due_on_receipt",
        },
        {
            "name": "HubSpot Marketing",
            "category": "software",
            "bucket_type": "fixed",
            "monthly_amount": Decimal("3800.00"),
            "priority": "important",
            "due_day": 15,
            "frequency": "monthly",
            "flexibility_level": "can_delay",
            "criticality": "important",
            "payment_terms": "net_30",
        },
        {
            "name": "Slack & Productivity Tools",
            "category": "software",
            "bucket_type": "fixed",
            "monthly_amount": Decimal("1850.00"),
            "priority": "important",
            "due_day": 20,
            "frequency": "monthly",
            "flexibility_level": "can_delay",
            "criticality": "important",
        },
        {
            "name": "AWS Infrastructure",
            "category": "software",
            "bucket_type": "variable",
            "monthly_amount": Decimal("6500.00"),
            "priority": "essential",
            "due_day": 5,
            "frequency": "monthly",
            "flexibility_level": "cannot_delay",
            "criticality": "critical",
        },
        # Marketing & Business Dev
        {
            "name": "Ad Spend - Google/Meta",
            "category": "marketing",
            "bucket_type": "variable",
            "monthly_amount": Decimal("35000.00"),
            "priority": "medium",
            "due_day": 1,
            "frequency": "monthly",
            "flexibility_level": "can_delay",
            "criticality": "flexible",
            "notes": "Can reduce if cash tight",
        },
        {
            "name": "Trade Show & Events",
            "category": "marketing",
            "bucket_type": "variable",
            "monthly_amount": Decimal("12000.00"),
            "priority": "low",
            "due_day": 25,
            "frequency": "monthly",
            "flexibility_level": "can_delay",
            "criticality": "flexible",
        },
        # Other recurring
        {
            "name": "Insurance (E&O + General)",
            "category": "other",
            "bucket_type": "fixed",
            "monthly_amount": Decimal("4500.00"),
            "priority": "essential",
            "due_day": 1,
            "frequency": "monthly",
            "flexibility_level": "cannot_delay",
            "criticality": "critical",
        },
        {
            "name": "Professional Services (Legal/Accounting)",
            "category": "other",
            "bucket_type": "variable",
            "monthly_amount": Decimal("8000.00"),
            "priority": "important",
            "due_day": 30,
            "frequency": "monthly",
            "flexibility_level": "negotiable",
            "criticality": "important",
            "payment_terms": "net_30",
        },
    ]

    expenses = []
    for data in expenses_data:
        expense = ExpenseBucket(
            id=generate_id("bucket"),
            user_id=user_id,
            name=data["name"],
            category=data["category"],
            bucket_type=data["bucket_type"],
            monthly_amount=data["monthly_amount"],
            currency="USD",
            priority=data["priority"],
            is_stable=data["bucket_type"] == "fixed",
            due_day=data.get("due_day", 15),
            frequency=data.get("frequency", "monthly"),
            flexibility_level=data.get("flexibility_level"),
            criticality=data.get("criticality"),
            payment_terms=data.get("payment_terms"),
            employee_count=data.get("employee_count"),
            notes=data.get("notes"),
            source="manual",
        )
        db.add(expense)
        expenses.append(expense)

    await db.flush()

    # =========================================================================
    # OVERDUE INVOICES (5 invoices, 3-14 days late) - Create as ObligationSchedules
    # =========================================================================

    # Find clients that should have overdue invoices
    overdue_clients = [
        ("StartupX", 12, Decimal("55000.00")),  # 12 days late
        ("RetailCo Rebrand", 14, Decimal("52500.00")),  # 14 days late (Design milestone)
        ("HealthTech Campaign", 8, Decimal("47500.00")),  # 8 days late (Execution milestone)
        ("LocalBiz Network", 10, Decimal("25000.00")),  # 10 days late
        ("ContentMill Agency", 3, Decimal("21000.00")),  # 3 days late
    ]

    overdue_obligations = []
    for client in clients:
        for name, days_late, amount in overdue_clients:
            if client.name == name:
                # Create obligation agreement for this revenue
                obligation = ObligationAgreement(
                    id=generate_id("obl"),
                    user_id=user_id,
                    client_id=client.id,
                    obligation_type="revenue",
                    amount_type="fixed",
                    amount_source="manual_entry",
                    base_amount=amount,
                    currency="USD",
                    frequency="monthly" if client.client_type == "retainer" else "one_time",
                    start_date=today - timedelta(days=60),
                    category="other",  # Revenue category
                    confidence="high",
                    vendor_name=client.name,
                    notes=f"Invoice from {client.name}",
                )
                db.add(obligation)
                await db.flush()

                # Create overdue schedule
                schedule = ObligationSchedule(
                    id=generate_id("sched"),
                    obligation_id=obligation.id,
                    due_date=today - timedelta(days=days_late),
                    estimated_amount=amount,
                    estimate_source="fixed_agreement",
                    confidence="high",
                    status="overdue",
                    notes=f"Invoice {days_late} days overdue",
                )
                db.add(schedule)
                overdue_obligations.append((obligation, schedule))
                break

    # =========================================================================
    # TAX OBLIGATION ($22K due in 18 days)
    # =========================================================================
    tax_obligation = ObligationAgreement(
        id=generate_id("obl"),
        user_id=user_id,
        obligation_type="tax_obligation",
        amount_type="fixed",
        amount_source="manual_entry",
        base_amount=Decimal("22000.00"),
        currency="USD",
        frequency="quarterly",
        start_date=today,
        category="other",
        confidence="high",
        vendor_name="IRS - Quarterly Estimated Tax",
        notes="Q1 2026 Estimated Tax Payment",
    )
    db.add(tax_obligation)
    await db.flush()

    tax_schedule = ObligationSchedule(
        id=generate_id("sched"),
        obligation_id=tax_obligation.id,
        due_date=today + timedelta(days=18),
        estimated_amount=Decimal("22000.00"),
        estimate_source="manual_estimate",
        confidence="high",
        status="scheduled",
        notes="Quarterly estimated tax - statutory deadline",
    )
    db.add(tax_schedule)

    # =========================================================================
    # USER CONFIGURATION
    # =========================================================================
    user_config = UserConfiguration(
        user_id=user_id,
        obligations_buffer_amount=Decimal("150000.00"),  # 3 months of payroll buffer
        runway_buffer_months=3,
        late_payment_threshold_days=7,
        unexpected_expense_threshold_pct=Decimal("20.0"),
        safety_mode="normal",  # Use string value for enum
        payroll_check_days_before=7,
        payroll_buffer_percent=Decimal("10.0"),
        payment_cluster_threshold_pct=Decimal("40.0"),
    )
    db.add(user_config)

    # =========================================================================
    # DETECTION RULES (Enable all rules with default thresholds)
    # =========================================================================
    detection_rules = [
        DetectionRule(
            user_id=user_id,
            detection_type="late_payment",
            name="Late Payment Detection",
            description="Alerts when client payments are overdue",
            enabled=True,
            thresholds={"days_overdue": 7, "emergency_days": 14},
        ),
        DetectionRule(
            user_id=user_id,
            detection_type="payroll_safety",
            name="Payroll Safety Check",
            description="Ensures cash is available before payroll",
            enabled=True,
            thresholds={"days_before": 7, "buffer_percent": 10},
        ),
        DetectionRule(
            user_id=user_id,
            detection_type="buffer_breach",
            name="Cash Buffer Monitor",
            description="Alerts when cash buffer drops below threshold",
            enabled=True,
            thresholds={"warning_percent": 80, "emergency_percent": 50},
        ),
        DetectionRule(
            user_id=user_id,
            detection_type="statutory_deadline",
            name="Statutory Deadline Tracker",
            description="Tracks tax and regulatory payment deadlines",
            enabled=True,
            thresholds={"warning_days": [14, 7, 3]},
        ),
        DetectionRule(
            user_id=user_id,
            detection_type="unexpected_expense",
            name="Expense Variance Alert",
            description="Flags unusual expense increases",
            enabled=True,
            thresholds={"variance_percent": 20, "emergency_percent": 50},
        ),
        DetectionRule(
            user_id=user_id,
            detection_type="payment_timing_conflict",
            name="Payment Timing Conflict",
            description="Detects cash flow conflicts from clustered payments",
            enabled=True,
            thresholds={"cash_percent": 40, "emergency_percent": 60},
        ),
    ]
    for rule in detection_rules:
        db.add(rule)

    await db.flush()

    # =========================================================================
    # AUTOMATION RULES (V2 defaults) - Skipped due to enum migration issue
    # =========================================================================
    # TODO: Re-enable once database enum is properly migrated
    # automation_rules = [
    #     ExecutionAutomationRule(
    #         user_id=user_id,
    #         action_type=Automationinvoice_follow_up,
    #         auto_execute=False,
    #         threshold_amount=None,
    #         excluded_tags=["strategic"],
    #         require_approval=True,
    #     ),
    #     ...
    # ]
    # for rule in automation_rules:
    #     db.add(rule)
    # await db.flush()

    # =========================================================================
    # PRE-CREATED DETECTION ALERTS (Demo scenarios)
    # =========================================================================
    alerts_created = []

    # Alert 1: Late Payment - RetailCo (14 days, EMERGENCY)
    retailco_client = next((c for c in clients if c.name == "RetailCo Rebrand"), None)
    if retailco_client:
        alert1 = DetectionAlert(
            id=generate_id("alert"),
            user_id=user_id,
            detection_type="late_payment",
            severity="emergency",
            status="active",
            title="Payment 14 Days Overdue: RetailCo Rebrand",
            description="Design milestone payment of $52,500 from RetailCo Rebrand is now 14 days overdue. This is unusual - the invoice was due on completion of design phase.",
            cash_impact=Decimal("-52500.00"),
            context_data={
                "client_id": retailco_client.id,
                "client_name": retailco_client.name,
                "invoice_amount": 52500,
                "days_overdue": 14,
                "relationship_type": "transactional",
                "revenue_percent": 5.5,
                "payment_behavior": "delayed",
            },
            deadline=today + timedelta(days=1),
        )
        db.add(alert1)
        alerts_created.append(alert1)
        await db.flush()

        # Create prepared action for this alert
        action1 = PreparedAction(
            id=generate_id("action"),
            user_id=user_id,
            alert_id=alert1.id,
            action_type="invoice_follow_up",
            status="pending_approval",
            problem_summary="RetailCo Rebrand's Design milestone payment ($52,500) is 14 days overdue - significantly past their usual payment pattern. This impacts next week's cash position.",
            deadline=today + timedelta(days=1),
        )
        db.add(action1)
        await db.flush()

        # Create options for the action
        option1_1 = ActionOption(
            id=generate_id("opt"),
            action_id=action1.id,
            is_recommended=True,
            risk_level="medium",
            reasoning=[
                "Client is transactional (5.5% of revenue) - not a strategic relationship",
                "14 days is significantly past their usual 3-day delay pattern",
                "Firm but professional tone appropriate for escalation",
            ],
            prepared_content={
                "email_subject": "Urgent: Invoice #RC-2026-04 - 14 Days Overdue",
                "email_body": """Hi,

I hope this message finds you well. I'm following up on Invoice #RC-2026-04 for the Design milestone ($52,500), which is now 14 days past due.

We understand that delays can happen, but this is outside your usual payment timeline. Could you please provide an update on when we can expect payment?

If there are any issues with the invoice or the deliverables, please let me know so we can resolve them promptly.

Best regards,
AgencyCo Finance Team""",
                "recipient": "accounts@retailco.example.com",
                "tone": "firm",
            },
            cash_impact=Decimal("52500.00"),
        )
        option1_2 = ActionOption(
            id=generate_id("opt"),
            action_id=action1.id,
            is_recommended=False,
            risk_level="low",
            reasoning=[
                "Softer approach preserves relationship",
                "May be appropriate if there's an internal client issue",
                "Lower urgency but less likely to get immediate payment",
            ],
            prepared_content={
                "email_subject": "Following Up: Invoice #RC-2026-04",
                "email_body": """Hi,

Just wanted to check in on Invoice #RC-2026-04 for the Design milestone. I noticed it's still outstanding and wanted to see if there's anything we can help with on our end.

Please let me know if you have any questions or need any additional documentation.

Best,
AgencyCo Finance Team""",
                "recipient": "accounts@retailco.example.com",
                "tone": "soft",
            },
            cash_impact=Decimal("52500.00"),
        )
        db.add(option1_1)
        db.add(option1_2)

    # Alert 2: New Hire Impact - Senior Developer starting Monday
    alert2 = DetectionAlert(
        id=generate_id("alert"),
        user_id=user_id,
        detection_type="headcount_change",  # Use enum value from DetectionType
        severity="this_week",
        status="active",
        title="New Hire Impact: Senior Developer starts Monday",
        description="Alex Chen starts Monday with $12,500/month salary + benefits. This increases monthly burn by 8.3% ($150K annually) and reduces runway from 14 weeks to 11 weeks.",
        cash_impact=Decimal("-16000.00"),
        context_data={
            "employee_name": "Alex Chen",
            "role": "Senior Developer",
            "start_date": str(today + timedelta(days=(7 - today.weekday()) % 7)),
            "monthly_salary": 12500,
            "annual_cost": 150000,
            "onboarding_cost": 3500,
            "first_month_total": 16000,
            "burn_increase_percent": 8.3,
            "runway_before": 14,
            "runway_after": 11,
        },
        deadline=today + timedelta(days=(7 - today.weekday()) % 7),
    )
    db.add(alert2)
    alerts_created.append(alert2)
    await db.flush()

    action2 = PreparedAction(
        id=generate_id("action"),
        user_id=user_id,
        alert_id=alert2.id,
        action_type="manual",
        status="pending_approval",
        problem_summary="New hire Alex Chen starts Monday. First month costs $16K (salary + onboarding). Runway drops from 14 to 11 weeks. Consider accelerating invoicing to offset.",
        deadline=today + timedelta(days=(7 - today.weekday()) % 7),
    )
    db.add(action2)
    await db.flush()

    option2_1 = ActionOption(
        id=generate_id("opt"),
        action_id=action2.id,
        is_recommended=True,
        risk_level="low",
        reasoning=[
            "Equipment budget $3,500 already allocated",
            "First month total cost: $16,000",
            "No unexpected costs detected",
        ],
        prepared_content={
            "action": "confirm_onboarding",
            "equipment_list": "MacBook Pro ($2,400), monitors ($600), software licenses ($500)",
            "first_month_cost": 16000,
            "notes": "All onboarding costs within budget. Recommend accelerating TechCorp invoicing to offset.",
        },
        cash_impact=Decimal("-16000.00"),
    )
    option2_2 = ActionOption(
        id=generate_id("opt"),
        action_id=action2.id,
        is_recommended=False,
        risk_level="low",
        reasoning=[
            "$28K in invoices ready to send to TechCorp",
            "Can improve cash timing by 3 weeks",
            "Offsets new hire cost impact",
        ],
        prepared_content={
            "action": "accelerate_invoicing",
            "invoice_total": 28000,
            "client": "TechCorp",
            "description": "Batch invoice for TechCorp Q1 deliverables - 3 milestone payments",
        },
        cash_impact=Decimal("28000.00"),
    )
    db.add(option2_1)
    db.add(option2_2)

    # Alert 3: Vendor Rate Increase - Figma renewal +40%
    alert3 = DetectionAlert(
        id=generate_id("alert"),
        user_id=user_id,
        detection_type="unexpected_expense",  # Use enum value from DetectionType
        severity="this_week",
        status="active",
        title="Vendor Rate Increase: Figma renewal +40%",
        description="Figma annual renewal increased from $3,600 to $5,040 (+40%). Auto-renewal triggers in 12 days. Team is only using 60% of current seat allocation (8/12 seats active).",
        cash_impact=Decimal("-1440.00"),
        context_data={
            "vendor": "Figma",
            "current_cost": 3600,
            "new_cost": 5040,
            "increase_percent": 40,
            "days_until_renewal": 12,
            "seats_total": 12,
            "seats_active": 8,
            "utilization_percent": 60,
            "renewal_type": "auto",
        },
        deadline=today + timedelta(days=12),
    )
    db.add(alert3)
    alerts_created.append(alert3)
    await db.flush()

    action3 = PreparedAction(
        id=generate_id("action"),
        user_id=user_id,
        alert_id=alert3.id,
        action_type="vendor_delay",
        status="pending_approval",
        problem_summary="Figma renewal +40% ($3,600 → $5,040). Auto-renewal in 12 days. With 40% seats unused, you have leverage for negotiation or plan downsizing.",
        deadline=today + timedelta(days=10),
    )
    db.add(action3)
    await db.flush()

    option3_1 = ActionOption(
        id=generate_id("opt"),
        action_id=action3.id,
        is_recommended=True,
        risk_level="low",
        reasoning=[
            "40% of seats are unused (8/12 active)",
            "Negotiation typically yields 15-25% savings",
            "Competitor alternatives available as leverage",
        ],
        prepared_content={
            "email_subject": "Renewal Discussion - Account #F8892",
            "email_body": """Hi Figma Team,

We're reviewing our renewal and noticed we're not fully utilizing our seat allocation. Before auto-renewal, we'd like to discuss options:

1. Enterprise pricing for our usage level
2. Right-sizing our plan to match actual usage

Our team is using 8 of 12 seats. Could we schedule a call to discuss options?

Best regards,
AgencyCo""",
            "recipient": "enterprise@figma.com",
            "tone": "professional",
        },
        cash_impact=Decimal("-1260.00"),
    )
    option3_2 = ActionOption(
        id=generate_id("opt"),
        action_id=action3.id,
        is_recommended=False,
        risk_level="medium",
        reasoning=[
            "Saves $1,680/year immediately",
            "Requires confirming with team leads which seats to remove",
            "May need to reassign some users",
        ],
        prepared_content={
            "action": "right_size_plan",
            "current_seats": 12,
            "recommended_seats": 8,
            "annual_savings": 1680,
            "notes": "Audit current usage and identify 4 inactive seats to remove",
        },
        cash_impact=Decimal("-1680.00"),
    )
    db.add(option3_1)
    db.add(option3_2)

    # Alert 4: Opportunity - Early Payment Discount
    alert4 = DetectionAlert(
        id=generate_id("alert"),
        user_id=user_id,
        detection_type="cash_optimization",
        severity="upcoming",
        status="active",
        title="Opportunity: Early payment discount from GlobalTech",
        description="GlobalTech offering 2% discount ($900 savings) for payment within 10 days. Invoice: $45,000. Cash position supports early payment with buffer maintained.",
        cash_impact=Decimal("900.00"),
        context_data={
            "vendor": "GlobalTech",
            "invoice_amount": 45000,
            "discount_percent": 2,
            "discount_amount": 900,
            "days_remaining": 10,
            "standard_due_days": 30,
            "annualized_return": 24,
            "buffer_after_payment": "maintained",
        },
        deadline=today + timedelta(days=10),
    )
    db.add(alert4)
    alerts_created.append(alert4)
    await db.flush()

    action4 = PreparedAction(
        id=generate_id("action"),
        user_id=user_id,
        alert_id=alert4.id,
        action_type="payment_batch",
        status="pending_approval",
        problem_summary="GlobalTech offers 2% discount for early payment. Pay $44,100 now instead of $45,000 in 30 days. Equivalent to 24% annualized return.",
        deadline=today + timedelta(days=8),
    )
    db.add(action4)
    await db.flush()

    option4_1 = ActionOption(
        id=generate_id("opt"),
        action_id=action4.id,
        is_recommended=True,
        risk_level="low",
        reasoning=[
            "2% discount = 24% annualized return",
            "Cash buffer remains above minimum threshold",
            "Strong cash position supports early payment",
        ],
        prepared_content={
            "action": "early_payment",
            "vendor": "GlobalTech",
            "original_amount": 45000,
            "discounted_amount": 44100,
            "savings": 900,
            "payment_deadline": str(today + timedelta(days=10)),
        },
        cash_impact=Decimal("900.00"),
    )
    db.add(option4_1)

    # Alert 5: Client Contract Ending - HealthTech Phase 1
    healthtech_client = next((c for c in clients if "HealthTech" in c.name), None)
    if healthtech_client:
        alert5 = DetectionAlert(
            id=generate_id("alert"),
            user_id=user_id,
            detection_type="client_churn",  # Use enum value from DetectionType
            severity="upcoming",
            status="active",
            title="Client Contract Ending: HealthTech Phase 1",
            description="HealthTech Phase 1 contract ($18K/month) ends in 6 weeks. No Phase 2 contract signed yet. Represents 12% of monthly revenue.",
            cash_impact=Decimal("-54000.00"),
            context_data={
                "client_id": healthtech_client.id,
                "client_name": healthtech_client.name,
                "contract_value_monthly": 18000,
                "contract_end_weeks": 6,
                "revenue_percent": 12,
                "phase_2_status": "not_signed",
                "relationship_strength": "strong",
                "expansion_interest": "mentioned",
            },
            deadline=today + timedelta(weeks=6),
        )
        db.add(alert5)
        alerts_created.append(alert5)
        await db.flush()

        action5 = PreparedAction(
            id=generate_id("action"),
            user_id=user_id,
            alert_id=alert5.id,
            action_type="invoice_follow_up",
            status="pending_approval",
            problem_summary="HealthTech Phase 1 ($18K/month) ends in 6 weeks. Client mentioned expansion interest. Proactive outreach recommended to secure Phase 2.",
            deadline=today + timedelta(weeks=4),
        )
        db.add(action5)
        await db.flush()

        option5_1 = ActionOption(
            id=generate_id("opt"),
            action_id=action5.id,
            is_recommended=True,
            risk_level="low",
            reasoning=[
                "Strong relationship - Phase 1 delivered on time",
                "Client mentioned expansion interest in last call",
                "Proactive outreach shows partnership mindset",
            ],
            prepared_content={
                "email_subject": "Phase 2 Proposal - HealthTech Platform",
                "email_body": """Hi Jennifer,

As we wrap up Phase 1, I wanted to share our proposal for the next phase of the HealthTech Platform project.

Based on our conversations and the success of Phase 1, we've outlined three options for Phase 2:

1. Core maintenance + minor enhancements: $15K/month
2. Full feature expansion: $22K/month
3. Enterprise rollout support: $28K/month

Would you have time this week to discuss which direction makes sense for the team?

Best regards,
AgencyCo""",
                "recipient": "jennifer@healthtech.example.com",
                "tone": "professional",
            },
            cash_impact=Decimal("54000.00"),
        )
        option5_2 = ActionOption(
            id=generate_id("opt"),
            action_id=action5.id,
            is_recommended=False,
            risk_level="low",
            reasoning=[
                "Understand worst-case runway impact",
                "Plan contingencies if contract not renewed",
                "No action required - analysis only",
            ],
            prepared_content={
                "action": "run_scenario",
                "scenario_name": "HealthTech contract ends without renewal",
                "revenue_impact": -18000,
                "runway_impact": "Analyze impact on 13-week forecast",
            },
            cash_impact=Decimal("0.00"),
        )
        db.add(option5_1)
        db.add(option5_2)

    # Alert 6: High Churn Risk Client - LocalBiz Network
    localbiz_client = next((c for c in clients if c.name == "LocalBiz Network"), None)
    if localbiz_client:
        alert6 = DetectionAlert(
            id=generate_id("alert"),
            user_id=user_id,
            detection_type="client_churn",  # Use enum value from DetectionType
            severity="this_week",
            status="active",
            title="High Churn Risk: LocalBiz Network",
            description="LocalBiz Network shows high churn risk signals: declining engagement, delayed payments, and reduced scope requests. This client represents $25K/month (3.5% of revenue).",
            cash_impact=Decimal("-75000.00"),  # 3 months impact
            context_data={
                "client_id": localbiz_client.id,
                "client_name": localbiz_client.name,
                "monthly_revenue": 25000,
                "revenue_percent": 3.5,
                "churn_risk": "high",
                "risk_signals": ["payment_delays", "reduced_engagement", "scope_reduction_requests"],
            },
            deadline=today + timedelta(days=14),
        )
        db.add(alert6)
        alerts_created.append(alert6)
        await db.flush()

        action6 = PreparedAction(
            id=generate_id("action"),
            user_id=user_id,
            alert_id=alert6.id,
            action_type="invoice_follow_up",
            status="pending_approval",
            problem_summary="LocalBiz Network showing churn signals. Proactive outreach recommended to retain this $25K/month client.",
            deadline=today + timedelta(days=7),
        )
        db.add(action6)
        await db.flush()

        option6_1 = ActionOption(
            id=generate_id("opt"),
            action_id=action6.id,
            is_recommended=True,
            risk_level="medium",
            reasoning=[
                "Client has delayed recent payments",
                "Engagement metrics down 30% this quarter",
                "Proactive check-in may prevent churn",
            ],
            prepared_content={
                "email_subject": "Checking in - How can we better support LocalBiz?",
                "email_body": """Hi,

I wanted to personally reach out to see how things are going with our partnership. We've noticed a few changes in our recent interactions and I'd love to understand if there's anything we can do differently.

Would you have 15 minutes this week for a quick call? I'd like to ensure we're delivering maximum value for your business.

Best regards,
AgencyCo""",
                "recipient": "contact@localbiz.example.com",
                "tone": "consultative",
            },
            cash_impact=Decimal("25000.00"),
        )
        db.add(option6_1)

    await db.flush()

    # =========================================================================
    # Generate Obligations from Clients and Expenses
    # =========================================================================
    # Note: Obligations are now the canonical source for forecasts.
    # Import ObligationService and generate obligations from seeded clients/expenses.
    from app.services.obligations import ObligationService
    obligation_service = ObligationService(db)

    obligations_created = 0
    schedules_created = 0

    # Generate obligations from clients (with schedules)
    for client in clients:
        try:
            obligation = await obligation_service.create_obligation_from_client(
                client, auto_generate_schedules=True
            )
            if obligation:
                obligations_created += 1
                # Count schedules for this obligation
                from sqlalchemy import func
                schedule_count = await db.execute(
                    select(func.count()).select_from(ObligationSchedule).where(
                        ObligationSchedule.obligation_id == obligation.id
                    )
                )
                schedules_created += schedule_count.scalar() or 0
        except Exception as e:
            logger.warning(f"Failed to create obligation for client {client.name}: {e}")

    # Generate obligations from expenses (with schedules)
    for expense in expenses:
        try:
            obligation = await obligation_service.create_obligation_from_expense(
                expense, auto_generate_schedules=True
            )
            if obligation:
                obligations_created += 1
                # Count schedules for this obligation
                from sqlalchemy import func
                schedule_count = await db.execute(
                    select(func.count()).select_from(ObligationSchedule).where(
                        ObligationSchedule.obligation_id == obligation.id
                    )
                )
                schedules_created += schedule_count.scalar() or 0
        except Exception as e:
            logger.warning(f"Failed to create obligation for expense {expense.name}: {e}")

    await db.commit()

    result = {
        "status": "created",
        "user_id": user_id,
        "user_email": DEMO_USER_EMAIL,
        "counts": {
            "cash_accounts": len(cash_accounts),
            "clients": len(clients),
            "expenses": len(expenses),
            "overdue_invoices": len(overdue_obligations),
            "obligations": obligations_created,
            "schedules": schedules_created,
            "detection_rules": len(detection_rules),
            "automation_rules": 0,  # Skipped due to enum migration issue
            "alerts": len(alerts_created),
        },
        "summary": {
            "total_cash": sum(float(a.balance) for a in cash_accounts),
            "next_payroll": str(get_next_friday()),
            "payroll_amount": 85000,
            "overdue_total": sum(float(s.estimated_amount) for _, s in overdue_obligations),
            "tax_due_date": str(today + timedelta(days=18)),
            "tax_amount": 22000,
        },
        "demo_scenarios": {
            "emergency_alerts": 1,  # RetailCo 14 days overdue
            "this_week_alerts": 2,  # StartupX + Payroll check
            "upcoming_alerts": 1,   # Tax payment
            "actions_pending": 3,   # Invoice follow-ups + payroll confirmation
        }
    }

    logger.info(f"AgencyCo demo data seeded successfully: {result}")
    return result


async def clear_demo_data(db: AsyncSession) -> dict:
    """Remove all demo data by deleting the demo user (cascades to related data)."""
    result = await db.execute(
        select(User).where(User.email == DEMO_USER_EMAIL)
    )
    user = result.scalar_one_or_none()

    if user:
        await db.delete(user)
        await db.commit()
        return {"status": "deleted", "user_email": DEMO_USER_EMAIL}

    return {"status": "not_found", "user_email": DEMO_USER_EMAIL}
