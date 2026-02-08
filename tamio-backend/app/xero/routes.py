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
import logging

from app.database import get_db
from app.config import settings
from app.xero import schemas
from app.xero.models import XeroConnection, XeroSyncLog, OAuthState
from app.xero.client import (
    get_authorization_url,
    generate_state,
    exchange_code_for_tokens,
    get_xero_tenants,
    get_valid_connection,
    XeroClient,
)
from app.xero.sync import sync_xero_data, analyze_payment_behavior
from app.auth.dependencies import get_current_user
from app.data.users.models import User


router = APIRouter()
logger = logging.getLogger(__name__)

# OAuth state expiry time (10 minutes)
OAUTH_STATE_EXPIRY_MINUTES = 10


# ============================================================================
# CONNECTION STATUS
# ============================================================================

@router.get("/status", response_model=schemas.XeroConnectionStatus)
async def get_xero_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current Xero connection status for the authenticated user.
    """
    result = await db.execute(
        select(XeroConnection).where(XeroConnection.user_id == current_user.id)
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
    current_user: User = Depends(get_current_user),
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

    # Generate state token
    state = generate_state()

    # Store state in database (replaces in-memory storage - survives restarts)
    oauth_state = OAuthState(
        state=state,
        user_id=current_user.id,
        provider="xero",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=OAUTH_STATE_EXPIRY_MINUTES)
    )
    db.add(oauth_state)
    await db.commit()

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

    Note: This endpoint is called by Xero, so it cannot use JWT auth.
    We validate the state token instead.
    """
    # Look up state in database
    result = await db.execute(
        select(OAuthState).where(OAuthState.state == state)
    )
    state_record = result.scalar_one_or_none()

    if not state_record:
        logger.warning(f"OAuth callback with invalid state: {state[:20]}...")
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired state parameter"
        )

    # Check if state has expired
    if state_record.expires_at < datetime.now(timezone.utc):
        # Clean up expired state
        await db.delete(state_record)
        await db.commit()
        logger.warning(f"OAuth callback with expired state for user: {state_record.user_id}")
        raise HTTPException(
            status_code=400,
            detail="OAuth state has expired. Please try connecting again."
        )

    user_id = state_record.user_id

    # Delete the used state (one-time use)
    await db.delete(state_record)
    await db.commit()

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
        logger.info(f"Xero connected for user: {user_id}, tenant: {tenant.get('tenantName')}")

        # Auto-sync data after successful connection
        try:
            await sync_xero_data(db=db, user_id=user_id, sync_type="full")
            logger.info(f"Auto-sync completed for user: {user_id}")

            # Run detection after initial sync
            try:
                from app.detection.scheduler import run_detections_after_sync
                await run_detections_after_sync(user_id=user_id, sync_type="xero")
            except Exception as detection_err:
                logger.error(f"Post-sync detection failed: {detection_err}")

        except Exception as sync_err:
            # Log but don't fail - user can manually sync later
            logger.error(f"Auto-sync failed after Xero connection: {sync_err}")

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
        logger.error(f"Xero OAuth callback error: {e}")
        # Redirect to frontend with error
        frontend_url = f"{settings.FRONTEND_URL}?xero_error={str(e)}"
        return RedirectResponse(url=frontend_url)


