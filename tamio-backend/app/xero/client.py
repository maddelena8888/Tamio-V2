"""Xero API client wrapper.

This module provides a wrapper around the xero-python SDK
with automatic token refresh and error handling.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import secrets
import urllib.parse

from xero_python.api_client import ApiClient, Configuration
from xero_python.api_client.oauth2 import OAuth2Token
from xero_python.accounting import AccountingApi
from xero_python.identity import IdentityApi

from app.config import settings
from app.xero.models import XeroConnection


# ============================================================================
# OAUTH2 CONFIGURATION
# ============================================================================

XERO_AUTH_URL = "https://login.xero.com/identity/connect/authorize"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
XERO_CONNECTIONS_URL = "https://api.xero.com/connections"


def get_authorization_url(state: str) -> str:
    """Generate the Xero OAuth2 authorization URL."""
    params = {
        "response_type": "code",
        "client_id": settings.XERO_CLIENT_ID,
        "redirect_uri": settings.XERO_REDIRECT_URI,
        "scope": settings.XERO_SCOPES,
        "state": state,
    }
    return f"{XERO_AUTH_URL}?{urllib.parse.urlencode(params)}"


def generate_state() -> str:
    """Generate a secure random state for OAuth."""
    return secrets.token_urlsafe(32)


# ============================================================================
# API CLIENT FACTORY
# ============================================================================

def create_api_client(access_token: str) -> ApiClient:
    """Create a configured Xero API client."""
    configuration = Configuration()

    # Create OAuth2 token object
    oauth2_token = OAuth2Token(
        client_id=settings.XERO_CLIENT_ID,
        client_secret=settings.XERO_CLIENT_SECRET
    )
    oauth2_token.access_token = access_token

    api_client = ApiClient(
        configuration,
        oauth2_token=oauth2_token
    )

    return api_client


# ============================================================================
# TOKEN MANAGEMENT
# ============================================================================

async def exchange_code_for_tokens(code: str) -> Dict[str, Any]:
    """Exchange authorization code for access and refresh tokens."""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            XERO_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.XERO_REDIRECT_URI,
            },
            auth=(settings.XERO_CLIENT_ID, settings.XERO_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.text}")

        return response.json()


async def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """Refresh the access token using the refresh token."""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            XERO_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            auth=(settings.XERO_CLIENT_ID, settings.XERO_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")

        return response.json()


async def get_xero_tenants(access_token: str) -> List[Dict[str, Any]]:
    """Get list of connected Xero tenants (organizations)."""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.get(
            XERO_CONNECTIONS_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
        )

        if response.status_code != 200:
            raise Exception(f"Failed to get tenants: {response.text}")

        return response.json()


# ============================================================================
# CONNECTION HELPER
# ============================================================================

async def get_valid_connection(
    db: AsyncSession,
    user_id: str
) -> Optional[XeroConnection]:
    """
    Get a valid Xero connection for a user, refreshing token if needed.
    Returns None if no valid connection exists.
    """
    result = await db.execute(
        select(XeroConnection).where(
            XeroConnection.user_id == user_id,
            XeroConnection.is_active == True
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        return None

    # Check if token is expired or about to expire (within 5 minutes)
    if connection.token_expires_at:
        expiry_buffer = datetime.now(timezone.utc) + timedelta(minutes=5)
        if connection.token_expires_at < expiry_buffer:
            # Refresh the token
            try:
                tokens = await refresh_access_token(connection.refresh_token)

                connection.access_token = tokens["access_token"]
                connection.refresh_token = tokens.get("refresh_token", connection.refresh_token)
                connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])

                await db.commit()
                await db.refresh(connection)
            except Exception as e:
                connection.is_active = False
                connection.sync_error = f"Token refresh failed: {str(e)}"
                await db.commit()
                return None

    return connection


# ============================================================================
# XERO API WRAPPER CLASS
# ============================================================================

class XeroClient:
    """High-level Xero API client with automatic token management."""

    def __init__(self, connection: XeroConnection):
        self.connection = connection
        self.api_client = create_api_client(connection.access_token)
        self.accounting_api = AccountingApi(self.api_client)
        self.tenant_id = connection.tenant_id

    # -------------------------------------------------------------------------
    # Organisation
    # -------------------------------------------------------------------------

    def get_organisation(self) -> Dict[str, Any]:
        """Get organisation details."""
        response = self.accounting_api.get_organisations(self.tenant_id)
        if response.organisations:
            org = response.organisations[0]
            return {
                "organisation_id": org.organisation_id,
                "name": org.name,
                "legal_name": org.legal_name,
                "base_currency": org.base_currency,
                "country_code": org.country_code,
                "organisation_type": org.organisation_type,
            }
        return {}

    # -------------------------------------------------------------------------
    # Invoices
    # -------------------------------------------------------------------------

    def get_invoices(
        self,
        status: Optional[str] = None,
        where: Optional[str] = None,
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Get invoices from Xero.

        Args:
            status: Filter by status (DRAFT, SUBMITTED, AUTHORISED, PAID, etc.)
            where: Xero filter expression
            page: Page number for pagination
        """
        invoices = []

        response = self.accounting_api.get_invoices(
            self.tenant_id,
            statuses=[status] if status else None,
            where=where,
            page=page
        )

        for inv in response.invoices or []:
            invoices.append({
                "invoice_id": inv.invoice_id,
                "invoice_number": inv.invoice_number,
                "contact_name": inv.contact.name if inv.contact else None,
                "contact_id": inv.contact.contact_id if inv.contact else None,
                "type": inv.type,  # ACCREC or ACCPAY
                "status": inv.status,
                "amount_due": float(inv.amount_due or 0),
                "total": float(inv.total or 0),
                "currency_code": inv.currency_code,
                "due_date": inv.due_date,
                "date": inv.date,
                "line_items": [
                    {
                        "description": li.description,
                        "quantity": float(li.quantity or 0),
                        "unit_amount": float(li.unit_amount or 0),
                        "line_amount": float(li.line_amount or 0),
                        "account_code": li.account_code,
                    }
                    for li in (inv.line_items or [])
                ]
            })

        return invoices

    def get_outstanding_invoices(self) -> List[Dict[str, Any]]:
        """Get all outstanding (unpaid) invoices."""
        # Get receivables (money coming in)
        receivables = self.get_invoices(where='Type=="ACCREC" AND AmountDue>0')

        # Get payables (money going out)
        payables = self.get_invoices(where='Type=="ACCPAY" AND AmountDue>0')

        return receivables + payables

    # -------------------------------------------------------------------------
    # Contacts
    # -------------------------------------------------------------------------

    def get_contacts(
        self,
        is_customer: Optional[bool] = None,
        is_supplier: Optional[bool] = None,
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """Get contacts from Xero."""
        contacts = []

        where = None
        if is_customer is not None:
            where = f"IsCustomer=={str(is_customer).lower()}"
        elif is_supplier is not None:
            where = f"IsSupplier=={str(is_supplier).lower()}"

        response = self.accounting_api.get_contacts(
            self.tenant_id,
            where=where,
            page=page
        )

        for contact in response.contacts or []:
            # Extract payment terms if available
            payment_terms = None
            if contact.payment_terms and contact.payment_terms.sales:
                payment_terms = contact.payment_terms.sales.day

            contacts.append({
                "contact_id": contact.contact_id,
                "name": contact.name,
                "email": contact.email_address,
                "is_customer": contact.is_customer,
                "is_supplier": contact.is_supplier,
                "default_currency": contact.default_currency,
                "payment_terms": payment_terms,
                "account_number": contact.account_number,
                "contact_status": contact.contact_status,
            })

        return contacts

    # -------------------------------------------------------------------------
    # Bank Transactions
    # -------------------------------------------------------------------------

    def get_bank_transactions(
        self,
        page: int = 1,
        where: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get bank transactions from Xero."""
        transactions = []

        response = self.accounting_api.get_bank_transactions(
            self.tenant_id,
            where=where,
            page=page
        )

        for txn in response.bank_transactions or []:
            transactions.append({
                "transaction_id": txn.bank_transaction_id,
                "type": txn.type,
                "contact_name": txn.contact.name if txn.contact else None,
                "contact_id": txn.contact.contact_id if txn.contact else None,
                "date": txn.date,
                "total": float(txn.total or 0),
                "is_reconciled": txn.is_reconciled,
                "reference": txn.reference,
                "status": txn.status,
            })

        return transactions

    # -------------------------------------------------------------------------
    # Reports
    # -------------------------------------------------------------------------

    def get_aged_receivables(self) -> Dict[str, Any]:
        """Get aged receivables report."""
        response = self.accounting_api.get_report_aged_receivables_by_contact(
            self.tenant_id
        )

        # Parse the report
        contacts = []
        if response.reports and response.reports[0].rows:
            for row in response.reports[0].rows:
                if row.row_type == "Section" and row.rows:
                    for detail_row in row.rows:
                        if detail_row.row_type == "Row" and detail_row.cells:
                            cells = detail_row.cells
                            contacts.append({
                                "contact": cells[0].value if len(cells) > 0 else None,
                                "current": float(cells[1].value or 0) if len(cells) > 1 else 0,
                                "30_days": float(cells[2].value or 0) if len(cells) > 2 else 0,
                                "60_days": float(cells[3].value or 0) if len(cells) > 3 else 0,
                                "90_days": float(cells[4].value or 0) if len(cells) > 4 else 0,
                                "older": float(cells[5].value or 0) if len(cells) > 5 else 0,
                                "total": float(cells[6].value or 0) if len(cells) > 6 else 0,
                            })

        return {"contacts": contacts}

    def get_aged_payables(self) -> Dict[str, Any]:
        """Get aged payables report."""
        response = self.accounting_api.get_report_aged_payables_by_contact(
            self.tenant_id
        )

        # Parse the report (same structure as receivables)
        contacts = []
        if response.reports and response.reports[0].rows:
            for row in response.reports[0].rows:
                if row.row_type == "Section" and row.rows:
                    for detail_row in row.rows:
                        if detail_row.row_type == "Row" and detail_row.cells:
                            cells = detail_row.cells
                            contacts.append({
                                "contact": cells[0].value if len(cells) > 0 else None,
                                "current": float(cells[1].value or 0) if len(cells) > 1 else 0,
                                "30_days": float(cells[2].value or 0) if len(cells) > 2 else 0,
                                "60_days": float(cells[3].value or 0) if len(cells) > 3 else 0,
                                "90_days": float(cells[4].value or 0) if len(cells) > 4 else 0,
                                "older": float(cells[5].value or 0) if len(cells) > 5 else 0,
                                "total": float(cells[6].value or 0) if len(cells) > 6 else 0,
                            })

        return {"contacts": contacts}

    # -------------------------------------------------------------------------
    # Repeating Invoices (for retainers)
    # -------------------------------------------------------------------------

    def get_repeating_invoices(self) -> List[Dict[str, Any]]:
        """Get repeating invoices (recurring revenue/expenses)."""
        invoices = []

        response = self.accounting_api.get_repeating_invoices(self.tenant_id)

        for inv in response.repeating_invoices or []:
            invoices.append({
                "repeating_invoice_id": inv.repeating_invoice_id,
                "contact_name": inv.contact.name if inv.contact else None,
                "contact_id": inv.contact.contact_id if inv.contact else None,
                "type": inv.type,  # ACCREC or ACCPAY
                "status": inv.status,
                "total": float(inv.total or 0),
                "currency_code": inv.currency_code,
                "schedule": {
                    "period": inv.schedule.period if inv.schedule else None,
                    "unit": inv.schedule.unit if inv.schedule else None,
                    "due_date": inv.schedule.due_date if inv.schedule else None,
                    "due_date_type": inv.schedule.due_date_type if inv.schedule else None,
                    "start_date": inv.schedule.start_date if inv.schedule else None,
                    "next_scheduled_date": inv.schedule.next_scheduled_date if inv.schedule else None,
                    "end_date": inv.schedule.end_date if inv.schedule else None,
                } if inv.schedule else None
            })

        return invoices
