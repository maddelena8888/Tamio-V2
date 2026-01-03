"""
Base integration adapter interface.

All accounting software integrations (Xero, QuickBooks, etc.) implement
this interface to provide a unified way to sync data with Tamio.
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


class IntegrationType(str, Enum):
    """Supported integration types."""
    MANUAL = "manual"
    XERO = "xero"
    QUICKBOOKS = "quickbooks"


@dataclass
class NormalizedContact:
    """
    Normalized contact data from any accounting platform.

    This is the common format that all adapters produce,
    which then gets mapped to Tamio's Client or ExpenseBucket.
    """
    external_id: str
    name: str
    is_customer: bool
    is_supplier: bool
    currency: Optional[str] = None
    payment_terms_days: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None


@dataclass
class NormalizedInvoice:
    """
    Normalized invoice/bill data from any accounting platform.

    Works for both:
    - Customer invoices (ACCREC) → revenue
    - Supplier bills (ACCPAY) → expenses
    """
    external_id: str
    contact_id: str
    contact_name: str
    invoice_type: str  # "receivable" | "payable"
    status: str  # "draft" | "submitted" | "authorised" | "paid" | "voided"
    total: Decimal
    amount_due: Decimal
    currency: str
    invoice_date: datetime
    due_date: datetime
    is_repeating: bool = False
    repeating_id: Optional[str] = None
    line_items: Optional[List[Dict[str, Any]]] = None


@dataclass
class NormalizedRepeatingInvoice:
    """
    Normalized repeating invoice/bill template.

    Used to identify retainer clients and recurring expenses.
    """
    external_id: str
    contact_id: str
    contact_name: str
    invoice_type: str  # "receivable" | "payable"
    status: str  # "draft" | "authorised"
    total: Decimal
    currency: str
    frequency: str  # "weekly" | "monthly" | "quarterly" | "annually"
    next_scheduled_date: Optional[datetime] = None
    due_day_of_month: Optional[int] = None


@dataclass
class NormalizedBankAccount:
    """Normalized bank account data."""
    external_id: str
    name: str
    account_type: str
    currency: str
    balance: Decimal
    as_of_date: datetime


class IntegrationAdapter(ABC):
    """
    Abstract base class for accounting software integrations.

    Each accounting platform (Xero, QuickBooks) implements this interface,
    providing normalized data that Tamio can process uniformly.

    Example usage:
        adapter = XeroAdapter(connection)
        customers = adapter.get_customers()
        for customer in customers:
            # customer is a NormalizedContact
            create_or_update_client(customer)
    """

    @property
    @abstractmethod
    def integration_type(self) -> IntegrationType:
        """Return the integration type."""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """Check if the integration is currently connected and authenticated."""
        pass

    @abstractmethod
    def get_tenant_name(self) -> Optional[str]:
        """Get the connected organization/company name."""
        pass

    # =========================================================================
    # Contact methods
    # =========================================================================

    @abstractmethod
    def get_customers(self) -> List[NormalizedContact]:
        """
        Get all customer contacts from the accounting system.

        Returns:
            List of normalized customer contacts
        """
        pass

    @abstractmethod
    def get_suppliers(self) -> List[NormalizedContact]:
        """
        Get all supplier/vendor contacts from the accounting system.

        Returns:
            List of normalized supplier contacts
        """
        pass

    @abstractmethod
    def get_contact(self, external_id: str) -> Optional[NormalizedContact]:
        """Get a single contact by external ID."""
        pass

    # =========================================================================
    # Invoice methods
    # =========================================================================

    @abstractmethod
    def get_outstanding_receivables(self) -> List[NormalizedInvoice]:
        """
        Get all outstanding customer invoices (money owed TO the business).

        Returns:
            List of normalized invoices with amount_due > 0
        """
        pass

    @abstractmethod
    def get_outstanding_payables(self) -> List[NormalizedInvoice]:
        """
        Get all outstanding supplier bills (money owed BY the business).

        Returns:
            List of normalized bills with amount_due > 0
        """
        pass

    @abstractmethod
    def get_repeating_invoices(self) -> List[NormalizedRepeatingInvoice]:
        """
        Get all repeating invoice templates (both receivables and payables).

        Returns:
            List of normalized repeating invoices
        """
        pass

    # =========================================================================
    # Bank account methods
    # =========================================================================

    @abstractmethod
    def get_bank_accounts(self) -> List[NormalizedBankAccount]:
        """
        Get all bank accounts with current balances.

        Returns:
            List of normalized bank accounts
        """
        pass

    # =========================================================================
    # Write methods (for bi-directional sync)
    # =========================================================================

    @abstractmethod
    def create_contact(
        self,
        name: str,
        is_customer: bool,
        is_supplier: bool,
        currency: Optional[str] = None,
        email: Optional[str] = None
    ) -> NormalizedContact:
        """Create a new contact in the accounting system."""
        pass

    @abstractmethod
    def update_contact(
        self,
        external_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None
    ) -> NormalizedContact:
        """Update an existing contact."""
        pass


class ManualAdapter(IntegrationAdapter):
    """
    Adapter for manual data entry (no external integration).

    This adapter always returns empty lists since there's no external
    system to sync with. It's used as a fallback/default.
    """

    @property
    def integration_type(self) -> IntegrationType:
        return IntegrationType.MANUAL

    def is_connected(self) -> bool:
        return True  # Manual is always "connected"

    def get_tenant_name(self) -> Optional[str]:
        return None

    def get_customers(self) -> List[NormalizedContact]:
        return []

    def get_suppliers(self) -> List[NormalizedContact]:
        return []

    def get_contact(self, external_id: str) -> Optional[NormalizedContact]:
        return None

    def get_outstanding_receivables(self) -> List[NormalizedInvoice]:
        return []

    def get_outstanding_payables(self) -> List[NormalizedInvoice]:
        return []

    def get_repeating_invoices(self) -> List[NormalizedRepeatingInvoice]:
        return []

    def get_bank_accounts(self) -> List[NormalizedBankAccount]:
        return []

    def create_contact(
        self,
        name: str,
        is_customer: bool,
        is_supplier: bool,
        currency: Optional[str] = None,
        email: Optional[str] = None
    ) -> NormalizedContact:
        raise NotImplementedError("Manual adapter does not support creating contacts")

    def update_contact(
        self,
        external_id: str,
        name: Optional[str] = None,
        email: Optional[str] = None
    ) -> NormalizedContact:
        raise NotImplementedError("Manual adapter does not support updating contacts")
