#!/usr/bin/env python3
"""
Rebuild Obligations Script.

This script rebuilds all ObligationAgreements and ObligationSchedules from
existing Client and ExpenseBucket records. It is used during the transition
to the canonical obligation-based architecture.

WARNING: This script DELETES all existing obligations and rebuilds from scratch.
Run with --dry-run first to see what would be done.

Usage:
    # Dry run (shows what would be done)
    python -m scripts.rebuild_obligations --dry-run

    # Actually rebuild
    python -m scripts.rebuild_obligations

    # Rebuild for a specific user
    python -m scripts.rebuild_obligations --user-id USER_ID
"""
import asyncio
import argparse
import sys
from datetime import date
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, "/Users/maddelenabergen/Desktop/Tamio VS 2/tamio-backend")

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.data.clients.models import Client
from app.data.expenses.models import ExpenseBucket
from app.data.obligations.models import ObligationAgreement, ObligationSchedule
from app.services.obligations import ObligationService


async def get_stats(db: AsyncSession, user_id: Optional[str] = None):
    """Get current counts for reporting."""
    conditions = []
    if user_id:
        conditions = [Client.user_id == user_id]

    # Clients
    query = select(func.count()).select_from(Client).where(Client.status == "active")
    if conditions:
        query = query.where(*conditions)
    result = await db.execute(query)
    client_count = result.scalar() or 0

    # Expenses
    query = select(func.count()).select_from(ExpenseBucket)
    if user_id:
        query = query.where(ExpenseBucket.user_id == user_id)
    result = await db.execute(query)
    expense_count = result.scalar() or 0

    # Obligations
    query = select(func.count()).select_from(ObligationAgreement)
    if user_id:
        query = query.where(ObligationAgreement.user_id == user_id)
    result = await db.execute(query)
    obligation_count = result.scalar() or 0

    # Schedules
    query = (
        select(func.count())
        .select_from(ObligationSchedule)
        .join(ObligationAgreement)
    )
    if user_id:
        query = query.where(ObligationAgreement.user_id == user_id)
    result = await db.execute(query)
    schedule_count = result.scalar() or 0

    return {
        "clients": client_count,
        "expenses": expense_count,
        "obligations": obligation_count,
        "schedules": schedule_count,
    }


