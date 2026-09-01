"""Map vendor-specific extra_fields labels onto canonical schema fields.

The extraction model invents a new label for the same thing on every run: one
"thank you" note has arrived as note, notes, note_to_customer, "Note to
customer", and thank_you_note, and payment terms as both "Terms" and "terms".
Normalising the label and looking it up here collapses those variants into a
single canonical field instead of leaving one value scattered across five
unqueryable keys.

To teach the system a new label, add it to the list for its canonical field in
_FIELD_LABELS. Labels are compared with punctuation, spacing, and case
removed, so only genuinely different wording needs an entry.
"""

import re

from vim.extraction.schema import HEADER_FIELDS

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]")


def normalize_label(label) -> str:
    """Collapse a printed label to a comparable key: "Note to customer" -> "notetocustomer"."""
    return _NON_ALNUM_RE.sub("", str(label or "").lower())


# Canonical field -> labels seen (or expected) for it on real documents.
#
# Deliberately excluded, because the label alone is too ambiguous to map
# safely: bare "Account No" (customer account or bank account?), "SWIFT"/"BIC"
# (not the same as a bank key), and bare "Total" (net, gross, or due?).
_FIELD_LABELS = {
    "customer_note": [
        "note", "notes", "note to customer", "notes to customer",
        "customer note", "thank you note", "thank you", "message",
        "remark", "remarks", "comment", "comments", "footer note",
    ],
    "payment_terms": [
        "terms", "term", "payment terms", "payment term",
        "terms of payment", "credit terms",
    ],
    "due_date": [
        "overdue date", "payment due date", "date due", "pay by",
    ],
    "order_date": [
        "order date", "date of order", "purchase order date", "po date",
    ],
    "delivery_date": [
        "deliver date", "delivery date", "ship date", "shipping date",
        "dispatch date", "date delivered", "service date",
    ],
    "document_type": [
        "title", "document title", "doc type", "document type",
        "invoice type", "voucher type",
    ],
    "original_invoice_number": [
        "original invoice", "original invoice no", "original invoice number",
        "reference invoice", "ref invoice no", "against invoice",
        "invoice reference", "original document",
    ],
    "po_number": [
        "purchase order", "purchase order no", "purchase order number",
        "po no", "po num", "customer po", "buyer po", "order number",
        "order no",
    ],
    "invoice_number": [
        "invoice no", "invoice num", "inv no", "bill no", "bill number",
        "document no", "document number",
    ],
    "invoice_date": [
        "bill date", "date of issue", "issue date", "dated",
        "document date", "invoice dt",
    ],
    "invoice_status": [
        "status", "payment status",
    ],
    "currency": [
        "currency code", "curr",
    ],
    "language": [
        "lang",
    ],
    "country_code": [
        "country",
    ],
    "account_number": [
        "account no", "account number", "a c no", "account id",
    ],
    "recipient_number": [
        "customer no", "customer number", "customer id", "customer code",
        "client no", "client id",
    ],
    "requestor_name": [
        "requested by", "requestor", "requester", "requestor name",
        "ordered by", "contact person",
    ],
    "vendor_code": [
        "vendor code", "vendor no", "vendor id", "supplier code",
        "supplier no", "supplier id",
    ],
    "vendor_gst_number": [
        "gstin", "gst no", "gst number", "gstin no", "gst registration no",
    ],
    "vendor_vat_number": [
        "vat no", "vat number", "vat id", "tax id", "tin",
        "tax registration no",
    ],
    "buyer_vat_number": [
        "buyer vat", "buyer gstin", "customer gstin", "customer vat",
        "recipient gstin", "buyer tax id",
    ],
    "bank_name": [
        "bank", "bank name", "beneficiary bank",
    ],
    "bank_account_number": [
        "bank account", "bank account no", "bank account number",
        "bank a c no", "beneficiary account", "beneficiary account no",
    ],
    "bank_key": [
        "sort code", "routing number", "routing no", "aba", "aba number",
        "bank key", "clearing number",
    ],
    "iban": [
        "iban", "iban no", "iban number",
    ],
    "ifsc_code": [
        "ifsc", "ifsc code",
    ],
    "payment_reference": [
        "payment reference", "payment ref", "utr", "utr no", "utr number",
        "remittance reference",
    ],
    "freight_amount": [
        "freight", "freight charges", "shipping", "shipping charges",
        "delivery charges", "carriage", "postage",
    ],
    "tax_rate": [
        "tax rate", "gst rate", "vat rate", "rate of tax",
    ],
    "tax_amount": [
        "tax", "total tax", "tax amount", "gst amount", "vat amount",
    ],
    "net_amount": [
        "net amount", "net total", "amount before tax", "taxable amount",
        "taxable value", "net value",
    ],
    "gross_amount": [
        "gross amount", "gross total", "gross value",
        "total inclusive of tax", "total including tax",
    ],
    "total_due": [
        "total due", "amount due", "balance due", "total payable",
        "amount payable", "net payable", "grand total", "total amount due",
    ],
    "vendor_postal_code": [
        "vendor postal code", "vendor zip", "vendor pin code",
    ],
    "remit_to_postal_code": [
        "remit to postal code", "remit postal code", "remittance postal code",
    ],
    "bill_to_address": [
        "bill to", "billing address", "buyer address", "invoice to",
    ],
    "customer_name": [
        "bill to name", "buyer name", "customer", "client name",
        "billed to",
    ],
}

