"""Persist extracted invoice records into the VIM database."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from vim_database.database import db
from vim_database.models import (
    Vendor,
    PurchaseOrder,
    Invoice,
    InvoiceDocument,
    InvoiceLineItem,
    OCRExtraction,
)
from vim_logger import get_logger

logger = get_logger("vim.extraction.load")


def _get(record: dict, field, default=None):
    v = record.get(field)
    if v not in (None, ""):
        return v
    return default


def _get_date(record: dict, field, default=None):
    v = _get(record, field, default=None)
    if v is None:
        return default
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(v, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return default


def _confidence_score(record: dict) -> Decimal:
    if record.get("_extraction_error"):
        return Decimal("0.00")

    scores = [
        v for v in (record.get("field_confidence") or {}).values()
        if isinstance(v, (int, float))
    ]
    if scores:
        return Decimal(str(round(sum(scores) / len(scores), 2)))

    issues = record.get("_validation_issues") or []
    if not issues:
        return Decimal("95.00")
    if len(issues) <= 2:
        return Decimal("75.00")
    return Decimal("50.00")


def _extraction_status(record: dict) -> str:
    if record.get("_extraction_error"):
        return "Failed"
    if record.get("_validation_issues"):
        return "NeedsReview"
    return "Success"


def _find_vendor(record: dict) -> Vendor:
    vendor_name = _get(record, "vendor_name")
    if not vendor_name:
        raise ValueError("vendor_name is required")

    logger.debug("[DB] Looking up vendor by name: '%s'", vendor_name)
    vendor = Vendor.query.filter(
        db.func.lower(Vendor.VendorName) == str(vendor_name).strip().lower(),
        Vendor.Status == 1,
    ).first()
    if vendor:
        logger.debug("[DB] Vendor found by name: '%s' (ID=%s)", vendor.VendorName, vendor.VendorID)
        return vendor

    vendor_id = record.get("vendor_id")
    if vendor_id:
        logger.debug("[DB] Vendor not found by name — trying vendor_id=%s", vendor_id)
        vendor = db.session.get(Vendor, vendor_id)
        if vendor and vendor.Status == 1:
            logger.debug("[DB] Vendor found by ID: '%s'", vendor.VendorName)
            return vendor

    raise ValueError(f"Vendor {vendor_name!r} is not registered")


def _find_or_create_purchase_order(record: dict, vendor: Vendor, file_name: str) -> PurchaseOrder:
    po_number = _get(record, "po_number") or f"AUTO-{file_name}"
    logger.debug("[DB] Looking up PO: '%s'", po_number)

    po = PurchaseOrder.query.filter_by(PONumber=po_number).first()
    if po:
        logger.debug("[DB] Existing PO found: '%s'", po_number)
        return po

    logger.info("[DB] Creating new PO: '%s' for vendor '%s'", po_number, vendor.VendorName)
    po = PurchaseOrder(
        PONumber=po_number,
        VendorID=vendor.VendorID,
        PODate=_get_date(record, "invoice_date", default=date(1970, 1, 1)),
        TotalAmount=_get(record, "total_due", default=0) or 0,
        Status=_get(record, "invoice_status", default="Open"),
    )
    db.session.add(po)
    db.session.flush()
    logger.debug("[DB] PO created: '%s'", po.PONumber)
    return po


def _upsert_ocr_extraction(document: InvoiceDocument, record: dict) -> None:
    ocr = document.ocr_extraction
    if not ocr:
        ocr = OCRExtraction(DocumentID=document.DocumentID)
        db.session.add(ocr)

    ocr.ExtractedVendorName = _get(record, "vendor_name", default="Unknown") or "Unknown"
    ocr.ExtractedInvoiceNumber = _get(record, "invoice_number", default="") or ""
    ocr.ExtractedInvoiceDate = _get_date(record, "invoice_date", default=date(1970, 1, 1))
    ocr.ExtractedAmount = _get(record, "total_due", default=0) or 0
    ocr.ConfidenceScore = _confidence_score(record)
    ocr.ExtractionStatus = _extraction_status(record)


def insert_record(record: dict) -> Invoice:
    """Insert or update invoice data from an enriched extraction record."""
    file_name = record.get("file_name")
    logger.info("[DB INSERT] Processing record for file: '%s'", file_name)

    vendor = _find_vendor(record)
    po = _find_or_create_purchase_order(record, vendor, file_name)

    invoice_fields = dict(
        InvoiceNumber=_get(record, "invoice_number", default="") or f"UNKNOWN-{file_name}",
        InvoiceDate=_get_date(record, "invoice_date", default=date(1970, 1, 1)),
        VendorID=vendor.VendorID,
        PONumber=po.PONumber,
        InvoiceAmount=_get(record, "total_due", default=0) or 0,
        Currency=_get(record, "currency", default="USD"),
        DueDate=_get_date(record, "due_date", default=date(1970, 1, 1)),
        InvoiceStatus=_get(record, "invoice_status", default="Pending"),
    )

    existing_doc = InvoiceDocument.query.filter_by(FileName=file_name).first()

    if existing_doc:
        logger.info("[DB INSERT] Existing document found — updating invoice (ID=%s)", existing_doc.InvoiceID)
        invoice = db.session.get(Invoice, existing_doc.InvoiceID)
        for key, value in invoice_fields.items():
            setattr(invoice, key, value)
        document = existing_doc
    else:
        logger.info(
            "[DB INSERT] New invoice — InvoiceNumber='%s', Vendor='%s', Amount=%s",
            invoice_fields["InvoiceNumber"], vendor.VendorName, invoice_fields["InvoiceAmount"]
        )
        invoice = Invoice(**invoice_fields)
        db.session.add(invoice)
        db.session.flush()
        logger.debug("[DB INSERT] Invoice flushed — InvoiceID=%s", invoice.InvoiceID)

        document = InvoiceDocument(
            InvoiceID=invoice.InvoiceID,
            FileName=file_name,
            FileType="",
            StoragePath="",
        )
        db.session.add(document)
        db.session.flush()
        logger.debug("[DB INSERT] InvoiceDocument flushed — DocumentID=%s", document.DocumentID)

    document.FileType = Path(file_name or "").suffix.lstrip(".").upper()
    document.StoragePath = record.get("file_path") or ""

    line_items = record.get("line_items") or []
    InvoiceLineItem.query.filter_by(InvoiceID=invoice.InvoiceID).delete()
    logger.debug("[DB INSERT] Writing %d line item(s) for InvoiceID=%s", len(line_items), invoice.InvoiceID)
    for item in line_items:
        db.session.add(InvoiceLineItem(
            InvoiceID=invoice.InvoiceID,
            Description=_get(item, "description", default=""),
            Quantity=_get(item, "quantity", default=0) or 0,
            CostAmount=_get(item, "unit_price", default=0) or 0,
            DiscountAmount=0,
            LineAmount=_get(item, "amount", default=0) or 0,
        ))

    _upsert_ocr_extraction(document, record)
    logger.info(
        "[DB INSERT] Done — InvoiceID=%s, InvoiceNumber='%s', line_items=%d",
        invoice.InvoiceID, invoice.InvoiceNumber, len(line_items)
    )
    return invoice
