"""Pydantic schemas for Xero integration."""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


# ============================================================================
# CONNECTION SCHEMAS
# ============================================================================

class XeroConnectionStatus(BaseModel):
    """Status of Xero connection."""
    is_connected: bool
    tenant_name: Optional[str] = None
    tenant_id: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    token_expires_at: Optional[datetime] = None
    sync_error: Optional[str] = None


class XeroAuthUrl(BaseModel):
    """Authorization URL for OAuth flow."""
    auth_url: str
    state: str


class XeroCallbackRequest(BaseModel):
    """OAuth callback parameters."""
    code: str
    state: str


class XeroTokenResponse(BaseModel):
    """Token response after OAuth."""
    success: bool
    message: str
    tenant_name: Optional[str] = None


# ============================================================================
# SYNC SCHEMAS
# ============================================================================

class XeroSyncRequest(BaseModel):
    """Request to sync data from Xero."""
    user_id: str
    sync_type: str = "full"  # "full" | "incremental" | "invoices" | "contacts"


class XeroSyncResult(BaseModel):
    """Result of a sync operation."""
    success: bool
    message: str
    records_fetched: Dict[str, int] = {}
    records_created: Dict[str, int] = {}
    records_updated: Dict[str, int] = {}
    errors: List[str] = []


# ============================================================================
# XERO DATA SCHEMAS (for API responses)
# ============================================================================

class XeroInvoiceSummary(BaseModel):
    """Summary of a Xero invoice."""
    invoice_id: str
    invoice_number: Optional[str] = None
    contact_name: str
    contact_id: str
    type: str  # "ACCREC" (receivable) or "ACCPAY" (payable)
    status: str
    amount_due: float
    total: float
    currency: str
    due_date: Optional[datetime] = None
    date: Optional[datetime] = None


class XeroContactSummary(BaseModel):
    """Summary of a Xero contact."""
    contact_id: str
    name: str
    email: Optional[str] = None
    is_customer: bool
    is_supplier: bool
    default_currency: Optional[str] = None
    payment_terms: Optional[int] = None  # Days


class XeroBankTransactionSummary(BaseModel):
    """Summary of a Xero bank transaction."""
    transaction_id: str
    type: str
    contact_name: Optional[str] = None
    date: datetime
    amount: float
    is_reconciled: bool
    reference: Optional[str] = None


class XeroOrganisation(BaseModel):
    """Xero organisation info."""
    organisation_id: str
    name: str
    legal_name: Optional[str] = None
    base_currency: str
    country_code: Optional[str] = None
    organisation_type: Optional[str] = None