_ALIAS_TO_FIELD: dict[str, str] = {}

for _field, _labels in _FIELD_LABELS.items():
    for _label in _labels:
        _ALIAS_TO_FIELD[normalize_label(_label)] = _field

# A canonical field name is always an alias for itself, so a model that emits
# "vendor_name" inside extra_fields still lands in the right place.
for _field in HEADER_FIELDS:
    _ALIAS_TO_FIELD.setdefault(normalize_label(_field), _field)


def canonical_field(label) -> str | None:
    """Return the canonical header field a printed label maps to, if any."""
    return _ALIAS_TO_FIELD.get(normalize_label(label))


def promote_extra_fields(record: dict) -> list[str]:
    """
    Move recognised extra_fields entries into their canonical header field.

    A value is only promoted into a field that is currently empty — an
    explicitly extracted value always outranks a leftover label. When both are
    set and disagree, the extra is kept and the disagreement is reported.

    Returns conflict messages only. Successful promotions are recorded in
    record["_promoted_fields"] so they do not mark the invoice for review.
    """
    extra = record.get("extra_fields")
    if not isinstance(extra, dict) or not extra:
        return []

    extra_conf = record.get("extra_fields_confidence")
    if not isinstance(extra_conf, dict):
        extra_conf = {}

    field_conf = record.get("field_confidence")
    if not isinstance(field_conf, dict):
        field_conf = {}
        record["field_confidence"] = field_conf

    conflicts: list[str] = []
    promoted: dict[str, str] = {}
    remaining: dict = {}

    for label, value in extra.items():
        field = canonical_field(label)

        if field is None or value in (None, "", "null"):
            remaining[label] = value
            continue

        current = record.get(field)

        if current in (None, "", "null"):
            record[field] = value
            promoted[label] = field
            # Carry the label's confidence over to the field it filled.
            if field_conf.get(field) is None and extra_conf.get(label) is not None:
                field_conf[field] = extra_conf[label]
            continue

        if str(current).strip() == str(value).strip():
            # Same value under two names; the canonical one already has it.
            promoted[label] = field
            continue

        remaining[label] = value
        conflicts.append(
            f"extra_fields.{label}={value!r} disagrees with extracted "
            f"{field}={current!r} — kept as an extra field"
        )

    record["extra_fields"] = remaining
    if promoted:
        record["_promoted_fields"] = promoted

    return conflicts
