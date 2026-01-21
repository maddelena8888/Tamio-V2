"""Seed data routes for demo/development."""
from datetime import datetime, timedelta
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.seed.agencyco import seed_agencyco_data, clear_demo_data, DEMO_USER_EMAIL, generate_id
from app.detection.models import DetectionAlert
from app.preparation.models import PreparedAction, ActionOption
from app.data.users.models import User
from app.data.clients.models import Client

router = APIRouter()


@router.post("/seed/agencyco")
async def seed_agencyco(
    force: bool = Query(False, description="Force reseed if demo user exists"),
    db: AsyncSession = Depends(get_db),
):
    """
    Seed the database with AgencyCo demo data.

    Creates:
    - Demo user (demo@agencyco.com / demo2026)
    - 3 cash accounts ($487K total)
    - 15 clients (retainers, projects, usage-based)
    - 12 expense buckets (payroll, rent, software, etc.)
    - 5 overdue invoices
    - Tax obligation ($22K due in 18 days)
    - 13 weeks of cash events

    Args:
        force: If True, delete existing demo data and reseed
    """
    try:
        result = await seed_agencyco_data(db, force=force)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/seed/agencyco")
async def clear_agencyco(
    db: AsyncSession = Depends(get_db),
):
    """
    Delete all AgencyCo demo data.

    Removes the demo user and all associated data (cascades).
    """
    try:
        result = await clear_demo_data(db)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/seed/status")
async def seed_status(
    db: AsyncSession = Depends(get_db),
):
    """
    Check if demo data exists.
    """
    from sqlalchemy import select
    from app.data.users.models import User

    result = await db.execute(
        select(User).where(User.email == DEMO_USER_EMAIL)
    )
    user = result.scalar_one_or_none()

    if user:
        # Count related entities
        from sqlalchemy import func
        from app.data.clients.models import Client
        from app.data.expenses.models import ExpenseBucket
        from app.data.balances.models import CashAccount
        from app.data.events.models import CashEvent

        clients_count = await db.execute(
            select(func.count(Client.id)).where(Client.user_id == user.id)
        )
        expenses_count = await db.execute(
            select(func.count(ExpenseBucket.id)).where(ExpenseBucket.user_id == user.id)
        )
        accounts_count = await db.execute(
            select(func.count(CashAccount.id)).where(CashAccount.user_id == user.id)
        )
        events_count = await db.execute(
            select(func.count(CashEvent.id)).where(CashEvent.user_id == user.id)
        )

        return {
            "exists": True,
            "user_id": user.id,
            "user_email": user.email,
            "company_name": user.company_name,
            "is_demo": user.is_demo,
            "counts": {
                "clients": clients_count.scalar(),
                "expenses": expenses_count.scalar(),
                "cash_accounts": accounts_count.scalar(),
                "cash_events": events_count.scalar(),
            }
        }

    return {
        "exists": False,
        "user_email": DEMO_USER_EMAIL,
    }


