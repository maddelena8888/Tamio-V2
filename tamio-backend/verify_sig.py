
import inspect
from app.xero.client import XeroClient

print("Verifying XeroClient signatures...")

sig_invoices = inspect.signature(XeroClient.get_invoices)
print(f"get_invoices parameters: {list(sig_invoices.parameters.keys())}")
if 'fetch_all' in sig_invoices.parameters:
    print("SUCCESS: get_invoices has 'fetch_all'")
else:
    print("FAILURE: get_invoices MISSING 'fetch_all'")

sig_contacts = inspect.signature(XeroClient.get_contacts)
print(f"get_contacts parameters: {list(sig_contacts.parameters.keys())}")
if 'fetch_all' in sig_contacts.parameters:
    print("SUCCESS: get_contacts has 'fetch_all'")
else:
    print("FAILURE: get_contacts MISSING 'fetch_all'")
