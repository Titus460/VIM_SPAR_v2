"""Vendor registration checks for the extraction pipeline."""
 
import re
 
from vim_database.database import db
from vim_database.models import Vendor
 
# Company-form words dropped when comparing names, so "SPAR Information
# Systems LLC" and "SPAR Information Systems, L.L.C." are recognised as the
# same vendor instead of becoming two rows.
_LEGAL_SUFFIXES = {
    "llc", "llp", "lllp", "ltd", "limited", "inc", "incorporated",
    "corp", "corporation", "co", "company", "gmbh", "mbh", "ag", "bv", "nv",
    "sa", "srl", "spa", "pty", "pvt", "private", "plc", "kg", "oy", "ab",
    "as", "aps", "sas", "sarl", "kk", "lda", "kft", "doo", "sro",
}
 
_WORD_RE = re.compile(r"[a-z0-9]+")
 
 
def match_key(vendor_name) -> str:
    """
    Comparable form of a vendor name: lowercased words, no punctuation, and no
    trailing company-form words.
 
    Only trailing suffixes are dropped, so "SPAR Information Systems India
    Private Limited" stays distinct from "SPAR Information Systems LLC".
    """
    words = _WORD_RE.findall(str(vendor_name or "").lower())
    while words and words[-1] in _LEGAL_SUFFIXES:
        words.pop()
    return " ".join(words)
 
 
def registered_vendor_names() -> list[str]:
    """Active vendor names from the database."""
    return [
        v.VendorName
        for v in Vendor.query.filter_by(Status=1).order_by(Vendor.VendorName).all()
        if v.VendorName
    ]
 
 
def find_registered_vendor(vendor_name: str | None) -> Vendor | None:
    """Return a vendor row when name matches an active registration (case-insensitive)."""
    if not vendor_name or not str(vendor_name).strip():
        return None
 
    normalized = str(vendor_name).strip()
    return Vendor.query.filter(
        db.func.lower(Vendor.VendorName) == normalized.lower(),
        Vendor.Status == 1,
    ).first()
 
 
def find_vendor_any_status(vendor_name: str | None) -> Vendor | None:
    """Match a vendor by name whatever its active status, to avoid duplicate rows."""
    if not vendor_name or not str(vendor_name).strip():
        return None
 
    return Vendor.query.filter(
        db.func.lower(Vendor.VendorName) == str(vendor_name).strip().lower()
    ).first()
 
 
def find_vendor_by_match_key(vendor_name: str | None) -> Vendor | None:
    """
    Find an active vendor whose name matches apart from punctuation and company
    form. Scans in Python because the comparison cannot be expressed in SQL and
    the vendor table is small.
    """
    key = match_key(vendor_name)
    if not key:
        return None
 
    for vendor in Vendor.query.filter_by(Status=1).order_by(Vendor.VendorID):
        if match_key(vendor.VendorName) == key:
            return vendor
    return None
 
 
def is_unregistered_vendor_error(message: str | None) -> bool:
    """True when vendor detection failed only because nothing matched the register."""
    return bool(message) and "no registered vendor" in str(message).lower()
 
 
def _fit(value, length: int, default=None):
    """Trim an extracted value to its column width."""
    text = str(value).strip() if value not in (None, "") else ""
    if not text:
        return default
    return text[:length]
 
 
# Vendor master columns and the extracted record field each is filled from,
# with the column width used to trim the value.
_VENDOR_DETAIL_FIELDS = [
    ("GSTNumber", "vendor_gst_number", 50),
    ("VATNumber", "vendor_vat_number", 50),
    ("Address", "vendor_address", 255),
    ("PostalCode", "vendor_postal_code", 20),
    ("CountryCode", "country_code", 10),
    ("Email", "vendor_email", 100),
    ("PhoneNumber", "vendor_phone_number", 20),
    ("VendorCode", "vendor_code", 50),
]
 
 
def _fill_blank_details(vendor: Vendor, record: dict) -> list[str]:
    """
    Copy extracted vendor details into columns the master record leaves empty.
 
    Existing values are never overwritten: an invoice is weaker evidence than
    whatever an admin already entered.
    """
    filled = []
    for column, field, length in _VENDOR_DETAIL_FIELDS:
        if (getattr(vendor, column) or "").strip():
            continue
        value = _fit(record.get(field), length)
        if value:
            setattr(vendor, column, value)
            filled.append(column)
    return filled
 
 
def find_or_create_vendor(record: dict, *, create: bool = True) -> tuple[Vendor | None, str]:
    """
    Resolve the vendor named on an invoice.
 
    Returns (vendor, action) where action is one of matched, reactivated,
    created, or unknown. The new row is flushed but not committed, so it is
    saved or rolled back together with the invoice.
 
    When create is False, an unknown name is not registered: the caller
    gets (None, "unknown") and can ask the admin whether to proceed.
    """
    vendor_name = _fit(record.get("vendor_name"), 100)
    if not vendor_name:
        return None, "unknown"
 
    vendor = find_registered_vendor(vendor_name)
    action = "matched"
 
    if not vendor:
        existing = find_vendor_any_status(vendor_name)
        if existing:
            existing.Status = 1
            vendor, action = existing, "reactivated"
        elif (similar := find_vendor_by_match_key(vendor_name)) is not None:
            # Same company, different punctuation or company form.
            vendor, action = similar, "matched"
        elif create:
            # GSTNumber and Email are NOT NULL, so they start as empty strings
            # and _fill_blank_details populates them when the invoice shows them.
            vendor = Vendor(
                VendorName=vendor_name,
                GSTNumber="",
                Email="",
                Status=1,
            )
            db.session.add(vendor)
            action = "created"
        else:
            return None, "unknown"
 
    _fill_blank_details(vendor, record)
    db.session.flush()
    return vendor, action
 
 
def attach_vendor_id(record: dict) -> dict:
    """Ensure enriched.json records include vendor_id when vendor is registered."""
    if record.get("vendor_id"):
        return record
 
    vendor = find_registered_vendor(record.get("vendor_name"))
    if vendor:
        record["vendor_id"] = vendor.VendorID
        record["vendor_name"] = vendor.VendorName
    else:
        record.setdefault("vendor_id", None)
 
    return record