@router.post("/seed/refresh-alerts")
async def refresh_alerts(
    db: AsyncSession = Depends(get_db),
):
    """
    Refresh the detection alerts for the demo user with updated diverse scenarios.
    This only updates alerts, not other data, avoiding cascade issues.
    """
    # Find demo user
    result = await db.execute(
        select(User).where(User.email == DEMO_USER_EMAIL)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Demo user not found")

    user_id = user.id
    today = datetime.now().date()

    # Delete existing alerts and their actions (cascade should handle ActionOptions)
    # First get all alert IDs
    alerts_result = await db.execute(
        select(DetectionAlert.id).where(DetectionAlert.user_id == user_id)
    )
    alert_ids = [row[0] for row in alerts_result.fetchall()]

    # Delete ActionOptions for PreparedActions linked to these alerts
    for alert_id in alert_ids:
        actions_result = await db.execute(
            select(PreparedAction.id).where(PreparedAction.alert_id == alert_id)
        )
        action_ids = [row[0] for row in actions_result.fetchall()]
        for action_id in action_ids:
            await db.execute(delete(ActionOption).where(ActionOption.action_id == action_id))
        await db.execute(delete(PreparedAction).where(PreparedAction.alert_id == alert_id))

    await db.execute(delete(DetectionAlert).where(DetectionAlert.user_id == user_id))
    await db.flush()

    # Get RetailCo client for linking
    clients_result = await db.execute(
        select(Client).where(Client.user_id == user_id)
    )
    clients = clients_result.scalars().all()
    retailco_client = next((c for c in clients if "RetailCo" in c.name), None)

    alerts_created = []

    # Alert 1: Late Payment - RetailCo (14 days, EMERGENCY)
    alert1 = DetectionAlert(
        id=generate_id("alert"),
        user_id=user_id,
        detection_type="late_payment",
        severity="emergency",
        status="active",
        title="Payment 14 Days Overdue: RetailCo Rebrand",
        description="Design milestone payment of $52,500 from RetailCo Rebrand is now 14 days overdue.",
        cash_impact=-52500.00,
        context_data={
            "client_name": "RetailCo Rebrand",
            "invoice_amount": 52500,
            "days_overdue": 14,
        },
        deadline=datetime.combine(today + timedelta(days=1), datetime.min.time()),
    )
    db.add(alert1)
    alerts_created.append(alert1)
    await db.flush()

    # Create prepared action for alert1 - this is the MITIGATION action
    action1 = PreparedAction(
        id=generate_id("action"),
        user_id=user_id,
        alert_id=alert1.id,
        action_type="invoice_follow_up",
        status="pending_approval",
        problem_summary="Send payment reminder to RetailCo",
        problem_context="Draft email ready for overdue $52,500 invoice. Personalized based on your communication history with Sarah.",
        deadline=datetime.combine(today + timedelta(days=1), datetime.min.time()),
    )
    db.add(action1)
    await db.flush()

    option1 = ActionOption(
        id=generate_id("opt"),
        action_id=action1.id,
        is_recommended=True,
        risk_level="medium",
        reasoning=["Client is transactional - firm follow-up appropriate"],
        prepared_content={"email_subject": "Urgent: Invoice Overdue", "email_body": "Hi Sarah, I hope you're doing well..."},
        cash_impact=52500.00,
    )
    db.add(option1)

    # Alert 2: New Hire Impact
    alert2 = DetectionAlert(
        id=generate_id("alert"),
        user_id=user_id,
        detection_type="staffing_change",
        severity="this_week",
        status="active",
        title="New Hire Impact: Senior Developer starts Monday",
        description="Alex Chen starts Monday with $12,500/month salary. Monthly burn increases 8.3%.",
        cash_impact=-16000.00,
        context_data={
            "employee_name": "Alex Chen",
            "role": "Senior Developer",
            "monthly_salary": 12500,
        },
        deadline=datetime.combine(today + timedelta(days=(7 - today.weekday()) % 7), datetime.min.time()),
    )
    db.add(alert2)
    alerts_created.append(alert2)
    await db.flush()

    action2 = PreparedAction(
        id=generate_id("action"),
        user_id=user_id,
        alert_id=alert2.id,
        action_type="payment_batch",
        status="pending_approval",
        problem_summary="Accelerate TechCorp Q1 invoices",
        problem_context="Three invoices totaling $28K ready to send now instead of end of month. Offsets new hire cost impact.",
        deadline=datetime.combine(today + timedelta(days=(7 - today.weekday()) % 7), datetime.min.time()),
    )
    db.add(action2)
    await db.flush()

    option2 = ActionOption(
        id=generate_id("opt"),
        action_id=action2.id,
        is_recommended=True,
        risk_level="low",
        reasoning=["Accelerate Q1 invoicing to offset new hire costs"],
        prepared_content={"invoices": ["TechCorp - Phase 2 milestone", "TechCorp - Design review", "TechCorp - Q1 retainer"]},
        cash_impact=28000.00,
    )
    db.add(option2)

    # Alert 3: Vendor Rate Increase
    alert3 = DetectionAlert(
        id=generate_id("alert"),
        user_id=user_id,
        detection_type="expense_anomaly",
        severity="this_week",
        status="active",
        title="Vendor Rate Increase: Figma renewal +40%",
        description="Figma renewal quote shows 40% increase ($840/month to $1,176/month).",
        cash_impact=-4032.00,
        context_data={
            "vendor_name": "Figma",
            "current_rate": 840,
            "new_rate": 1176,
            "increase_percent": 40,
        },
        deadline=datetime.combine(today + timedelta(days=14), datetime.min.time()),
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
        problem_summary="Reduce Figma seats from 12 to 8",
        problem_context="Analysis shows 4 unused seats. Downgrading before renewal saves $1,400/year. Cancellation request drafted.",
        deadline=datetime.combine(today + timedelta(days=14), datetime.min.time()),
    )
    db.add(action3)
    await db.flush()

    option3 = ActionOption(
        id=generate_id("opt"),
        action_id=action3.id,
        is_recommended=True,
        risk_level="low",
        reasoning=["4 seats unused for 90+ days", "Downgrade captures savings before auto-renewal"],
        prepared_content={"email_subject": "Figma seat reduction request", "inactive_users": ["user3@agency.co", "user7@agency.co", "user9@agency.co", "user11@agency.co"]},
        cash_impact=-1400.00,
    )
    db.add(option3)

    # Alert 4: Early Payment Opportunity
    alert4 = DetectionAlert(
        id=generate_id("alert"),
        user_id=user_id,
        detection_type="cash_optimization",
        severity="upcoming",
        status="active",
        title="Opportunity: Early payment discount from GlobalTech",
        description="GlobalTech offers 2% discount ($3,200 savings) for paying invoice 20 days early.",
        cash_impact=3200.00,
        context_data={
            "client_name": "GlobalTech",
            "invoice_amount": 160000,
            "discount_percent": 2,
            "savings": 3200,
        },
        deadline=datetime.combine(today + timedelta(days=10), datetime.min.time()),
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
        problem_summary="Defer AWS payment by 15 days",
        problem_context="Request payment extension on $8,200 AWS bill to align with expected RetailCo payment. Draft request prepared.",
        deadline=datetime.combine(today + timedelta(days=10), datetime.min.time()),
    )
    db.add(action4)
    await db.flush()

    option4 = ActionOption(
        id=generate_id("opt"),
        action_id=action4.id,
        is_recommended=True,
        risk_level="low",
        reasoning=["Prevents cash crunch next week", "Keeps buffer above safety threshold"],
        prepared_content={"email_subject": "Payment extension request - Invoice #AWS-2026-0142"},
        cash_impact=8200.00,
    )
    db.add(option4)

    # Alert 5: Contract Ending
    alert5 = DetectionAlert(
        id=generate_id("alert"),
        user_id=user_id,
        detection_type="revenue_risk",
        severity="upcoming",
        status="active",
        title="Client Contract Ending: HealthTech Phase 1",
        description="HealthTech Phase 1 contract ends in 3 weeks. No Phase 2 discussions scheduled.",
        cash_impact=-18000.00,
        context_data={
            "client_name": "HealthTech",
            "contract_value": 18000,
            "monthly_value": 6000,
        },
        deadline=datetime.combine(today + timedelta(days=21), datetime.min.time()),
    )
    db.add(alert5)
    alerts_created.append(alert5)
    await db.flush()

    action5 = PreparedAction(
        id=generate_id("action"),
        user_id=user_id,
        alert_id=alert5.id,
        action_type="email",
        status="pending_approval",
        problem_summary="Schedule HealthTech Phase 2 call",
        problem_context="Phase 1 ends in 3 weeks. Calendar invite drafted for Phase 2 scoping to secure the $18K follow-on.",
        deadline=datetime.combine(today + timedelta(days=7), datetime.min.time()),
    )
    db.add(action5)
    await db.flush()

    option5 = ActionOption(
        id=generate_id("opt"),
        action_id=action5.id,
        is_recommended=True,
        risk_level="low",
        reasoning=["Proactive outreach increases Phase 2 close rate by 40%", "Early scheduling locks in their budget cycle"],
        prepared_content={"email_subject": "Phase 2 Planning Discussion", "calendar_invite": True},
        cash_impact=18000.00,
    )
    db.add(option5)

    # Alert 6: VAT accumulation (standalone action - not linked to alert)
    # This is a proactive action, not a response to a risk
    action6 = PreparedAction(
        id=generate_id("action"),
        user_id=user_id,
        alert_id=None,  # No linked alert - this is a proactive recommendation
        action_type="transfer",
        status="pending_approval",
        problem_summary="Sweep $18.4K VAT to reserve account",
        problem_context="Move accumulated VAT from last month's client payments to your tax reserve. Prevents accidental spending of funds owed to HMRC.",
        deadline=datetime.combine(today + timedelta(days=3), datetime.min.time()),
    )
    db.add(action6)
    await db.flush()

    option6 = ActionOption(
        id=generate_id("opt"),
        action_id=action6.id,
        is_recommended=True,
        risk_level="low",
        reasoning=["$92K collected this month", "20% ($18.4K) is VAT that needs to be set aside", "Q1 filing deadline approaching"],
        prepared_content={"transfer_amount": 18400, "from_account": "Operating", "to_account": "Tax Reserve"},
        cash_impact=-18400.00,
    )
    db.add(option6)

    await db.commit()

    return {
        "success": True,
        "alerts_created": len(alerts_created),
        "alerts": [
            {"id": a.id, "title": a.title, "severity": a.severity}
            for a in alerts_created
        ],
    }
