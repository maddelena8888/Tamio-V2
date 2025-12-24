"""Development utilities for testing and debugging."""
import asyncio
from datetime import date, timedelta
from decimal import Decimal
from app.database import AsyncSessionLocal
from app.models import User, BankAccount, Client, CashEvent
from app.services.forecast_engine import ForecastEngine
import json


async def create_test_data(email: str = "test@example.com"):
    """
    Create test data for development.

    This creates a user with realistic cash events for testing the forecast.
    """
    async with AsyncSessionLocal() as db:
        # Create user
        user = User(email=email)
        db.add(user)
        await db.commit()
        await db.refresh(user)

        print(f"✅ Created user: {user.id} ({user.email})")

        # Create bank account (starting cash)
        account = BankAccount(
            user_id=user.id,
            account_name="Operating Account",
            current_balance=Decimal("450000.00"),
            currency="USD",
            as_of_date=date.today(),
            source="manual_input",
        )
        db.add(account)

        print(f"✅ Created bank account with ${account.current_balance}")

        # Create clients
        clients_data = [
            {"name": "Client A - Retainer", "type": "retainer"},
            {"name": "Client B - Project", "type": "project"},
            {"name": "Client C - Usage", "type": "usage"},
        ]

        clients = []
        for client_data in clients_data:
            client = Client(
                user_id=user.id,
                name=client_data["name"],
                client_type=client_data["type"],
                source="manual_input",
            )
            db.add(client)
            clients.append(client)

        await db.commit()
        print(f"✅ Created {len(clients)} clients")

        # Create cash events (revenue)
        today = date.today()
        events = []

        # Retainer revenue (recurring monthly)
        for week in range(0, 13, 4):  # Every 4 weeks
            event = CashEvent(
                user_id=user.id,
                date=today + timedelta(weeks=week),
                week_number=week + 1,
                amount=Decimal("25000.00"),
                direction="in",
                event_type="expected_revenue",
                revenue_type="retainer",
                category="retainer",
                client_id=clients[0].id,
                client_name=clients[0].name,
                confidence="high",
                confidence_reason="contract_signed",
                is_recurring=True,
                recurrence_pattern="monthly",
                source="manual_input",
            )
            db.add(event)
            events.append(event)

        # Project milestone payments
        milestones = [
            (2, Decimal("120000.00"), "high", "invoice_issued"),
            (5, Decimal("80000.00"), "medium", "user_estimate"),
            (9, Decimal("120000.00"), "low", "user_estimate"),
        ]

        for week, amount, confidence, reason in milestones:
            event = CashEvent(
                user_id=user.id,
                date=today + timedelta(weeks=week),
                week_number=week + 1,
                amount=amount,
                direction="in",
                event_type="expected_revenue",
                revenue_type="project",
                category="milestone_payment",
                client_id=clients[1].id,
                client_name=clients[1].name,
                confidence=confidence,
                confidence_reason=reason,
                is_recurring=False,
                source="manual_input",
            )
            db.add(event)
            events.append(event)

        # Usage-based revenue (weekly)
        for week in range(1, 13):
            event = CashEvent(
                user_id=user.id,
                date=today + timedelta(weeks=week),
                week_number=week + 1,
                amount=Decimal("5000.00"),
                direction="in",
                event_type="expected_revenue",
                revenue_type="usage",
                category="usage_fees",
                client_id=clients[2].id,
                client_name=clients[2].name,
                confidence="medium",
                confidence_reason="inferred_pattern",
                is_recurring=True,
                recurrence_pattern="weekly",
                source="manual_input",
            )
            db.add(event)
            events.append(event)

        # Obligations (expenses)
        obligations = [
            # Payroll (bi-weekly)
            {
                "name": "Payroll",
                "amount": Decimal("45000.00"),
                "category": "payroll",
                "obligation_type": "fixed",
                "pattern": "bi-weekly",
                "weeks": range(0, 13, 2),
            },
            # Rent (monthly)
            {
                "name": "Office Rent",
                "amount": Decimal("8000.00"),
                "category": "rent",
                "obligation_type": "fixed",
                "pattern": "monthly",
                "weeks": [0, 4, 8, 12],
            },
            # Contractors (monthly)
            {
                "name": "Contractors",
                "amount": Decimal("15000.00"),
                "category": "contractor",
                "obligation_type": "variable",
                "pattern": "monthly",
                "weeks": [2, 6, 10],
            },
            # Software subscriptions (monthly)
            {
                "name": "Software Subscriptions",
                "amount": Decimal("3000.00"),
                "category": "subscription",
                "obligation_type": "discretionary",
                "pattern": "monthly",
                "weeks": [1, 5, 9],
            },
        ]

        for obligation in obligations:
            for week in obligation["weeks"]:
                event = CashEvent(
                    user_id=user.id,
                    date=today + timedelta(weeks=week),
                    week_number=week + 1,
                    amount=obligation["amount"],
                    direction="out",
                    event_type="expected_obligation",
                    category=obligation["category"],
                    obligation_type=obligation["obligation_type"],
                    client_name=obligation["name"],
                    confidence="high",
                    confidence_reason="user_confirmed",
                    is_recurring=True,
                    recurrence_pattern=obligation["pattern"],
                    source="manual_input",
                )
                db.add(event)
                events.append(event)

        await db.commit()
        print(f"✅ Created {len(events)} cash events")

        return user.id


