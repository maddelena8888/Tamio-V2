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
    # Create OAuth2 token object
    oauth2_token = OAuth2Token(
        client_id=settings.XERO_CLIENT_ID,
        client_secret=settings.XERO_CLIENT_SECRET
    )
    oauth2_token.access_token = access_token

    # Configuration with oauth2_token
    configuration = Configuration(
        oauth2_token=oauth2_token
    )

    api_client = ApiClient(configuration)

    # Set up token getter - required by the SDK for auth
    @api_client.oauth2_token_getter
    def obtain_xero_oauth2_token():
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 1800,  # 30 minutes (Xero default)
            "scope": settings.XERO_SCOPES
        }

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
        ).with_for_update()
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
        statuses: Optional[List[str]] = None,
        where: Optional[str] = None,
        page: int = 1,
        fetch_all: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get invoices from Xero.

        Args:
            statuses: Filter by statuses (DRAFT, SUBMITTED, AUTHORISED, PAID, etc.)
            where: Xero filter expression
            page: Page number for pagination (starting page if fetch_all=True)
            fetch_all: If True, auto-paginate to fetch all matching results
        """
        all_invoices = []
        current_page = page

        while True:
            # Build kwargs to avoid passing None values
            kwargs = {"xero_tenant_id": self.tenant_id, "page": current_page}
            if statuses:
                kwargs["statuses"] = statuses
            if where:
                kwargs["where"] = where

            response = self.accounting_api.get_invoices(**kwargs)
            page_invoices = response.invoices or []
            
            # If no invoices returned, we're done
            if not page_invoices:
                break
                
            all_invoices.extend(page_invoices)
            
            # If we're not fetching all, or if we got fewer than 100 items (default page size), we're done
            if not fetch_all or len(page_invoices) < 100:
                break
                
            current_page += 1

        invoices = []
        for inv in all_invoices:
            # Convert type enum to string if needed
            inv_type = inv.type
            if hasattr(inv_type, 'value'):
                inv_type = inv_type.value

            # Convert status enum to string if needed
            inv_status = inv.status
            if hasattr(inv_status, 'value'):
                inv_status = inv_status.value

            invoices.append({
                "invoice_id": inv.invoice_id,
                "invoice_number": inv.invoice_number,
                "contact_name": inv.contact.name if inv.contact else None,
                "contact_id": inv.contact.contact_id if inv.contact else None,
                "type": inv_type,  # ACCREC or ACCPAY
                "status": inv_status,
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
        # Get all AUTHORISED invoices (outstanding) - these have amount due > 0
        # The statuses filter uses specific status values
        # Fetch ALL pages to ensure we don't miss any outstanding invoices
        all_invoices = self.get_invoices(
            statuses=["AUTHORISED", "SUBMITTED"], 
            fetch_all=True
        )

        # Filter to only those with amount due
        outstanding = [inv for inv in all_invoices if inv["amount_due"] > 0]

        return outstanding

    # -------------------------------------------------------------------------
    # Contacts
    # -------------------------------------------------------------------------

    def get_contacts(
        self,
        is_customer: Optional[bool] = None,
        is_supplier: Optional[bool] = None,
        page: int = 1,
        fetch_all: bool = False
    ) -> List[Dict[str, Any]]:
        """Get contacts from Xero.
        
        Args:
            is_customer: Filter by IsCustomer
            is_supplier: Filter by IsSupplier
            page: Page number
            fetch_all: If True, auto-paginate to fetch all matching results
        """
        all_contacts = []
        current_page = page
        
        while True:
            where = None
            if is_customer is not None:
                where = f"IsCustomer=={str(is_customer).lower()}"
            elif is_supplier is not None:
                where = f"IsSupplier=={str(is_supplier).lower()}"

            response = self.accounting_api.get_contacts(
                self.tenant_id,
                where=where,
                page=current_page
            )
            
            page_contacts = response.contacts or []
            if not page_contacts:
                break
                
            all_contacts.extend(page_contacts)
            
            if not fetch_all or len(page_contacts) < 100:
                break
                
            current_page += 1

        contacts = []
        for contact in all_contacts:
            # Extract payment terms if available
            payment_terms = None
            if contact.payment_terms and contact.payment_terms.sales:
                payment_terms = contact.payment_terms.sales.day

            # Convert CurrencyCode enum to string if present
            currency = None
            if contact.default_currency:
                currency = contact.default_currency.value if hasattr(contact.default_currency, 'value') else str(contact.default_currency)

            contacts.append({
                "contact_id": contact.contact_id,
                "name": contact.name,
                "email": contact.email_address,
                "is_customer": contact.is_customer,
                "is_supplier": contact.is_supplier,
                "default_currency": currency,
                "payment_terms": payment_terms,
                "account_number": contact.account_number,
                "contact_status": contact.contact_status,
            })

        return contacts

    # -------------------------------------------------------------------------
    # Bank Accounts
    # -------------------------------------------------------------------------

    def get_bank_accounts(self) -> List[Dict[str, Any]]:
        """Get bank accounts from Xero with their current balances."""
        accounts = []

        # Get accounts of type BANK
        response = self.accounting_api.get_accounts(
            self.tenant_id,
            where='Type=="BANK"'
        )

        for account in response.accounts or []:
            # Convert currency enum to string if needed
            currency = account.currency_code
            if hasattr(currency, 'value'):
                currency = currency.value

            accounts.append({
                "account_id": account.account_id,
                "name": account.name,
                "code": account.code,
                "type": account.type,
                "bank_account_number": account.bank_account_number,
                "currency_code": currency,
                "status": account.status,
                # Note: Balance requires a separate report call
            })

        return accounts

    def get_bank_summary(self) -> Dict[str, Any]:
        """Get bank account summary with balances from the Bank Summary report."""
        try:
            response = self.accounting_api.get_report_bank_summary(self.tenant_id)

            accounts = []
            total_balance = 0

            if response.reports and response.reports[0].rows:
                for row in response.reports[0].rows:
                    # Check for SECTION row type (can be enum or string)
                    row_type_str = str(row.row_type).upper() if row.row_type else ""
                    is_section = "SECTION" in row_type_str

                    if is_section and row.rows:
                        for detail_row in row.rows:
                            detail_type_str = str(detail_row.row_type).upper() if detail_row.row_type else ""
                            # Look for ROW type but not SUMMARYROW
                            is_data_row = "ROW" in detail_type_str and "SUMMARY" not in detail_type_str

                            if is_data_row and detail_row.cells:
                                cells = detail_row.cells
                                account_name = cells[0].value if len(cells) > 0 else None
                                # The balance is in the last column ("Balance in Xero")
                                balance = 0
                                if len(cells) > 1:
                                    try:
                                        balance = float(cells[-1].value or 0)
                                    except (ValueError, TypeError):
                                        balance = 0

                                if account_name and account_name.lower() not in ['total', '']:
                                    accounts.append({
                                        "name": account_name,
                                        "balance": balance
                                    })
                                    total_balance += balance

            return {
                "accounts": accounts,
                "total_balance": total_balance
            }
        except Exception as e:
            # If report fails, return empty (but log the error)
            print(f"Error getting bank summary: {e}")
            return {"accounts": [], "total_balance": 0}

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

    # -------------------------------------------------------------------------
    # Chart of Accounts
    # -------------------------------------------------------------------------

    def get_chart_of_accounts(self) -> List[Dict[str, Any]]:
        """
        Get chart of accounts from Xero.

        Returns account codes with their names, types, and classes
        for categorizing expenses.
        """
        accounts = []

        response = self.accounting_api.get_accounts(self.tenant_id)

        for account in response.accounts or []:
            # Convert enums to strings
            account_type = account.type
            if hasattr(account_type, 'value'):
                account_type = account_type.value

            account_class = account.account_class if hasattr(account, 'account_class') else None
            if hasattr(account_class, 'value'):
                account_class = account_class.value

            status = account.status
            if hasattr(status, 'value'):
                status = status.value

            accounts.append({
                "account_id": account.account_id,
                "code": account.code,
                "name": account.name,
                "type": account_type,  # BANK, EXPENSE, REVENUE, etc.
                "account_class": account_class,  # EXPENSE, ASSET, LIABILITY, etc.
                "status": status,
                "description": account.description if hasattr(account, 'description') else None,
                "tax_type": account.tax_type if hasattr(account, 'tax_type') else None,
            })

        return accounts

    # =========================================================================
    # WRITE OPERATIONS - Bi-directional Sync (Tamio → Xero)
    # =========================================================================

    # -------------------------------------------------------------------------
    # Contacts (Customers & Suppliers)
    # -------------------------------------------------------------------------

    def create_contact(
        self,
        name: str,
        is_customer: bool = False,
        is_supplier: bool = False,
        email: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new contact in Xero.

        Args:
            name: Contact name (required)
            is_customer: Mark as customer (for clients/revenue)
            is_supplier: Mark as supplier (for expenses)
            email: Optional email address
            currency: Optional default currency (ISO 4217)

        Returns:
            Created contact data including contact_id
        """
        from xero_python.accounting import Contact, CurrencyCode

        contact = Contact(
            name=name,
            is_customer=is_customer,
            is_supplier=is_supplier,
        )

        if email:
            contact.email_address = email
        if currency:
            # Convert string currency code to Xero's CurrencyCode enum
            try:
                contact.default_currency = CurrencyCode(currency)
            except ValueError:
                # If currency is not a valid CurrencyCode, skip setting it
                pass

        response = self.accounting_api.create_contacts(
            self.tenant_id,
            contacts={"contacts": [contact]}
        )

        created = response.contacts[0] if response.contacts else None
        if not created:
            raise Exception("Failed to create contact in Xero")

        return {
            "contact_id": created.contact_id,
            "name": created.name,
            "is_customer": created.is_customer,
            "is_supplier": created.is_supplier,
            "email": created.email_address,
            "default_currency": str(created.default_currency) if created.default_currency else None,
        }

    def update_contact(
        self,
        contact_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None,
        is_customer: Optional[bool] = None,
        is_supplier: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing contact in Xero.

        Args:
            contact_id: Xero contact UUID
            name: Updated name
            email: Updated email
            is_customer: Update customer flag
            is_supplier: Update supplier flag

        Returns:
            Updated contact data
        """
        from xero_python.accounting import Contact

        contact = Contact(contact_id=contact_id)

        if name is not None:
            contact.name = name
        if email is not None:
            contact.email_address = email
        if is_customer is not None:
            contact.is_customer = is_customer
        if is_supplier is not None:
            contact.is_supplier = is_supplier

        response = self.accounting_api.update_contact(
            self.tenant_id,
            contact_id=contact_id,
            contacts={"contacts": [contact]}
        )

        updated = response.contacts[0] if response.contacts else None
        if not updated:
            raise Exception(f"Failed to update contact {contact_id} in Xero")

        return {
            "contact_id": updated.contact_id,
            "name": updated.name,
            "is_customer": updated.is_customer,
            "is_supplier": updated.is_supplier,
            "email": updated.email_address,
        }

    def archive_contact(self, contact_id: str) -> Dict[str, Any]:
        """
        Archive a contact in Xero (soft delete).

        Note: Xero doesn't allow deleting contacts with transactions.
        Archiving hides them from active lists but preserves history.
        """
        from xero_python.accounting import Contact

        contact = Contact(
            contact_id=contact_id,
            contact_status="ARCHIVED"
        )

        response = self.accounting_api.update_contact(
            self.tenant_id,
            contact_id=contact_id,
            contacts={"contacts": [contact]}
        )

        return {"contact_id": contact_id, "status": "archived"}

    # -------------------------------------------------------------------------
    # Invoices (for Clients - Accounts Receivable)
    # -------------------------------------------------------------------------

    def create_invoice(
        self,
        contact_id: str,
        line_items: List[Dict[str, Any]],
        due_date: Optional[datetime] = None,
        reference: Optional[str] = None,
        status: str = "DRAFT",
    ) -> Dict[str, Any]:
        """
        Create an invoice (Accounts Receivable) in Xero.

        Args:
            contact_id: Xero contact UUID
            line_items: List of {"description": str, "quantity": float, "unit_amount": float, "account_code": str}
            due_date: Optional due date
            reference: Optional reference number
            status: DRAFT, SUBMITTED, or AUTHORISED

        Returns:
            Created invoice data including invoice_id
        """
        from xero_python.accounting import Invoice, LineItem, Contact

        xero_line_items = []
        for item in line_items:
            li = LineItem(
                description=item.get("description", ""),
                quantity=item.get("quantity", 1),
                unit_amount=item.get("unit_amount", 0),
                account_code=item.get("account_code", "200"),  # Default to Sales account
            )
            xero_line_items.append(li)

        invoice = Invoice(
            type="ACCREC",  # Accounts Receivable
            contact=Contact(contact_id=contact_id),
            line_items=xero_line_items,
            status=status,
        )

        if due_date:
            invoice.due_date = due_date
        if reference:
            invoice.reference = reference

        response = self.accounting_api.create_invoices(
            self.tenant_id,
            invoices={"invoices": [invoice]}
        )

        created = response.invoices[0] if response.invoices else None
        if not created:
            raise Exception("Failed to create invoice in Xero")

        return {
            "invoice_id": created.invoice_id,
            "invoice_number": created.invoice_number,
            "contact_id": contact_id,
            "total": float(created.total or 0),
            "status": str(created.status),
            "due_date": created.due_date,
        }

    # -------------------------------------------------------------------------
    # Bills (for Expenses - Accounts Payable)
    # -------------------------------------------------------------------------

    def create_bill(
        self,
        contact_id: str,
        line_items: List[Dict[str, Any]],
        due_date: Optional[datetime] = None,
        reference: Optional[str] = None,
        status: str = "DRAFT",
    ) -> Dict[str, Any]:
        """
        Create a bill (Accounts Payable) in Xero.

        Args:
            contact_id: Xero supplier contact UUID
            line_items: List of {"description": str, "quantity": float, "unit_amount": float, "account_code": str}
            due_date: Optional due date
            reference: Optional reference/PO number
            status: DRAFT, SUBMITTED, or AUTHORISED

        Returns:
            Created bill data including invoice_id (bills use Invoice type in Xero)
        """
        from xero_python.accounting import Invoice, LineItem, Contact

        xero_line_items = []
        for item in line_items:
            li = LineItem(
                description=item.get("description", ""),
                quantity=item.get("quantity", 1),
                unit_amount=item.get("unit_amount", 0),
                account_code=item.get("account_code", "400"),  # Default to General Expenses
            )
            xero_line_items.append(li)

        bill = Invoice(
            type="ACCPAY",  # Accounts Payable (Bill)
            contact=Contact(contact_id=contact_id),
            line_items=xero_line_items,
            status=status,
        )

        if due_date:
            bill.due_date = due_date
        if reference:
            bill.reference = reference

        response = self.accounting_api.create_invoices(
            self.tenant_id,
            invoices={"invoices": [bill]}
        )

        created = response.invoices[0] if response.invoices else None
        if not created:
            raise Exception("Failed to create bill in Xero")

        return {
            "bill_id": created.invoice_id,
            "bill_number": created.invoice_number,
            "contact_id": contact_id,
            "total": float(created.total or 0),
            "status": str(created.status),
            "due_date": created.due_date,
        }

    # -------------------------------------------------------------------------
    # Repeating Invoices (for Retainer Clients)
    # -------------------------------------------------------------------------

    def create_repeating_invoice(
        self,
        contact_id: str,
        line_items: List[Dict[str, Any]],
        schedule_unit: str = "MONTHLY",
        schedule_period: int = 1,
        start_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Create a repeating invoice for recurring revenue (retainers).

        Args:
            contact_id: Xero contact UUID
            line_items: List of line items
            schedule_unit: WEEKLY, MONTHLY, YEARLY
            schedule_period: How often (1 = every month, 2 = every 2 months, etc.)
            start_date: When to start the schedule

        Returns:
            Created repeating invoice data
        """
        from xero_python.accounting import RepeatingInvoice, LineItem, Contact, Schedule

        xero_line_items = []
        for item in line_items:
            li = LineItem(
                description=item.get("description", ""),
                quantity=item.get("quantity", 1),
                unit_amount=item.get("unit_amount", 0),
                account_code=item.get("account_code", "200"),
            )
            xero_line_items.append(li)

        schedule = Schedule(
            unit=schedule_unit,
            period=schedule_period,
            due_date_type="DAYSAFTERBILLDATE",
            due_date=30,  # Net 30
        )

        if start_date:
            schedule.start_date = start_date

        repeating_invoice = RepeatingInvoice(
            type="ACCREC",
            contact=Contact(contact_id=contact_id),
            line_items=xero_line_items,
            schedule=schedule,
            status="DRAFT",
        )

        response = self.accounting_api.create_repeating_invoices(
            self.tenant_id,
            repeating_invoices={"repeating_invoices": [repeating_invoice]}
        )

        created = response.repeating_invoices[0] if response.repeating_invoices else None
        if not created:
            raise Exception("Failed to create repeating invoice in Xero")

        return {
            "repeating_invoice_id": created.repeating_invoice_id,
            "contact_id": contact_id,
            "total": float(created.total or 0),
            "status": str(created.status),
            "schedule": {
                "unit": schedule_unit,
                "period": schedule_period,
            }
        }

    # -------------------------------------------------------------------------
    # Repeating Bills (for Recurring Expenses)
    # -------------------------------------------------------------------------

    def create_repeating_bill(
        self,
        contact_id: str,
        line_items: List[Dict[str, Any]],
        schedule_unit: str = "MONTHLY",
        schedule_period: int = 1,
        start_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Create a repeating bill for recurring expenses.

        Args:
            contact_id: Xero supplier contact UUID
            line_items: List of line items
            schedule_unit: WEEKLY, MONTHLY, YEARLY
            schedule_period: How often
            start_date: When to start

        Returns:
            Created repeating bill data
        """
        from xero_python.accounting import RepeatingInvoice, LineItem, Contact, Schedule

        xero_line_items = []
        for item in line_items:
            li = LineItem(
                description=item.get("description", ""),
                quantity=item.get("quantity", 1),
                unit_amount=item.get("unit_amount", 0),
                account_code=item.get("account_code", "400"),
            )
            xero_line_items.append(li)

        schedule = Schedule(
            unit=schedule_unit,
            period=schedule_period,
            due_date_type="DAYSAFTERBILLDATE",
            due_date=30,
        )

        if start_date:
            schedule.start_date = start_date

        repeating_bill = RepeatingInvoice(
            type="ACCPAY",  # Accounts Payable
            contact=Contact(contact_id=contact_id),
            line_items=xero_line_items,
            schedule=schedule,
            status="DRAFT",
        )

        response = self.accounting_api.create_repeating_invoices(
            self.tenant_id,
            repeating_invoices={"repeating_invoices": [repeating_bill]}
        )

        created = response.repeating_invoices[0] if response.repeating_invoices else None
        if not created:
            raise Exception("Failed to create repeating bill in Xero")

        return {
            "repeating_bill_id": created.repeating_invoice_id,
            "contact_id": contact_id,
            "total": float(created.total or 0),
            "status": str(created.status),
            "schedule": {
                "unit": schedule_unit,
                "period": schedule_period,
            }
        }
