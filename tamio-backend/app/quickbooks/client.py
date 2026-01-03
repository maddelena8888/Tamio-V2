"""QuickBooks API client wrapper.

This module provides a wrapper around the QuickBooks Online API
with automatic token refresh and error handling.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import secrets
import urllib.parse
import base64

from app.config import settings
from app.quickbooks.models import QuickBooksConnection


# ============================================================================
# OAUTH2 CONFIGURATION
# ============================================================================

# QuickBooks OAuth endpoints
QUICKBOOKS_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
QUICKBOOKS_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QUICKBOOKS_REVOKE_URL = "https://developer.api.intuit.com/v2/oauth2/tokens/revoke"

# API base URLs
QUICKBOOKS_API_BASE_SANDBOX = "https://sandbox-quickbooks.api.intuit.com"
QUICKBOOKS_API_BASE_PRODUCTION = "https://quickbooks.api.intuit.com"


def get_api_base_url() -> str:
    """Get the appropriate API base URL based on environment."""
    if settings.QUICKBOOKS_ENVIRONMENT == "production":
        return QUICKBOOKS_API_BASE_PRODUCTION
    return QUICKBOOKS_API_BASE_SANDBOX


def get_authorization_url(state: str) -> str:
    """Generate the QuickBooks OAuth2 authorization URL."""
    params = {
        "response_type": "code",
        "client_id": settings.QUICKBOOKS_CLIENT_ID,
        "redirect_uri": settings.QUICKBOOKS_REDIRECT_URI,
        "scope": settings.QUICKBOOKS_SCOPES,
        "state": state,
    }
    return f"{QUICKBOOKS_AUTH_URL}?{urllib.parse.urlencode(params)}"


def generate_state() -> str:
    """Generate a secure random state for OAuth."""
    return secrets.token_urlsafe(32)


def get_basic_auth_header() -> str:
    """Generate Basic Auth header for token requests."""
    credentials = f"{settings.QUICKBOOKS_CLIENT_ID}:{settings.QUICKBOOKS_CLIENT_SECRET}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"


# ============================================================================
# TOKEN MANAGEMENT
# ============================================================================

async def exchange_code_for_tokens(code: str, realm_id: str) -> Dict[str, Any]:
    """Exchange authorization code for access and refresh tokens."""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            QUICKBOOKS_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.QUICKBOOKS_REDIRECT_URI,
            },
            headers={
                "Authorization": get_basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
        )

        if response.status_code != 200:
            raise Exception(f"Token exchange failed: {response.text}")

        tokens = response.json()
        tokens["realm_id"] = realm_id
        return tokens


async def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
    """Refresh the access token using the refresh token."""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            QUICKBOOKS_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            headers={
                "Authorization": get_basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
        )

        if response.status_code != 200:
            raise Exception(f"Token refresh failed: {response.text}")

        return response.json()


async def revoke_token(token: str) -> bool:
    """Revoke a token (access or refresh)."""
    import httpx

    async with httpx.AsyncClient() as client:
        response = await client.post(
            QUICKBOOKS_REVOKE_URL,
            data={"token": token},
            headers={
                "Authorization": get_basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            }
        )

        return response.status_code == 200


# ============================================================================
# CONNECTION HELPER
# ============================================================================

async def get_valid_connection(
    db: AsyncSession,
    user_id: str
) -> Optional[QuickBooksConnection]:
    """
    Get a valid QuickBooks connection for a user, refreshing token if needed.
    Returns None if no valid connection exists.
    """
    result = await db.execute(
        select(QuickBooksConnection).where(
            QuickBooksConnection.user_id == user_id,
            QuickBooksConnection.is_active == True
        )
    )
    connection = result.scalar_one_or_none()

    if not connection:
        return None

    # Check if refresh token has expired (100 days)
    if connection.refresh_token_expires_at:
        if connection.refresh_token_expires_at < datetime.now(timezone.utc):
            # Refresh token expired - user must re-authorize
            connection.is_active = False
            connection.sync_error = "Refresh token expired. Please reconnect to QuickBooks."
            await db.commit()
            return None

    # Check if access token is expired or about to expire (within 5 minutes)
    if connection.token_expires_at:
        expiry_buffer = datetime.now(timezone.utc) + timedelta(minutes=5)
        if connection.token_expires_at < expiry_buffer:
            # Refresh the token
            try:
                tokens = await refresh_access_token(connection.refresh_token)

                connection.access_token = tokens["access_token"]
                # QuickBooks may return a new refresh token
                if "refresh_token" in tokens:
                    connection.refresh_token = tokens["refresh_token"]
                    # Reset refresh token expiry (100 days from now)
                    connection.refresh_token_expires_at = datetime.now(timezone.utc) + timedelta(days=100)

                connection.token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens["expires_in"])
                connection.sync_error = None

                await db.commit()
                await db.refresh(connection)
            except Exception as e:
                connection.is_active = False
                connection.sync_error = f"Token refresh failed: {str(e)}"
                await db.commit()
                return None

    return connection


# ============================================================================
# QUICKBOOKS API CLIENT CLASS
# ============================================================================

class QuickBooksClient:
    """High-level QuickBooks API client with automatic token management."""

    def __init__(self, connection: QuickBooksConnection):
        self.connection = connection
        self.access_token = connection.access_token
        self.realm_id = connection.realm_id
        self.base_url = get_api_base_url()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _get_url(self, endpoint: str) -> str:
        """Build full API URL."""
        return f"{self.base_url}/v3/company/{self.realm_id}/{endpoint}"

    async def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make a GET request to the QuickBooks API."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                self._get_url(endpoint),
                headers=self._get_headers(),
                params=params
            )

            if response.status_code != 200:
                raise Exception(f"QuickBooks API error: {response.status_code} - {response.text}")

            return response.json()

    async def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make a POST request to the QuickBooks API."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._get_url(endpoint),
                headers=self._get_headers(),
                json=data
            )

            if response.status_code not in [200, 201]:
                raise Exception(f"QuickBooks API error: {response.status_code} - {response.text}")

            return response.json()

    async def _query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a QuickBooks query."""
        import httpx

        url = self._get_url("query")
        params = {"query": query}

        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self._get_headers(),
                params=params
            )

            if response.status_code != 200:
                raise Exception(f"QuickBooks query error: {response.status_code} - {response.text}")

            result = response.json()
            # QuickBooks returns data in QueryResponse
            query_response = result.get("QueryResponse", {})
            # The actual data is in a key matching the entity type
            for key in query_response:
                if key not in ["startPosition", "maxResults", "totalCount"]:
                    return query_response.get(key, [])
            return []

    # -------------------------------------------------------------------------
    # Company Info
    # -------------------------------------------------------------------------

    async def get_company_info(self) -> Dict[str, Any]:
        """Get company information."""
        result = await self._get(f"companyinfo/{self.realm_id}")
        company = result.get("CompanyInfo", {})

        return {
            "company_id": company.get("Id"),
            "company_name": company.get("CompanyName"),
            "legal_name": company.get("LegalName"),
            "country": company.get("Country"),
            "currency": company.get("HomeCurrency", {}).get("value") if isinstance(company.get("HomeCurrency"), dict) else company.get("HomeCurrency"),
        }

    # -------------------------------------------------------------------------
    # Customers
    # -------------------------------------------------------------------------

    async def get_customers(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all customers."""
        query = "SELECT * FROM Customer"
        if active_only:
            query += " WHERE Active = true"
        query += " MAXRESULTS 1000"

        customers = await self._query(query)

        return [
            {
                "customer_id": c.get("Id"),
                "display_name": c.get("DisplayName"),
                "company_name": c.get("CompanyName"),
                "email": c.get("PrimaryEmailAddr", {}).get("Address") if c.get("PrimaryEmailAddr") else None,
                "balance": float(c.get("Balance", 0)),
                "currency": c.get("CurrencyRef", {}).get("value") if c.get("CurrencyRef") else None,
                "is_active": c.get("Active", True),
                "given_name": c.get("GivenName"),
                "family_name": c.get("FamilyName"),
                "payment_terms": c.get("SalesTermRef", {}).get("value") if c.get("SalesTermRef") else None,
            }
            for c in customers
        ]

    async def create_customer(
        self,
        display_name: str,
        email: Optional[str] = None,
        company_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new customer."""
        data = {
            "DisplayName": display_name,
        }

        if email:
            data["PrimaryEmailAddr"] = {"Address": email}
        if company_name:
            data["CompanyName"] = company_name

        result = await self._post("customer", data)
        customer = result.get("Customer", {})

        return {
            "customer_id": customer.get("Id"),
            "display_name": customer.get("DisplayName"),
            "email": customer.get("PrimaryEmailAddr", {}).get("Address") if customer.get("PrimaryEmailAddr") else None,
        }

    async def update_customer(
        self,
        customer_id: str,
        sync_token: str,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update an existing customer."""
        data = {
            "Id": customer_id,
            "SyncToken": sync_token,
            "sparse": True,
        }

        if display_name:
            data["DisplayName"] = display_name
        if email:
            data["PrimaryEmailAddr"] = {"Address": email}

        result = await self._post("customer", data)
        return result.get("Customer", {})

    # -------------------------------------------------------------------------
    # Vendors (Suppliers)
    # -------------------------------------------------------------------------

    async def get_vendors(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all vendors (suppliers)."""
        query = "SELECT * FROM Vendor"
        if active_only:
            query += " WHERE Active = true"
        query += " MAXRESULTS 1000"

        vendors = await self._query(query)

        return [
            {
                "vendor_id": v.get("Id"),
                "display_name": v.get("DisplayName"),
                "company_name": v.get("CompanyName"),
                "email": v.get("PrimaryEmailAddr", {}).get("Address") if v.get("PrimaryEmailAddr") else None,
                "balance": float(v.get("Balance", 0)),
                "currency": v.get("CurrencyRef", {}).get("value") if v.get("CurrencyRef") else None,
                "is_active": v.get("Active", True),
            }
            for v in vendors
        ]

    async def create_vendor(
        self,
        display_name: str,
        email: Optional[str] = None,
        company_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new vendor (supplier)."""
        data = {
            "DisplayName": display_name,
        }

        if email:
            data["PrimaryEmailAddr"] = {"Address": email}
        if company_name:
            data["CompanyName"] = company_name

        result = await self._post("vendor", data)
        vendor = result.get("Vendor", {})

        return {
            "vendor_id": vendor.get("Id"),
            "display_name": vendor.get("DisplayName"),
            "email": vendor.get("PrimaryEmailAddr", {}).get("Address") if vendor.get("PrimaryEmailAddr") else None,
        }

    # -------------------------------------------------------------------------
    # Invoices (Accounts Receivable)
    # -------------------------------------------------------------------------

    async def get_invoices(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get invoices.

        Args:
            status: Filter by status (None for all, or specific status)
        """
        query = "SELECT * FROM Invoice"
        if status:
            # QuickBooks uses Balance > 0 for unpaid invoices
            if status.lower() == "open":
                query += " WHERE Balance > '0'"
        query += " MAXRESULTS 1000"

        invoices = await self._query(query)

        return [
            {
                "invoice_id": inv.get("Id"),
                "doc_number": inv.get("DocNumber"),
                "customer_name": inv.get("CustomerRef", {}).get("name") if inv.get("CustomerRef") else None,
                "customer_id": inv.get("CustomerRef", {}).get("value") if inv.get("CustomerRef") else None,
                "status": "Open" if float(inv.get("Balance", 0)) > 0 else "Paid",
                "balance": float(inv.get("Balance", 0)),
                "total_amount": float(inv.get("TotalAmt", 0)),
                "currency": inv.get("CurrencyRef", {}).get("value") if inv.get("CurrencyRef") else "USD",
                "due_date": inv.get("DueDate"),
                "txn_date": inv.get("TxnDate"),
                "line_items": [
                    {
                        "description": line.get("Description"),
                        "amount": float(line.get("Amount", 0)),
                        "detail_type": line.get("DetailType"),
                    }
                    for line in inv.get("Line", [])
                    if line.get("DetailType") == "SalesItemLineDetail"
                ]
            }
            for inv in invoices
        ]

    async def get_outstanding_invoices(self) -> List[Dict[str, Any]]:
        """Get all outstanding (unpaid) invoices."""
        return await self.get_invoices(status="open")

    async def create_invoice(
        self,
        customer_id: str,
        line_items: List[Dict[str, Any]],
        due_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create an invoice.

        Args:
            customer_id: QuickBooks customer ID
            line_items: List of {"description": str, "amount": float, "item_id": str (optional)}
            due_date: Due date in YYYY-MM-DD format
        """
        lines = []
        for i, item in enumerate(line_items, 1):
            line = {
                "Amount": item.get("amount", 0),
                "DetailType": "SalesItemLineDetail",
                "Description": item.get("description", ""),
                "SalesItemLineDetail": {
                    "Qty": item.get("quantity", 1),
                    "UnitPrice": item.get("unit_price", item.get("amount", 0)),
                }
            }
            if item.get("item_id"):
                line["SalesItemLineDetail"]["ItemRef"] = {"value": item["item_id"]}
            lines.append(line)

        data = {
            "CustomerRef": {"value": customer_id},
            "Line": lines,
        }

        if due_date:
            data["DueDate"] = due_date

        result = await self._post("invoice", data)
        invoice = result.get("Invoice", {})

        return {
            "invoice_id": invoice.get("Id"),
            "doc_number": invoice.get("DocNumber"),
            "customer_id": customer_id,
            "total_amount": float(invoice.get("TotalAmt", 0)),
            "due_date": invoice.get("DueDate"),
        }

    # -------------------------------------------------------------------------
    # Bills (Accounts Payable)
    # -------------------------------------------------------------------------

    async def get_bills(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get bills (accounts payable)."""
        query = "SELECT * FROM Bill"
        if status:
            if status.lower() == "open":
                query += " WHERE Balance > '0'"
        query += " MAXRESULTS 1000"

        bills = await self._query(query)

        return [
            {
                "bill_id": bill.get("Id"),
                "doc_number": bill.get("DocNumber"),
                "vendor_name": bill.get("VendorRef", {}).get("name") if bill.get("VendorRef") else None,
                "vendor_id": bill.get("VendorRef", {}).get("value") if bill.get("VendorRef") else None,
                "status": "Open" if float(bill.get("Balance", 0)) > 0 else "Paid",
                "balance": float(bill.get("Balance", 0)),
                "total_amount": float(bill.get("TotalAmt", 0)),
                "currency": bill.get("CurrencyRef", {}).get("value") if bill.get("CurrencyRef") else "USD",
                "due_date": bill.get("DueDate"),
                "txn_date": bill.get("TxnDate"),
            }
            for bill in bills
        ]

    async def get_outstanding_bills(self) -> List[Dict[str, Any]]:
        """Get all outstanding (unpaid) bills."""
        return await self.get_bills(status="open")

    async def create_bill(
        self,
        vendor_id: str,
        line_items: List[Dict[str, Any]],
        due_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a bill (accounts payable)."""
        lines = []
        for item in line_items:
            line = {
                "Amount": item.get("amount", 0),
                "DetailType": "AccountBasedExpenseLineDetail",
                "Description": item.get("description", ""),
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"value": item.get("account_id", "7")}  # Default to an expense account
                }
            }
            lines.append(line)

        data = {
            "VendorRef": {"value": vendor_id},
            "Line": lines,
        }

        if due_date:
            data["DueDate"] = due_date

        result = await self._post("bill", data)
        bill = result.get("Bill", {})

        return {
            "bill_id": bill.get("Id"),
            "doc_number": bill.get("DocNumber"),
            "vendor_id": vendor_id,
            "total_amount": float(bill.get("TotalAmt", 0)),
            "due_date": bill.get("DueDate"),
        }

    # -------------------------------------------------------------------------
    # Accounts (Chart of Accounts)
    # -------------------------------------------------------------------------

    async def get_accounts(self, account_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get chart of accounts."""
        query = "SELECT * FROM Account WHERE Active = true"
        if account_type:
            query += f" AND AccountType = '{account_type}'"
        query += " MAXRESULTS 1000"

        accounts = await self._query(query)

        return [
            {
                "account_id": acc.get("Id"),
                "name": acc.get("Name"),
                "account_type": acc.get("AccountType"),
                "account_sub_type": acc.get("AccountSubType"),
                "current_balance": float(acc.get("CurrentBalance", 0)),
                "currency": acc.get("CurrencyRef", {}).get("value") if acc.get("CurrencyRef") else None,
            }
            for acc in accounts
        ]

    async def get_bank_accounts(self) -> List[Dict[str, Any]]:
        """Get bank accounts with balances."""
        return await self.get_accounts(account_type="Bank")

    # -------------------------------------------------------------------------
    # Reports
    # -------------------------------------------------------------------------

    async def get_aged_receivables(self) -> Dict[str, Any]:
        """Get aged receivables report."""
        result = await self._get("reports/AgedReceivables")

        # Parse the report
        report = result.get("Rows", {}).get("Row", [])
        contacts = []

        for row in report:
            if row.get("type") == "Data":
                cols = row.get("ColData", [])
                if len(cols) >= 7:
                    contacts.append({
                        "contact": cols[0].get("value"),
                        "current": float(cols[1].get("value", 0) or 0),
                        "30_days": float(cols[2].get("value", 0) or 0),
                        "60_days": float(cols[3].get("value", 0) or 0),
                        "90_days": float(cols[4].get("value", 0) or 0),
                        "older": float(cols[5].get("value", 0) or 0),
                        "total": float(cols[6].get("value", 0) or 0),
                    })

        return {"contacts": contacts}

    async def get_aged_payables(self) -> Dict[str, Any]:
        """Get aged payables report."""
        result = await self._get("reports/AgedPayables")

        # Parse the report (same structure as receivables)
        report = result.get("Rows", {}).get("Row", [])
        contacts = []

        for row in report:
            if row.get("type") == "Data":
                cols = row.get("ColData", [])
                if len(cols) >= 7:
                    contacts.append({
                        "contact": cols[0].get("value"),
                        "current": float(cols[1].get("value", 0) or 0),
                        "30_days": float(cols[2].get("value", 0) or 0),
                        "60_days": float(cols[3].get("value", 0) or 0),
                        "90_days": float(cols[4].get("value", 0) or 0),
                        "older": float(cols[5].get("value", 0) or 0),
                        "total": float(cols[6].get("value", 0) or 0),
                    })

        return {"contacts": contacts}

    # -------------------------------------------------------------------------
    # Recurring Transactions
    # -------------------------------------------------------------------------

    async def get_recurring_transactions(self) -> List[Dict[str, Any]]:
        """Get recurring transactions (scheduled invoices/bills)."""
        # QuickBooks uses RecurringTransaction entity
        query = "SELECT * FROM RecurringTransaction MAXRESULTS 1000"

        try:
            transactions = await self._query(query)
            return [
                {
                    "id": t.get("Id"),
                    "type": t.get("RecurType"),
                    "next_date": t.get("NextDate"),
                    "end_date": t.get("EndDate"),
                    "interval": t.get("NumInterval"),
                    "interval_type": t.get("IntervalType"),
                }
                for t in transactions
            ]
        except Exception:
            # RecurringTransaction may not be available in all QBO versions
            return []