async def get_forecast(user_id: str):
    """Get and print forecast for a user."""
    async with AsyncSessionLocal() as db:
        engine = ForecastEngine(db)
        forecast = await engine.calculate_13_week_forecast(user_id)

        print("\n" + "=" * 80)
        print(f"13-WEEK CASH FORECAST")
        print("=" * 80)
        print(f"Starting Cash: ${forecast.starting_cash:,.2f}")
        print(f"Forecast Start: {forecast.forecast_start_date}")
        print()

        for week in forecast.weeks:
            print(f"Week {week.week_number} ({week.week_start} to {week.week_end})")
            print(f"  Starting: ${week.starting_balance:,.2f}")
            print(f"  Cash In:  +${week.cash_in:,.2f}")
            print(f"  Cash Out: -${week.cash_out:,.2f}")
            print(f"  Net:      ${week.net_change:+,.2f}")
            print(f"  Ending:   ${week.ending_balance:,.2f}")
            print(f"  Events:   {len(week.events)}")
            print()

        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Lowest Cash: Week {forecast.summary.lowest_cash_week} - ${forecast.summary.lowest_cash_amount:,.2f}")
        print(f"Total Cash In: ${forecast.summary.total_cash_in:,.2f}")
        print(f"Total Cash Out: ${forecast.summary.total_cash_out:,.2f}")
        print(f"Runway: {forecast.summary.runway_weeks} weeks")
        print("=" * 80)


async def clear_all_data():
    """Clear all data from database (DEVELOPMENT ONLY)."""
    async with AsyncSessionLocal() as db:
        # Delete in order due to foreign keys
        await db.execute("DELETE FROM cash_events")
        await db.execute("DELETE FROM clients")
        await db.execute("DELETE FROM bank_accounts")
        await db.execute("DELETE FROM users")
        await db.commit()
        print("✅ Cleared all data from database")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage:")
        print("  python dev_utils.py create_test_data [email]")
        print("  python dev_utils.py get_forecast <user_id>")
        print("  python dev_utils.py clear_all")
        sys.exit(1)

    command = sys.argv[1]

    if command == "create_test_data":
        email = sys.argv[2] if len(sys.argv) > 2 else "test@example.com"
        user_id = asyncio.run(create_test_data(email))
        print(f"\n🎉 Test data created! User ID: {user_id}")
        print(f"\nNow run: python dev_utils.py get_forecast {user_id}")

    elif command == "get_forecast":
        if len(sys.argv) < 3:
            print("❌ Please provide user_id")
            sys.exit(1)
        user_id = sys.argv[2]
        asyncio.run(get_forecast(user_id))

    elif command == "clear_all":
        confirm = input("⚠️  Are you sure? This will delete ALL data. Type 'yes' to confirm: ")
        if confirm.lower() == "yes":
            asyncio.run(clear_all_data())
        else:
            print("❌ Cancelled")

    else:
        print(f"❌ Unknown command: {command}")
