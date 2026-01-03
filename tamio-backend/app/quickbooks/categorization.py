"""
QuickBooks account to Tamio expense category mapping.

This module provides automatic categorization of QuickBooks transactions
based on their account types and names.
"""
import re
from typing import Optional, Dict

# Default mapping patterns: QuickBooks account name pattern -> Tamio category
DEFAULT_ACCOUNT_PATTERNS = {
    r"payroll|wages?|salaries|salary": "payroll",
    r"rent|lease": "rent",
    r"contractor|subcontractor|freelance": "contractors",
    r"software|saas|subscription|hosting|cloud": "software",
    r"marketing|advertising|ads": "marketing",
    r"insurance": "other",
    r"utilities|phone|internet|telecom": "other",
    r"legal|accounting|professional\s*fees": "other",
    r"office|supplies|equipment": "other",
    r"travel|transportation": "other",
    r"tax|vat|gst|sales\s*tax": "other",
}

# QuickBooks account types to Tamio categories
# https://developer.intuit.com/app/developer/qbo/docs/api/accounting/all-entities/account
ACCOUNT_TYPE_MAPPING = {
    "Expense": "other",
    "Cost of Goods Sold": "other",
    "Other Expense": "other",
}

# QuickBooks account sub-types to Tamio categories
ACCOUNT_SUBTYPE_MAPPING = {
    "PayrollExpenses": "payroll",
    "PayrollTaxes": "payroll",
    "Rent": "rent",
    "RentOrLeaseOfBuildings": "rent",
    "AdvertisingPromotional": "marketing",
    "Insurance": "other",
    "Utilities": "other",
    "LegalAndProfessionalFees": "other",
    "OfficeGeneralAdministrativeExpenses": "other",
    "Travel": "other",
    "TravelMeals": "other",
}


def categorize_account_code(
    account_id: str,
    account_name: str,
    account_type: Optional[str] = None,
    account_sub_type: Optional[str] = None,
    custom_mappings: Optional[Dict[str, str]] = None
) -> str:
    """
    Categorize a QuickBooks account to a Tamio expense category.

    Args:
        account_id: QuickBooks account ID
        account_name: QuickBooks account name
        account_type: QuickBooks account type (e.g., "Expense")
        account_sub_type: QuickBooks account sub-type (e.g., "PayrollExpenses")
        custom_mappings: Optional user-defined mappings {account_id: category}

    Returns:
        Tamio expense category (payroll, rent, contractors, software, marketing, or other)

    Examples:
        >>> categorize_account_code("1", "Payroll Expenses", "Expense", "PayrollExpenses")
        'payroll'
        >>> categorize_account_code("2", "Office Rent", "Expense", "Rent")
        'rent'
    """
    # 1. Check custom user mappings first (if provided)
    if custom_mappings and account_id in custom_mappings:
        return custom_mappings[account_id]

    # 2. Check account sub-type mapping
    if account_sub_type and account_sub_type in ACCOUNT_SUBTYPE_MAPPING:
        return ACCOUNT_SUBTYPE_MAPPING[account_sub_type]

    # 3. Try pattern matching on account name
    account_name_lower = account_name.lower()

    for pattern, category in DEFAULT_ACCOUNT_PATTERNS.items():
        if re.search(pattern, account_name_lower):
            return category

    # 4. Default to "other" for unmatched accounts
    return "other"


def get_category_from_account(
    account_name: Optional[str] = None,
    account_type: Optional[str] = None,
    account_sub_type: Optional[str] = None,
) -> str:
    """
    Determine expense category from account information.

    Args:
        account_name: Account name
        account_type: QuickBooks account type
        account_sub_type: QuickBooks account sub-type

    Returns:
        Tamio expense category
    """
    # Check sub-type first
    if account_sub_type and account_sub_type in ACCOUNT_SUBTYPE_MAPPING:
        return ACCOUNT_SUBTYPE_MAPPING[account_sub_type]

    # Try pattern matching on name
    if account_name:
        account_name_lower = account_name.lower()
        for pattern, category in DEFAULT_ACCOUNT_PATTERNS.items():
            if re.search(pattern, account_name_lower):
                return category

    return "other"


def get_category_from_line_items(line_items: list) -> str:
    """
    Determine expense category from bill/invoice line items.

    Uses the first line item's account for categorization.
    If multiple line items map to different categories, uses the
    category of the largest line item.

    Args:
        line_items: List of line items with account info

    Returns:
        Tamio expense category
    """
    if not line_items:
        return "other"

    # If single line item, use its category
    if len(line_items) == 1:
        item = line_items[0]
        return get_category_from_account(
            account_name=item.get("description"),
            account_type=item.get("account_type"),
            account_sub_type=item.get("account_sub_type"),
        )

    # Multiple line items: use category of largest amount
    largest_item = max(line_items, key=lambda x: x.get("amount", 0))
    return get_category_from_account(
        account_name=largest_item.get("description"),
        account_type=largest_item.get("account_type"),
        account_sub_type=largest_item.get("account_sub_type"),
    )
