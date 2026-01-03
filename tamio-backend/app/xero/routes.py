"""Xero API Routes.

Endpoints:
- GET /xero/status - Check connection status
- GET /xero/connect - Start OAuth flow
- GET /xero/callback - OAuth callback
- POST /xero/disconnect - Disconnect Xero
- POST /xero/sync - Sync data from Xero
- GET /xero/preview - Preview data before sync
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database import get_db
from app.config import settings
from app.xero import schemas
from app.xero.models import XeroConnection, XeroSyncLog
from app.xero.client import (
    get_authorization_url,
    generate_state,
    exchange_code_for_tokens,
    get_xero_tenants,
    get_valid_connection,
    XeroClient,
)
from app.xero.sync import sync_xero_data, analyze_payment_behavior


router = APIRouter()

# In-memory state storage (use Redis in production)
_oauth_states: dict = {}


# ============================================================================
# CONNECTION STATUS
# ============================================================================

@router.get("/status", response_model=schemas.XeroConnectionStatus)
async def get_xero_status(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current Xero connection status for a user.
    """
    result = await db.execute(
        select(XeroConnection).where(XeroConnection.user_id == user_id)
    )
    connection = result.scalar_one_or_none()

    if not connection:
        return schemas.XeroConnectionStatus(
            is_connected=False
        )

    return schemas.XeroConnectionStatus(
        is_connected=connection.is_active,
        tenant_name=connection.tenant_name,
        tenant_id=connection.tenant_id,
        last_sync_at=connection.last_sync_at,
        token_expires_at=connection.token_expires_at,
        sync_error=connection.sync_error
    )


# ============================================================================
# OAUTH FLOW
# ============================================================================

