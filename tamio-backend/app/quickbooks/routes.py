"""QuickBooks API Routes.

Endpoints:
- GET /quickbooks/status - Check connection status
- GET /quickbooks/connect - Start OAuth flow
- GET /quickbooks/callback - OAuth callback
- POST /quickbooks/disconnect - Disconnect QuickBooks
- POST /quickbooks/sync - Sync data from QuickBooks
- GET /quickbooks/preview - Preview data before sync
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database import get_db
from app.config import settings
from app.quickbooks import schemas
from app.quickbooks.models import QuickBooksConnection, QuickBooksSyncLog
from app.quickbooks.client import (
    get_authorization_url,
    generate_state,
    exchange_code_for_tokens,
    get_valid_connection,
    QuickBooksClient,
)
from app.quickbooks.sync import sync_quickbooks_data, analyze_payment_behavior


router = APIRouter()

# In-memory state storage (use Redis in production)
_oauth_states: dict = {}


# ============================================================================
# CONNECTION STATUS
# ============================================================================

@router.get("/status", response_model=schemas.QuickBooksConnectionStatus)
async def get_quickbooks_status(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current QuickBooks connection status for a user.
    """
    result = await db.execute(
        select(QuickBooksConnection).where(QuickBooksConnection.user_id == user_id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        return schemas.QuickBooksConnectionStatus(
            is_connected=False
        )

    return schemas.QuickBooksConnectionStatus(
        is_connected=connection.is_active,
        company_name=connection.company_name,
        realm_id=connection.realm_id,
        last_sync_at=connection.last_sync_at,
        token_expires_at=connection.token_expires_at,
        refresh_token_expires_at=connection.refresh_token_expires_at,
        sync_error=connection.sync_error
    )


# ============================================================================
# OAUTH FLOW
# ============================================================================

@router.get("/connect")
async def connect_quickbooks(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Start the QuickBooks OAuth flow.
    Returns the authorization URL to redirect the user to.
    """
    if not settings.QUICKBOOKS_CLIENT_ID or not settings.QUICKBOOKS_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="QuickBooks credentials not configured. Please set QUICKBOOKS_CLIENT_ID and QUICKBOOKS_CLIENT_SECRET."
        )

    # Generate state with user_id embedded
    state = generate_state()
    _oauth_states[state] = {
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc)
    }

    auth_url = get_authorization_url(state)

    return schemas.QuickBooksAuthUrl(
        auth_url=auth_url,
        state=state
    )


@router.get("/callback")
async def quickbooks_callback(
    code: str = Query(...),
    state: str = Query(...),
    realmId: str = Query(...),  # QuickBooks passes company ID as realmId
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth callback endpoint.
    Exchanges the authorization code for tokens and stores the connection.
    """
    # Validate state
    state_data = _oauth_states.pop(state, None)
    if not state_data:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state parameter"
        )

    user_id = state_data["user_id"]

    try:
        # Exchange code for tokens
        tokens = await exchange_code_for_tokens(code, realmId)

        # Check for existing connection
        result = await db.execute(
            select(QuickBooksConnection).where(QuickBooksConnection.user_id == user_id)
        )
        connection = result.scalar_one_or_none()

        # Calculate token expiry times
        access_token_expires = datetime.now(timezone.utc) + timedelta(seconds=tokens.get("expires_in", 3600))
        # QuickBooks refresh tokens expire in 100 days
        refresh_token_expires = datetime.now(timezone.utc) + timedelta(days=100)

        if connection:
            # Update existing connection
            connection.realm_id = realmId
            connection.access_token = tokens["access_token"]
            connection.refresh_token = tokens.get("refresh_token")
            connection.token_expires_at = access_token_expires
            connection.refresh_token_expires_at = refresh_token_expires
            connection.is_active = True
            connection.sync_error = None
        else:
            # Create new connection
            connection = QuickBooksConnection(
                user_id=user_id,
                realm_id=realmId,
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token"),
                token_expires_at=access_token_expires,
                refresh_token_expires_at=refresh_token_expires,
                is_active=True
            )
            db.add(connection)

        await db.commit()

        # Fetch company info to get the name
        try:
            await db.refresh(connection)
            qb_client = QuickBooksClient(connection)
            company_info = await qb_client.get_company_info()
            connection.company_name = company_info.get("company_name", "QuickBooks Company")
            await db.commit()
        except Exception:
            # If we can't get company info, that's okay - continue with the connection
            pass

        # Auto-sync data after successful connection
        try:
            await sync_quickbooks_data(db=db, user_id=user_id, sync_type="full")
        except Exception as sync_err:
            # Log but don't fail - user can manually sync later
            print(f"Auto-sync failed after QuickBooks connection: {sync_err}")

        # Mark onboarding as complete
        try:
            from app.data import models
            user_result = await db.execute(
                select(models.User).where(models.User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                user.has_completed_onboarding = True
                await db.commit()
        except Exception:
            pass

        # Redirect to frontend with success
        company_name = connection.company_name or "QuickBooks"
        frontend_url = f"{settings.FRONTEND_URL}?quickbooks_connected=true&company={company_name}"
        return RedirectResponse(url=frontend_url)

    except Exception as e:
        # Redirect to frontend with error
        frontend_url = f"{settings.FRONTEND_URL}?quickbooks_error={str(e)}"
        return RedirectResponse(url=frontend_url)


@router.post("/disconnect")
async def disconnect_quickbooks(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Disconnect QuickBooks integration for a user.
    """
    result = await db.execute(
        select(QuickBooksConnection).where(QuickBooksConnection.user_id == user_id)
    )
    connection = result.scalar_one_or_none()

    if connection:
        connection.is_active = False
        connection.access_token = None
        connection.refresh_token = None
        await db.commit()

    return {"success": True, "message": "QuickBooks disconnected successfully"}


# ============================================================================
# DATA SYNC
# ============================================================================

@router.post("/sync", response_model=schemas.QuickBooksSyncResult)
async def sync_from_quickbooks(
    request: schemas.QuickBooksSyncRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Sync data from QuickBooks to Tamio.

    Sync types:
    - "full": Sync all data (customers, invoices, vendors, bills)
    - "incremental": Only sync changes since last sync
    - "invoices": Only sync invoices
    - "customers": Only sync customers
    """
    result = await sync_quickbooks_data(
        db=db,
        user_id=request.user_id,
        sync_type=request.sync_type
    )

    return schemas.QuickBooksSyncResult(**result)


@router.get("/preview")
async def preview_quickbooks_data(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Preview data from QuickBooks before syncing.
    Returns a summary of what would be imported.
    """
    import traceback

    connection = await get_valid_connection(db, user_id)
    if not connection:
        raise HTTPException(
            status_code=400,
            detail="No active QuickBooks connection. Please connect to QuickBooks first."
        )

    try:
        qb_client = QuickBooksClient(connection)

        # Get data with error handling for each call
        invoices = []
        customers = []
        vendors = []
        bills = []
        company_info = {}
        bank_accounts = []

        try:
            company_info = await qb_client.get_company_info()
        except Exception as err:
            print(f"Error getting company info: {err}")
            traceback.print_exc()

        try:
            invoices = await qb_client.get_outstanding_invoices()
        except Exception as err:
            print(f"Error getting invoices: {err}")
            traceback.print_exc()

        try:
            customers = await qb_client.get_customers()
        except Exception as err:
            print(f"Error getting customers: {err}")
            traceback.print_exc()

        try:
            vendors = await qb_client.get_vendors()
        except Exception as err:
            print(f"Error getting vendors: {err}")
            traceback.print_exc()

        try:
            bills = await qb_client.get_outstanding_bills()
        except Exception as err:
            print(f"Error getting bills: {err}")
            traceback.print_exc()

        try:
            bank_accounts = await qb_client.get_bank_accounts()
        except Exception as err:
            print(f"Error getting bank accounts: {err}")
            traceback.print_exc()

        # Calculate totals
        total_receivables = sum(i.get("balance", 0) for i in invoices)
        total_payables = sum(b.get("balance", 0) for b in bills)
        total_bank_balance = sum(a.get("current_balance", 0) for a in bank_accounts)

        return {
            "company_info": company_info,
            "summary": {
                "customers": len(customers),
                "outstanding_invoices": len(invoices),
                "receivables_total": total_receivables,
                "vendors": len(vendors),
                "outstanding_bills": len(bills),
                "payables_total": total_payables,
            },
            "bank_summary": {
                "accounts": bank_accounts,
                "total_balance": total_bank_balance
            },
            "customers": customers[:10],
            "invoices": invoices[:10],
            "vendors": vendors[:10],
            "bills": bills[:10],
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching QuickBooks data: {str(e)}"
        )


# ============================================================================
# ANALYTICS
# ============================================================================

@router.get("/payment-analysis")
async def get_payment_analysis(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze payment behavior from QuickBooks aged receivables.
    """
    connection = await get_valid_connection(db, user_id)
    if not connection:
        raise HTTPException(
            status_code=400,
            detail="No active QuickBooks connection."
        )

    try:
        qb_client = QuickBooksClient(connection)
        results = await analyze_payment_behavior(db, user_id, qb_client)

        await db.commit()

        return results

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing payment behavior: {str(e)}"
        )


# ============================================================================
# SYNC HISTORY
# ============================================================================

@router.get("/sync-history")
async def get_sync_history(
    user_id: str = Query(...),
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get sync history for a user.
    """
    result = await db.execute(
        select(QuickBooksSyncLog)
        .where(QuickBooksSyncLog.user_id == user_id)
        .order_by(QuickBooksSyncLog.started_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    return {
        "sync_logs": [
            {
                "id": log.id,
                "sync_type": log.sync_type,
                "status": log.status,
                "records_fetched": log.records_fetched,
                "records_created": log.records_created,
                "records_updated": log.records_updated,
                "error_message": log.error_message,
                "started_at": log.started_at,
                "completed_at": log.completed_at,
            }
            for log in logs
        ]
    }
