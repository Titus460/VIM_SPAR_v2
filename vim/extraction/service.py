"""Orchestrates upload → extract → persist for the VIM web app."""

from pathlib import Path
from uuid import uuid4

from werkzeug.utils import secure_filename

from vim.extraction import config
from vim.extraction.enrich import detect_vendor_name, extract_from_file
from vim.extraction.load import insert_record
from vim.extraction.schema import empty_record
from vim.extraction.vendors import find_registered_vendor
from vim_database.database import db
from vim_logger import get_logger

logger = get_logger("vim.extraction.service")


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in config.SUPPORTED_EXTENSIONS


def save_upload(file_storage) -> Path:
    """Save an uploaded file and return its path."""
    original = secure_filename(file_storage.filename or "")
    if not original:
        raise ValueError("No filename provided")

    ext = Path(original).suffix.lower()
    if ext not in config.SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    dest = config.UPLOAD_DIR / f"{uuid4().hex}_{original}"
    file_storage.save(dest)
    logger.info("[UPLOAD] Saved '%s' → %s", original, dest)
    return dest


def _resolve_status(record: dict) -> str:
    """Derive pipeline status from extraction/validation outcome."""
    if record.get("status") == "vendor_not_registered":
        return "vendor_not_registered"
    if record.get("_extraction_error"):
        return "extraction_failed"
    if record.get("_db_error") or record.get("status") == "db_error":
        return "db_error"
    if record.get("_validation_issues"):
        return "needs_review"
    return "success"


def _vendor_gate_failure(
    *,
    original_name: str,
    saved_path: Path,
    vendor_name: str | None,
    message: str,
) -> dict:
    record = empty_record()
    record["file_name"] = original_name
    record["stored_file_name"] = saved_path.name
    record["file_path"] = str(saved_path)
    record["vendor_name"] = vendor_name
    record["_extraction_error"] = message
    record["status"] = "vendor_not_registered"
    return record


def process_uploaded_file(file_storage) -> dict:
    """
    Full intelligent upload pipeline:
    1. Save file
    2. Detect vendor and verify registration
    3. Extract data (LlamaParse + Groq) when vendor is registered
    4. Validate
    5. Save to output/enriched.json
    6. Persist to VIM database (skipped when extraction fails)
    """
    from vim.extraction.json_store import upsert_record

    config.validate()

    original_name = secure_filename(file_storage.filename or "")
    logger.info("━" * 55)
    logger.info("[PIPELINE START] File: '%s'", original_name)

    # ── Step 1: Save ────────────────────────────────────────────
    saved_path = save_upload(file_storage)

    # ── Step 2: Detect vendor ───────────────────────────────────
    logger.info("[STEP 2/6] Detecting vendor from document ...")
    detected_name, raw_text, detect_error = detect_vendor_name(str(saved_path))

    if detect_error:
        logger.warning(
            "[STEP 2/6] Vendor detection FAILED for '%s': %s",
            original_name, detect_error
        )
        record = empty_record()
        record["file_name"] = original_name
        record["stored_file_name"] = saved_path.name
        record["file_path"] = str(saved_path)
        record["vendor_name"] = detected_name
        record["_extraction_error"] = detect_error
        is_vendor_issue = "registered vendor" in detect_error.lower()
        record["status"] = "vendor_not_registered" if is_vendor_issue else "extraction_failed"
        upsert_record(record)
        logger.info("[PIPELINE END] '%s' → status=%s", original_name, record["status"])
        return record

    logger.info("[STEP 2/6] Detected vendor name: '%s'", detected_name)

    # ── Step 3: Vendor registration gate ────────────────────────
    logger.info("[STEP 3/6] Looking up registered vendor '%s' ...", detected_name)
    vendor = find_registered_vendor(detected_name)
    if not vendor:
        logger.warning(
            "[STEP 3/6] Vendor '%s' is NOT registered — blocking pipeline", detected_name
        )
        record = _vendor_gate_failure(
            original_name=original_name,
            saved_path=saved_path,
            vendor_name=detected_name,
            message=(
                f"Vendor {detected_name!r} is not registered. "
                "Add the vendor under Admin → Vendors before uploading."
            ),
        )
        record["vendor_id"] = None
        upsert_record(record)
        logger.info("[PIPELINE END] '%s' → status=vendor_not_registered", original_name)
        return record

    logger.info(
        "[STEP 3/6] Vendor matched: '%s' (VendorID=%s)",
        vendor.VendorName, vendor.VendorID
    )

    # ── Step 4: Full extraction ─────────────────────────────────
    logger.info("[STEP 4/6] Running LlamaParse + Groq extraction ...")
    record = extract_from_file(str(saved_path), raw_text=raw_text)

    # Keep human-readable filename in the record (not the uuid prefix on disk)
    record["file_name"] = original_name
    record["stored_file_name"] = saved_path.name
    record["vendor_name"] = vendor.VendorName
    record["vendor_id"] = vendor.VendorID

    if record.get("_extraction_error"):
        logger.error(
            "[STEP 4/6] Extraction FAILED for '%s': %s",
            original_name, record["_extraction_error"]
        )
        record["status"] = "extraction_failed"
        upsert_record(record)
        logger.info("[PIPELINE END] '%s' → status=extraction_failed", original_name)
        return record

    validation_issues = record.get("_validation_issues", [])
    logger.info(
        "[STEP 4/6] Extraction OK — invoice_number='%s', total_due=%s, "
        "line_items=%d, validation_issues=%d",
        record.get("invoice_number"), record.get("total_due"),
        len(record.get("line_items") or []), len(validation_issues)
    )
    if validation_issues:
        logger.debug("[STEP 4/6] Extraction validation issues: %s", validation_issues)

    # ── Step 5: Save to enriched.json ───────────────────────────
    logger.info("[STEP 5/6] Saving record to enriched.json ...")
    upsert_record(record)
    logger.info("[STEP 5/6] enriched.json updated")

    # ── Step 6: Persist to DB ───────────────────────────────────
    logger.info("[STEP 6/6] Persisting invoice to database ...")
    try:
        invoice = insert_record(record)
        db.session.commit()
        record["invoice_id"] = invoice.InvoiceID
        logger.info(
            "[STEP 6/6] DB persist OK — InvoiceID=%s, InvoiceNumber='%s'",
            invoice.InvoiceID, invoice.InvoiceNumber
        )
    except Exception as e:
        db.session.rollback()
        record["status"] = "db_error"
        record["_db_error"] = str(e)
        logger.error("[STEP 6/6] DB persist FAILED for '%s': %s", original_name, e)
        upsert_record(record)
        logger.info("[PIPELINE END] '%s' → status=db_error", original_name)
        return record

    record["status"] = _resolve_status(record)
    upsert_record(record)
    logger.info(
        "[PIPELINE END] '%s' → status=%s  (InvoiceID=%s)",
        original_name, record["status"], record.get("invoice_id")
    )
    logger.info("━" * 55)
    return record

