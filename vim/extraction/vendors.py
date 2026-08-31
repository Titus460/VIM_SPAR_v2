"""Vendor registration checks for the extraction pipeline."""

from vim_database.database import db
from vim_database.models import Vendor


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
