"""Fixed JSON schema for invoice extraction."""
 
# Document class printed on the page. The numeric code is what downstream
# routing keys off; the label is kept for display.
DOCUMENT_TYPE_CODES = {
    0: "Invoice",
    1: "Debit Memo",
    2: "Credit Memo",
    3: "Others",
}
 
DOCUMENT_TYPE_INVOICE = 0
DOCUMENT_TYPE_DEBIT_MEMO = 1
DOCUMENT_TYPE_CREDIT_MEMO = 2
DOCUMENT_TYPE_OTHER = 3
 
# Grouped only for display and for building the prompt; HEADER_FIELDS below is
# the flat list every record is keyed by.
DOCUMENT_FIELDS = [
    "document_type_code",
    "document_type",
    "po_non_po",
    "language",
    "country_code",
]
 
VENDOR_FIELDS = [
    "vendor_name",
    "vendor_code",
    "vendor_address",
    "vendor_postal_code",
    "vendor_email",
    "vendor_phone_number",
    "vendor_gst_number",
    "vendor_vat_number",
    "remit_to_postal_code",
]
 
BUYER_FIELDS = [
    "customer_name",
    "bill_to_address",
    "buyer_vat_number",
    "recipient_number",
    "requestor_name",
    "account_number",
]
 
INVOICE_FIELDS = [
    "invoice_number",
    "invoice_date",
    "due_date",
    "order_date",
    "delivery_date",
    "po_number",
    "payment_terms",
    "payment_reference",
    "original_invoice_number",
    "invoice_status",
    "billing_period_start",
    "billing_period_end",
]
 
AMOUNT_FIELDS = [
    "currency",
    "net_amount",
    "tax_amount",
    "tax_rate",
    "freight_amount",
    "gross_amount",
    "subtotal",
    "tax_total",
    "total_due",
    "previous_balance",
    "payment_received",
]
 
BANK_FIELDS = [
    "bank_name",
    "bank_account_number",
    "bank_key",
    "iban",
    "ifsc_code",
]
 
NOTE_FIELDS = [
    "customer_note",
]
 
HEADER_FIELD_GROUPS = [
    ("Document", DOCUMENT_FIELDS),
    ("Vendor", VENDOR_FIELDS),
    ("Buyer", BUYER_FIELDS),
    ("Invoice", INVOICE_FIELDS),
    ("Amounts", AMOUNT_FIELDS),
    ("Bank", BANK_FIELDS),
    ("Notes", NOTE_FIELDS),
]
 
HEADER_FIELDS = [
    field for _group, fields in HEADER_FIELD_GROUPS for field in fields
]
 
DATE_FIELDS = [
    "invoice_date",
    "due_date",
    "order_date",
    "delivery_date",
    "billing_period_start",
    "billing_period_end",
]
 
MONEY_FIELDS = [
    "net_amount",
    "tax_amount",
    "freight_amount",
    "gross_amount",
    "subtotal",
    "tax_total",
    "total_due",
    "previous_balance",
    "payment_received",
]
 
# Percentages, not currency amounts — parsed from things like "18%" or "18,5".
PERCENT_FIELDS = [
    "tax_rate",
]
 
LINE_ITEM_FIELDS = [
    "description",
    "item_type",
    "quantity",
    "unit_of_measure",
    "unit_price",
    "tax_rate",
    "tax_amount",
    "amount",
    "po_number",
]
 
LINE_ITEM_MONEY_FIELDS = ["unit_price", "tax_amount", "amount"]
LINE_ITEM_PERCENT_FIELDS = ["tax_rate"]
 
CONFIDENCE_KEYS = ("field_confidence", "line_items_confidence", "extra_fields_confidence")
 