@router.get("/connect")
async def connect_xero(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Start the Xero OAuth flow.
    Returns the authorization URL to redirect the user to.
    """
    if not settings.XERO_CLIENT_ID or not settings.XERO_CLIENT_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Xero credentials not configured. Please set XERO_CLIENT_ID and XERO_CLIENT_SECRET."
        )

    # Generate state with user_id embedded
    state = generate_state()
    _oauth_states[state] = {
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc)
    }

    auth_url = get_authorization_url(state)

    return schemas.XeroAuthUrl(
        auth_url=auth_url,
        state=state
    )


@router.get("/callback")
async def xero_callback(
    code: str = Query(...),
    state: str = Query(...),
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
        tokens = await exchange_code_for_tokens(code)

        # Get connected tenants
        tenants = await get_xero_tenants(tokens["access_token"])

        if not tenants:
            raise HTTPException(
                status_code=400,
                detail="No Xero organizations found. Please ensure you selected an organization during authorization."
            )

        # Use the first tenant (most users have one organization)
        tenant = tenants[0]

        # Check for existing connection
        result = await db.execute(
            select(XeroConnection).where(XeroConnection.user_id == user_id)
        )
        connection = result.scalar_one_or_none()

        if connection:
            # Update existing connection
            connection.tenant_id = tenant["tenantId"]
            connection.tenant_name = tenant.get("tenantName", "Unknown Organization")
            connection.access_token = tokens["access_token"]
            connection.refresh_token = tokens.get("refresh_token")
            connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
            connection.scopes = tokens.get("scope", settings.XERO_SCOPES)
            connection.id_token = tokens.get("id_token")
            connection.is_active = True
            connection.sync_error = None
        else:
            # Create new connection
            connection = XeroConnection(
                user_id=user_id,
                tenant_id=tenant["tenantId"],
                tenant_name=tenant.get("tenantName", "Unknown Organization"),
                access_token=tokens["access_token"],
                refresh_token=tokens.get("refresh_token"),
                token_expires_at=datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"]),
                scopes=tokens.get("scope", settings.XERO_SCOPES),
                id_token=tokens.get("id_token"),
                is_active=True
            )
            db.add(connection)

        await db.commit()

        # Auto-sync data after successful connection
        try:
            await sync_xero_data(db=db, user_id=user_id, sync_type="full")
        except Exception as sync_err:
            # Log but don't fail - user can manually sync later
            print(f"Auto-sync failed after Xero connection: {sync_err}")

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
        frontend_url = f"{settings.FRONTEND_URL}?xero_connected=true&tenant={tenant.get('tenantName', 'Xero')}"
        return RedirectResponse(url=frontend_url)

    except Exception as e:
        # Redirect to frontend with error
        frontend_url = f"{settings.FRONTEND_URL}?xero_error={str(e)}"
        return RedirectResponse(url=frontend_url)


@router.post("/disconnect")
async def disconnect_xero(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Disconnect Xero integration for a user.
    """
    result = await db.execute(
        select(XeroConnection).where(XeroConnection.user_id == user_id)
    )
    connection = result.scalar_one_or_none()

    if connection:
        connection.is_active = False
        connection.access_token = None
        connection.refresh_token = None
        await db.commit()

    return {"success": True, "message": "Xero disconnected successfully"}


# ============================================================================
# DATA SYNC
# ============================================================================

@router.post("/sync", response_model=schemas.XeroSyncResult)
async def sync_from_xero(
    request: schemas.XeroSyncRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Sync data from Xero to Tamio.

    Sync types:
    - "full": Sync all data (contacts, invoices, repeating invoices)
    - "incremental": Only sync changes since last sync
    - "invoices": Only sync invoices
    - "contacts": Only sync contacts
    """
    result = await sync_xero_data(
        db=db,
        user_id=request.user_id,
        sync_type=request.sync_type
    )

    return schemas.XeroSyncResult(**result)


@router.get("/preview")
async def preview_xero_data(
    user_id: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Preview data from Xero before syncing.
    Returns a summary of what would be imported.
    """
    import traceback

    connection = await get_valid_connection(db, user_id)
    if not connection:
        raise HTTPException(
            status_code=400,
            detail="No active Xero connection. Please connect to Xero first."
        )

    try:
        xero_client = XeroClient(connection)

        # Get data with error handling for each call
        invoices = []
        contacts = []
        repeating = []
        organisation = {}
        bank_summary = {"accounts": [], "total_balance": 0}

        try:
            organisation = xero_client.get_organisation()
        except Exception as org_err:
            print(f"Error getting organisation: {org_err}")
            traceback.print_exc()

        try:
            invoices = xero_client.get_outstanding_invoices()
        except Exception as inv_err:
            print(f"Error getting invoices: {inv_err}")
            traceback.print_exc()

        try:
            contacts = xero_client.get_contacts(is_customer=True)
        except Exception as contact_err:
            print(f"Error getting contacts: {contact_err}")
            traceback.print_exc()

        try:
            repeating = xero_client.get_repeating_invoices()
        except Exception as rep_err:
            print(f"Error getting repeating invoices: {rep_err}")
            traceback.print_exc()

        try:
            bank_summary = xero_client.get_bank_summary()
        except Exception as bank_err:
            print(f"Error getting bank summary: {bank_err}")
            traceback.print_exc()

        # Separate receivables and payables
        receivables = [i for i in invoices if i.get("type") == "ACCREC"]
        payables = [i for i in invoices if i.get("type") == "ACCPAY"]

        # Calculate totals
        total_receivables = sum(i.get("amount_due", 0) for i in receivables)
        total_payables = sum(i.get("amount_due", 0) for i in payables)

        return {
            "organisation": organisation,
            "summary": {
                "contacts": len(contacts),
                "outstanding_invoices": len(invoices),
                "receivables_count": len(receivables),
                "receivables_total": total_receivables,
                "payables_count": len(payables),
                "payables_total": total_payables,
                "repeating_invoices": len(repeating),
            },
            "bank_summary": bank_summary,
            "contacts": contacts[:10],
            "invoices": receivables[:10],
            "bills": payables[:10],
            "repeating_invoices": repeating[:5],
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching Xero data: {str(e)}"
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
    Analyze payment behavior from Xero aged receivables.
    """
    connection = await get_valid_connection(db, user_id)
    if not connection:
        raise HTTPException(
            status_code=400,
            detail="No active Xero connection."
        )

    try:
        xero_client = XeroClient(connection)
        results = await analyze_payment_behavior(db, user_id, xero_client)

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
        select(XeroSyncLog)
        .where(XeroSyncLog.user_id == user_id)
        .order_by(XeroSyncLog.started_at.desc())
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