@router.post("/disconnect")
async def disconnect_xero(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Disconnect Xero integration for the authenticated user.
    """
    result = await db.execute(
        select(XeroConnection).where(XeroConnection.user_id == current_user.id)
    )
    connection = result.scalar_one_or_none()

    if connection:
        connection.is_active = False
        connection.access_token = None
        connection.refresh_token = None
        await db.commit()
        logger.info(f"Xero disconnected for user: {current_user.id}")

    return {"success": True, "message": "Xero disconnected successfully"}


# ============================================================================
# DATA SYNC
# ============================================================================

@router.post("/sync", response_model=schemas.XeroSyncResult)
async def sync_from_xero(
    request: schemas.XeroSyncRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Sync data from Xero to Tamio for the authenticated user.

    Sync types:
    - "full": Sync all data (contacts, invoices, repeating invoices)
    - "incremental": Only sync changes since last sync
    - "invoices": Only sync invoices
    - "contacts": Only sync contacts

    After sync completes, automatically runs detection engine to check
    for alerts based on the new data.
    """
    result = await sync_xero_data(
        db=db,
        user_id=current_user.id,  # Use authenticated user, ignore request.user_id
        sync_type=request.sync_type
    )

    # After main sync, also pull outstanding invoices to update billing_config
    if request.sync_type in ["full", "invoices"]:
        from app.xero.sync_service import SyncService
        try:
            sync_service = SyncService(db, current_user.id)
            invoices_processed, clients_updated, invoice_errors = await sync_service.pull_invoices_from_xero()
            result["invoices_synced"] = {
                "processed": invoices_processed,
                "clients_updated": clients_updated,
                "errors": invoice_errors
            }
        except Exception as e:
            logger.error(f"Invoice sync error: {e}")
            result["invoices_synced"] = {"error": str(e)}

    # Run detection engine after sync
    try:
        from app.detection.scheduler import run_detections_after_sync
        detection_result = await run_detections_after_sync(
            user_id=current_user.id,
            sync_type="xero"
        )
        result["detections"] = {
            "alerts_created": detection_result.get("alerts_created", 0),
            "notifications_sent": detection_result.get("notifications_sent", 0),
        }
    except Exception as e:
        logger.error(f"Detection error after sync: {e}")
        result["detections"] = {"error": str(e)}

    return schemas.XeroSyncResult(**result)


@router.post("/sync-invoices")
async def sync_invoices_only(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Sync only outstanding invoices from Xero for the authenticated user.
    """
    from app.xero.sync_service import SyncService

    connection = await get_valid_connection(db, current_user.id)
    if not connection:
        raise HTTPException(
            status_code=400,
            detail="No active Xero connection. Please connect to Xero first."
        )

    sync_service = SyncService(db, current_user.id)
    invoices_processed, clients_updated, errors = await sync_service.pull_invoices_from_xero()

    return {
        "success": len(errors) == 0,
        "invoices_processed": invoices_processed,
        "clients_updated": clients_updated,
        "errors": errors,
        "message": f"Synced {invoices_processed} invoices, updated {clients_updated} clients"
    }


@router.get("/preview")
async def preview_xero_data(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Preview data from Xero before syncing for the authenticated user.
    """
    connection = await get_valid_connection(db, current_user.id)
    if not connection:
        raise HTTPException(
            status_code=400,
            detail="No active Xero connection. Please connect to Xero first."
        )

    try:
        xero_client = XeroClient(connection)

        invoices = []
        contacts = []
        repeating = []
        organisation = {}
        bank_summary = {"accounts": [], "total_balance": 0}

        try:
            organisation = xero_client.get_organisation()
        except Exception as org_err:
            logger.error(f"Error getting organisation: {org_err}")

        try:
            invoices = xero_client.get_outstanding_invoices()
        except Exception as inv_err:
            logger.error(f"Error getting invoices: {inv_err}")

        try:
            contacts = xero_client.get_contacts(is_customer=True)
        except Exception as contact_err:
            logger.error(f"Error getting contacts: {contact_err}")

        try:
            repeating = xero_client.get_repeating_invoices()
        except Exception as rep_err:
            logger.error(f"Error getting repeating invoices: {rep_err}")

        try:
            bank_summary = xero_client.get_bank_summary()
        except Exception as bank_err:
            logger.error(f"Error getting bank summary: {bank_err}")

        receivables = [i for i in invoices if i.get("type") == "ACCREC"]
        payables = [i for i in invoices if i.get("type") == "ACCPAY"]

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
        logger.error(f"Error fetching Xero preview: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching Xero data: {str(e)}"
        )


# ============================================================================
# ANALYTICS
# ============================================================================

@router.get("/payment-analysis")
async def get_payment_analysis(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze payment behavior from Xero aged receivables for the authenticated user.
    """
    connection = await get_valid_connection(db, current_user.id)
    if not connection:
        raise HTTPException(
            status_code=400,
            detail="No active Xero connection."
        )

    try:
        xero_client = XeroClient(connection)
        results = await analyze_payment_behavior(db, current_user.id, xero_client)
        await db.commit()
        return results

    except Exception as e:
        logger.error(f"Payment analysis error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing payment behavior: {str(e)}"
        )


# ============================================================================
# SYNC HISTORY
# ============================================================================

@router.get("/sync-history")
async def get_sync_history(
    current_user: User = Depends(get_current_user),
    limit: int = Query(default=10, le=50),
    db: AsyncSession = Depends(get_db)
):
    """
    Get sync history for the authenticated user.
    """
    result = await db.execute(
        select(XeroSyncLog)
        .where(XeroSyncLog.user_id == current_user.id)
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


# ============================================================================
# CLEANUP (for maintenance)
# ============================================================================

async def cleanup_expired_oauth_states(db: AsyncSession):
    """Remove expired OAuth states from the database."""
    await db.execute(
        delete(OAuthState).where(OAuthState.expires_at < datetime.now(timezone.utc))
    )
    await db.commit()