async def rebuild_obligations(
    db: AsyncSession,
    user_id: Optional[str] = None,
    dry_run: bool = True
):
    """
    Rebuild all obligations from clients and expenses.

    Args:
        db: Database session
        user_id: Optional user ID to limit rebuild scope
        dry_run: If True, don't actually delete/create anything
    """
    print("\n" + "=" * 60)
    print("REBUILD OBLIGATIONS SCRIPT")
    print("=" * 60)

    if dry_run:
        print("\n[DRY RUN MODE - No changes will be made]\n")
    else:
        print("\n[LIVE MODE - Changes will be committed]\n")

    # Get current stats
    print("Current State:")
    stats_before = await get_stats(db, user_id)
    print(f"  Active Clients: {stats_before['clients']}")
    print(f"  Expense Buckets: {stats_before['expenses']}")
    print(f"  Obligations: {stats_before['obligations']}")
    print(f"  Schedules: {stats_before['schedules']}")

    if stats_before['obligations'] > 0 or stats_before['schedules'] > 0:
        print(f"\n⚠️  WARNING: {stats_before['obligations']} obligations and "
              f"{stats_before['schedules']} schedules will be DELETED")

    # Step 1: Delete existing obligations and schedules
    print("\n" + "-" * 40)
    print("Step 1: Delete Existing Obligations")
    print("-" * 40)

    if not dry_run:
        # Delete schedules first (foreign key constraint)
        if user_id:
            # Get obligation IDs for this user
            obligation_ids_query = (
                select(ObligationAgreement.id)
                .where(ObligationAgreement.user_id == user_id)
            )
            result = await db.execute(obligation_ids_query)
            obligation_ids = [row[0] for row in result.fetchall()]

            if obligation_ids:
                await db.execute(
                    delete(ObligationSchedule)
                    .where(ObligationSchedule.obligation_id.in_(obligation_ids))
                )
                await db.execute(
                    delete(ObligationAgreement)
                    .where(ObligationAgreement.user_id == user_id)
                )
        else:
            # Delete all
            await db.execute(delete(ObligationSchedule))
            await db.execute(delete(ObligationAgreement))

        await db.commit()
        print("  ✓ Deleted existing obligations and schedules")
    else:
        print("  [Would delete existing obligations and schedules]")

    # Step 2: Get all clients
    print("\n" + "-" * 40)
    print("Step 2: Rebuild from Clients")
    print("-" * 40)

    query = select(Client).where(Client.status == "active")
    if user_id:
        query = query.where(Client.user_id == user_id)

    result = await db.execute(query)
    clients = result.scalars().all()

    obligations_created = 0
    schedules_created = 0

    obligation_service = ObligationService(db)

    for client in clients:
        if dry_run:
            print(f"  [Would create obligation from client: {client.name}]")
            obligations_created += 1
            schedules_created += 3  # Estimate 3 months of schedules
        else:
            try:
                obligation = await obligation_service.create_obligation_from_client(
                    client,
                    auto_generate_schedules=True
                )
                if obligation:
                    # Count schedules created
                    schedule_query = (
                        select(func.count())
                        .select_from(ObligationSchedule)
                        .where(ObligationSchedule.obligation_id == obligation.id)
                    )
                    result = await db.execute(schedule_query)
                    count = result.scalar() or 0

                    print(f"  ✓ Created obligation from client: {client.name} ({count} schedules)")
                    obligations_created += 1
                    schedules_created += count
                else:
                    print(f"  - Skipped client (no revenue): {client.name}")
            except Exception as e:
                print(f"  ✗ Error processing client {client.name}: {e}")

    # Step 3: Get all expense buckets
    print("\n" + "-" * 40)
    print("Step 3: Rebuild from Expense Buckets")
    print("-" * 40)

    query = select(ExpenseBucket)
    if user_id:
        query = query.where(ExpenseBucket.user_id == user_id)

    result = await db.execute(query)
    expenses = result.scalars().all()

    for expense in expenses:
        if dry_run:
            print(f"  [Would create obligation from expense: {expense.name}]")
            obligations_created += 1
            schedules_created += 3  # Estimate 3 months of schedules
        else:
            try:
                obligation = await obligation_service.create_obligation_from_expense(
                    expense,
                    auto_generate_schedules=True
                )
                if obligation:
                    # Count schedules created
                    schedule_query = (
                        select(func.count())
                        .select_from(ObligationSchedule)
                        .where(ObligationSchedule.obligation_id == obligation.id)
                    )
                    result = await db.execute(schedule_query)
                    count = result.scalar() or 0

                    print(f"  ✓ Created obligation from expense: {expense.name} ({count} schedules)")
                    obligations_created += 1
                    schedules_created += count
                else:
                    print(f"  - Skipped expense (no amount): {expense.name}")
            except Exception as e:
                print(f"  ✗ Error processing expense {expense.name}: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    if dry_run:
        print("\n[DRY RUN - No changes made]")
        print(f"\nWould create:")
        print(f"  Obligations: ~{obligations_created}")
        print(f"  Schedules: ~{schedules_created}")
    else:
        print("\n[CHANGES COMMITTED]")

        # Get final stats
        stats_after = await get_stats(db, user_id)

        print(f"\nFinal State:")
        print(f"  Obligations: {stats_after['obligations']} (was {stats_before['obligations']})")
        print(f"  Schedules: {stats_after['schedules']} (was {stats_before['schedules']})")

        print(f"\nCreated:")
        print(f"  Obligations: {obligations_created}")
        print(f"  Schedules: {schedules_created}")

    print("\n" + "=" * 60)
    print("Done!")
    print("=" * 60 + "\n")


async def main():
    parser = argparse.ArgumentParser(
        description="Rebuild obligations from clients and expenses"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--user-id",
        type=str,
        default=None,
        help="Only rebuild for a specific user ID"
    )

    args = parser.parse_args()

    if not args.dry_run:
        print("\n⚠️  WARNING: This will DELETE all existing obligations!")
        confirm = input("Type 'yes' to continue: ")
        if confirm.lower() != 'yes':
            print("Aborted.")
            return

    async with AsyncSessionLocal() as db:
        await rebuild_obligations(
            db,
            user_id=args.user_id,
            dry_run=args.dry_run
        )


if __name__ == "__main__":
    asyncio.run(main())
