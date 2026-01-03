"""Pydantic schemas for QuickBooks integration."""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime


# ============================================================================
# CONNECTION SCHEMAS
# ============================================================================

class QuickBooksConnectionStatus(BaseModel):
    """Status of QuickBooks connection."""
    is_connected: bool
    company_name: Optional[str] = None
    realm_id: Optional[str] = None
    last_sync_at: Optional[datetime] = None
    token_expires_at: Optional[datetime] = None
    refresh_token_expires_at: Optional[datetime] = None
    sync_error: Optional[str] = None


class QuickBooksAuthUrl(BaseModel):
    """Authorization URL for OAuth flow."""
    auth_url: str
    state: str


class QuickBooksCallbackRequest(BaseModel):
    """OAuth callback parameters."""
    code: str
    state: str
    realm_id: str  # QuickBooks company ID


class QuickBooksTokenResponse(BaseModel):
    """Token response after OAuth."""
    success: bool
    message: str
    company_name: Optional[str] = None


# ============================================================================
# SYNC SCHEMAS
# ============================================================================

class QuickBooksSyncRequest(BaseModel):
    """Request to sync data from QuickBooks."""
    user_id: str
    sync_type: str = "full"  # "full" | "incremental" | "invoices" | "customers"


class QuickBooksSyncResult(BaseModel):
    """Result of a sync operation."""
    success: bool
    message: str
    records_fetched: Dict[str, int] = {}
    records_created: Dict[str, int] = {}
    records_updated: Dict[str, int] = {}
    errors: List[str] = []


# ============================================================================
# QUICKBOOKS DATA SCHEMAS (for API responses)
# ============================================================================

class QuickBooksInvoiceSummary(BaseModel):
    """Summary of a QuickBooks invoice."""
    invoice_id: str
    doc_number: Optional[str] = None
    customer_name: str
    customer_id: str
    status: str  # Open, Paid, Overdue, etc.
    balance: float  # Amount still due
    total_amount: float
    currency: str
    due_date: Optional[datetime] = None
    txn_date: Optional[datetime] = None


class QuickBooksCustomerSummary(BaseModel):
    """Summary of a QuickBooks customer."""
    customer_id: str
    display_name: str
    company_name: Optional[str] = None
    email: Optional[str] = None
    balance: float = 0  # Outstanding balance
    currency: Optional[str] = None
    is_active: bool = True


class QuickBooksVendorSummary(BaseModel):
    """Summary of a QuickBooks vendor (supplier)."""
    vendor_id: str
    display_name: str
    company_name: Optional[str] = None
    email: Optional[str] = None
    balance: float = 0  # Outstanding balance
    currency: Optional[str] = None
    is_active: bool = True


class QuickBooksBillSummary(BaseModel):
    """Summary of a QuickBooks bill (accounts payable)."""
    bill_id: str
    doc_number: Optional[str] = None
    vendor_name: str
    vendor_id: str
    status: str
    balance: float
    total_amount: float
    currency: str
    due_date: Optional[datetime] = None
    txn_date: Optional[datetime] = None


class QuickBooksCompanyInfo(BaseModel):
    """QuickBooks company info."""
    company_id: str
    company_name: str
    legal_name: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