SCHEMA_DESCRIPTION_FOR_PROMPT = """
{
  "document_type_code": "integer or null — 0 = invoice, 1 = debit memo/debit note, 2 = credit memo/credit note, 3 = other document type",
  "document_type": "string or null — the label printed on the document, e.g. \\"Tax Invoice\\", \\"Credit Note\\"",
  "po_non_po": "\\"PO\\" if the document references a purchase order, otherwise \\"Non-PO\\", or null",
  "language": "string or null — language of the document, as an ISO 639-1 code such as \\"en\\", \\"de\\"",
  "country_code": "string or null — ISO 3166-1 alpha-2 country of the vendor, such as \\"IN\\", \\"US\\"",
 
  "vendor_name": "string or null — the company that ISSUED the document",
  "vendor_code": "string or null — the vendor's supplier/account code in the buyer's system",
  "vendor_address": "string or null — full address of the issuing vendor",
  "vendor_postal_code": "string or null — postal/ZIP code of the vendor address",
  "vendor_email": "string or null",
  "vendor_phone_number": "string or null",
  "vendor_gst_number": "string or null — Indian GSTIN, if printed",
  "vendor_vat_number": "string or null — vendor VAT/tax registration number (non-Indian equivalent of GSTIN)",
  "remit_to_postal_code": "string or null — postal code of the remit-to/payment address when it differs from the vendor address",
 
  "customer_name": "string or null — the company being billed",
  "bill_to_address": "string or null — full buyer/bill-to address",
  "buyer_vat_number": "string or null — VAT/GST registration number of the buyer",
  "recipient_number": "string or null — recipient/customer identifier assigned by the vendor",
  "requestor_name": "string or null — person who requested or ordered the goods/services",
  "account_number": "string or null",
 
  "invoice_number": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null — also use this for a label like \\"Overdue Date\\"",
  "order_date": "YYYY-MM-DD or null — date the order was placed, when shown separately",
  "delivery_date": "YYYY-MM-DD or null — delivery/dispatch/ship date, when shown separately",
  "po_number": "string or null — purchase order number referenced by the document",
  "payment_terms": "string or null — payment terms exactly as printed, e.g. \\"Net 30\\", \\"Due on receipt\\"",
  "payment_reference": "string or null — payment/remittance reference or UTR printed for payment",
  "original_invoice_number": "string or null — for a credit or debit memo, the invoice number it refers to",
  "invoice_status": "string or null",
  "billing_period_start": "YYYY-MM-DD or null",
  "billing_period_end": "YYYY-MM-DD or null",
 
  "currency": "string or null — ISO code such as USD, INR, EUR",
  "net_amount": "number or null — total BEFORE tax",
  "tax_amount": "number or null — total tax charged",
  "tax_rate": "number or null — tax percentage as a plain number, e.g. 18 for 18%",
  "freight_amount": "number or null — shipping/freight/delivery charge",
  "gross_amount": "number or null — total INCLUDING tax",
  "subtotal": "number or null",
  "tax_total": "number or null",
  "total_due": "number or null — amount payable",
  "previous_balance": "number or null",
  "payment_received": "number or null",
 
  "bank_name": "string or null",
  "bank_account_number": "string or null",
  "bank_key": "string or null — bank routing key: sort code, ABA/routing number, or SAP bank key",
  "iban": "string or null",
  "ifsc_code": "string or null — Indian IFSC code",
 
  "customer_note": "string or null — free-text note or message addressed to the customer, e.g. \\"Thank you for your business.\\"",
 
  "line_items": [
    {
      "description": "string or null",
      "item_type": "\\"goods\\" or \\"service\\" or null",
      "quantity": "number or null",
      "unit_of_measure": "string or null — EA, KG, HR, PCS, etc.",
      "unit_price": "number or null",
      "tax_rate": "number or null — tax percentage for this line",
      "tax_amount": "number or null — tax charged on this line",
      "amount": "number or null — line total",
      "po_number": "string or null — purchase order number printed on this line, if the table has a PO column"
    }
  ],
  "extra_fields": { "key": "value — flat object for other printed fields" },
  "field_confidence": {
    "vendor_name": "number 0-100 or null",
    "...": "one score per header field above, same keys"
  },
  "line_items_confidence": [
    {
      "description": "number 0-100 or null",
      "...": "one score per line item field above, same keys"
    }
  ],
  "extra_fields_confidence": {
    "key": "number 0-100 or null — one score per extra_fields key"
  }
}
""".strip()
 
 
def empty_field_confidence() -> dict:
    return {field: None for field in HEADER_FIELDS}
 
 
def empty_line_item_confidence() -> dict:
    return {field: None for field in LINE_ITEM_FIELDS}
 
 
def empty_record() -> dict:
    record = {field: None for field in HEADER_FIELDS}
    record["vendor_id"] = None
    record["line_items"] = []
    record["extra_fields"] = {}
    record["field_confidence"] = empty_field_confidence()
    record["line_items_confidence"] = []
    record["extra_fields_confidence"] = {}
    return record
 
