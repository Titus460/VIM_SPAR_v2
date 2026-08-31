from .base_stage import BaseStage
import json
from pathlib import Path
from datetime import datetime, timedelta
from vim.extraction.vendors import find_registered_vendor

# Tolerance for floating-point amount comparisons (±1 cent)
_AMOUNT_TOLERANCE = 0.01

class InvoiceCompletenessCheck(BaseStage):

    REQUIRED_FIELDS = [
        "invoice_id",
        "invoice_number",
        "invoice_date",
        "vendor_id",
        "vendor_name",
        "line_items",
        "total_due",
        "currency",
        "due_date",
        "po_number"
    ]

    def __init__(self):
        super().__init__("Invoice Completeness")

    def validate(self, invoice, context=None):

        missing_fields = []

        for field in self.REQUIRED_FIELDS:

            # Field must exist, but its value may be None
            if field not in invoice:
                missing_fields.append(field)

        if missing_fields:

            return {
                "stage": self.name,
                "status": "FAILED",
                "message": "Required invoice fields are missing",
                "details": {
                    "missing_fields": missing_fields
                }
            }

        return {
            "stage": self.name,
            "status": "PASSED",
            "message": "All required invoice fields are present",
            "details": {}
        }

class OcrConfidenceValidation(BaseStage):

    THRESHOLD = 85

    # Fields extracted by OCR/LLM whose confidence we want to validate
    # vendor_id and invoice_id are intentionally NOT included
    CHECK_FIELDS = [
        "vendor_name",
        "invoice_number",
        "invoice_date",
        "due_date",
        "billing_period_start",
        "billing_period_end",
        "account_number",
        "customer_name",
        "bill_to_address",
        "subtotal",
        "tax_total",
        "total_due",
        "previous_balance",
        "payment_received",
        "currency",
        "po_number",
        "invoice_status",
        "vendor_gst_number",
        "vendor_address",
        "vendor_email",
        "vendor_phone_number"
    ]

    def __init__(self):
        super().__init__("OCR Confidence")

    def validate(self, invoice, context=None):

        field_confidence = invoice.get("field_confidence")

        # ---------------------------------------------
        # 1. Confidence data is not available
        # ---------------------------------------------

        if not field_confidence:

            return {
                "stage": self.name,
                "status": "FAILED",
                "message": "OCR confidence scores are not available",
                "details": {}
            }

        low_confidence_fields = []

        # ---------------------------------------------
        # 2. Check confidence of available fields
        # ---------------------------------------------

        for field in self.CHECK_FIELDS:

            # Get extracted value
            extracted_value = invoice.get(field)

            # If field value is null, skip confidence check
            if extracted_value is None:
                continue

            # Get confidence score
            confidence = field_confidence.get(field)

            # If confidence score is not available,
            # skip this field
            if confidence is None:
                continue

            # Check against threshold
            if confidence < self.THRESHOLD:

                low_confidence_fields.append({
                    "field": field,
                    "confidence": confidence
                })

        # ---------------------------------------------
        # 3. Low confidence fields found
        # ---------------------------------------------

        if low_confidence_fields:

            return {
                "stage": self.name,
                "status": "FAILED",
                "message": "One or more extracted fields have low OCR confidence",
                "details": {
                    "threshold": self.THRESHOLD,
                    "low_confidence_fields": low_confidence_fields
                }
            }

        # ---------------------------------------------
        # 4. OCR confidence passed
        # ---------------------------------------------

        return {
            "stage": self.name,
            "status": "PASSED",
            "message": "OCR confidence is above threshold for available extracted fields",
            "details": {
                "threshold": self.THRESHOLD
            }
        }

class VendorValidation(BaseStage):

    def __init__(self):
        super().__init__("Vendor Validation")

    def validate(self, invoice, context=None):
        vendor_id = invoice.get("vendor_id")
        vendor_name = invoice.get("vendor_name")

        # -------------------------------------------------
        # 1. Vendor ID must be present
        # -------------------------------------------------
        if vendor_id is None:
            return {
                "stage": self.name,
                "status": "FAILED",
                "message": "Vendor ID is missing",
                "details": {}
            }

        # -------------------------------------------------
        # 2. Vendor name must be present
        # -------------------------------------------------
        if not vendor_name:
            return {
                "stage": self.name,
                "status": "FAILED",
                "message": "Vendor name is missing",
                "details": {
                    "vendor_id": vendor_id
                }
            }

        # -------------------------------------------------
        # 3. Find registered ACTIVE vendor by name
        # -------------------------------------------------
        vendor = find_registered_vendor(vendor_name)
        if not vendor:
            return {
                "stage": self.name,
                "status": "FAILED",
                "message": "Vendor is not registered or is inactive",
                "details": {
                    "vendor_id": vendor_id,
                    "vendor_name": vendor_name
                }
            }

        # -------------------------------------------------
        # 4. Verify vendor ID
        # -------------------------------------------------
        if vendor.VendorID != vendor_id:
            return {
                "stage": self.name,
                "status": "FAILED",
                "message": "Vendor ID does not match registered vendor",
                "details": {
                    "extracted_vendor_id": vendor_id,
                    "registered_vendor_id": vendor.VendorID,
                    "vendor_name": vendor_name
                }
            }

        # -------------------------------------------------
        # 5. Vendor successfully validated
        # -------------------------------------------------
        return {
            "stage": self.name,
            "status": "PASSED",
            "message": "Vendor is registered and active",
            "details": {
                "vendor_id": vendor.VendorID,
                "vendor_name": vendor.VendorName,
                "vendor_status": vendor.Status
            }
        }

class POMatching(BaseStage):

    def __init__(self):
        super().__init__("PO Matching")

    def validate(self, invoice, context=None):

        context = context or {}
        purchase_orders = context.get("purchase_orders", {})

        po_number = invoice.get("po_number")

        if not po_number:
            return {
                "stage": self.name,
                "status": "FAILED",
                "message": "PO number is missing",
                "details": {}
            }

        po = purchase_orders.get(po_number)

        if not po:
            return {
                "stage": self.name,
                "status": "FAILED",
                "message": "Purchase order not found",
                "details": {
                    "po_number": po_number
                }
            }

        return {
            "stage": self.name,
            "status": "PASSED",
            "message": "Purchase order matched successfully",
            "details": {
                "po_number": po_number
            }
        }

class TaxValidation(BaseStage):

    def __init__(self):
        super().__init__("Tax Validation")

    def validate(self, invoice, context=None):
        subtotal = invoice.get("subtotal")
        tax_total = invoice.get("tax_total")
        total_due = invoice.get("total_due")
        line_items = invoice.get("line_items", [])

        # ----------------------------------------------------
        # TOTAL DUE IS REQUIRED
        # ----------------------------------------------------
        if total_due is None:
            return {
                "stage": self.name,
                "status": "FAILED",
                "message": "Total due is missing",
                "details": {}
            }
        actual_total = round(float(total_due), 2)

        # ----------------------------------------------------
        # CASE 1:
        # SUBTOTAL AND TAX ARE AVAILABLE
        # ----------------------------------------------------
        if subtotal is not None and tax_total is not None:
            calculated_total = round(
                float(subtotal) + float(tax_total),
                2
            )

            if abs(calculated_total - actual_total) > _AMOUNT_TOLERANCE:
                return {
                    "stage": self.name,
                    "status": "FAILED",
                    "message": "Subtotal plus tax does not equal total due",
                    "details": {
                        "subtotal": subtotal,
                        "tax_total": tax_total,
                        "calculated_total": calculated_total,
                        "total_due": total_due
                    }
                }

            return {
                "stage": self.name,
                "status": "PASSED",
                "message": "Subtotal, tax and total due validated successfully",
                "details": {
                    "subtotal": subtotal,
                    "tax_total": tax_total,
                    "calculated_total": calculated_total,
                    "total_due": total_due
                }
            }

        # ----------------------------------------------------
        # CASE 2:
        # SUBTOTAL AVAILABLE BUT TAX IS NULL
        # ----------------------------------------------------
        if subtotal is not None and tax_total is None:
            calculated_total = round(
                float(subtotal),
                2
            )

            if abs(calculated_total - actual_total) > _AMOUNT_TOLERANCE:
                return {
                    "stage": self.name,
                    "status": "FAILED",
                    "message": "Subtotal does not equal total due when tax is not reported",
                    "details": {
                        "subtotal": subtotal,
                        "tax_total": None,
                        "calculated_total": calculated_total,
                        "total_due": total_due
                    }
                }

            return {
                "stage": self.name,
                "status": "PASSED",
                "message": "Subtotal equals total due; no separate tax reported",
                "details": {
                    "subtotal": subtotal,
                    "tax_total": None,
                    "total_due": total_due
                }
            }

        # ----------------------------------------------------
        # CASE 3:
        # SUBTOTAL IS NULL
        # TRY CALCULATING FROM LINE ITEMS
        # ----------------------------------------------------

        if subtotal is None and line_items:
            calculated_subtotal = 0.0

            for item in line_items:
                amount = item.get("amount")

                if amount is not None:
                    calculated_subtotal += float(amount)

            calculated_subtotal = round(
                calculated_subtotal,
                2
            )

            # Tax is not available
            if tax_total is None:
                if abs(calculated_subtotal - actual_total) > _AMOUNT_TOLERANCE:
                    return {
                        "stage": self.name,
                        "status": "FAILED",
                        "message": "Line item total does not equal total due",
                        "details": {
                            "calculated_subtotal": calculated_subtotal,
                            "tax_total": None,
                            "total_due": total_due
                        }
                    }

                return {
                    "stage": self.name,
                    "status": "PASSED",
                    "message": "Line item total equals total due; no separate tax reported",
                    "details": {
                        "calculated_subtotal": calculated_subtotal,
                        "tax_total": None,
                        "total_due": total_due
                    }
                }

            # Tax is available
            calculated_total = round(calculated_subtotal + float(tax_total),2)

            if abs(calculated_total - actual_total) > _AMOUNT_TOLERANCE:
                return {
                    "stage": self.name,
                    "status": "FAILED",
                    "message": "Line item total plus tax does not equal total due",
                    "details": {
                        "calculated_subtotal": calculated_subtotal,
                        "tax_total": tax_total,
                        "calculated_total": calculated_total,
                        "total_due": total_due
                    }
                }

            return {
                "stage": self.name,
                "status": "PASSED",
                "message": "Line item total, tax and total due validated successfully",
                "details": {
                    "calculated_subtotal": calculated_subtotal,
                    "tax_total": tax_total,
                    "calculated_total": calculated_total,
                    "total_due": total_due
                }
            }

        # ----------------------------------------------------
        # CASE 4:
        # NOT ENOUGH INFORMATION
        # ----------------------------------------------------
        return {
            "stage": self.name,
            "status": "FAILED",
            "message": "Insufficient amount information for tax validation",
            "details": {
                "subtotal": subtotal,
                "tax_total": tax_total,
                "total_due": total_due
            }
        }

class DuplicateDetection(BaseStage):

    # Absolute path resolved from the project root.
    # stages.py → validation/ → validation_setup/ → vim/ → project_root
    # parents[0]=validation  parents[1]=validation_setup  parents[2]=vim  parents[3]=project_root
    _PROJECT_ROOT = Path(__file__).resolve().parents[3]
    PROCESSED_INVOICES_FILE = str(
        _PROJECT_ROOT / "vim" / "validation_setup" / "data" / "processed_invoices.json"
    )
    LOOKBACK_DAYS = 30

    def __init__(self):
        super().__init__("Duplicate Detection")

    @classmethod
    def _ensure_data_dir(cls):
        """Create the data directory if it doesn't exist."""
        Path(cls.PROCESSED_INVOICES_FILE).parent.mkdir(parents=True, exist_ok=True)

    def _save_history(self, records: list) -> None:
        """Persist the processed invoice history to disk, creating dir if needed."""
        try:
            self._ensure_data_dir()
            with open(self.PROCESSED_INVOICES_FILE, "w", encoding="utf-8") as file:
                json.dump(records, file, indent=4)
        except OSError as exc:
            from vim_logger import get_logger
            get_logger("vim.validation.stages").warning(
                "[DUPLICATE] Could not write processed_invoices.json: %s", exc
            )

    def validate(self, invoice, context=None):

        invoice_id = invoice.get("invoice_id")
        invoice_number = invoice.get("invoice_number")
        vendor_id = invoice.get("vendor_id")

        # --------------------------------------------------
        # Check required fields
        # --------------------------------------------------

        if not invoice_number:
            return {
                "stage": self.name,
                "status": "FAILED",
                "message": "Invoice number is missing",
                "details": {}
            }

        if vendor_id is None:
            return {
                "stage": self.name,
                "status": "SKIPPED",
                "message": "Vendor ID is not available; duplicate validation skipped",
                "details": {}
            }

        # --------------------------------------------------
        # Read processed invoices
        # --------------------------------------------------

        try:
            with open(
                self.PROCESSED_INVOICES_FILE,
                "r",
                encoding="utf-8"
            ) as file:
                processed_invoices = json.load(file)

        except (FileNotFoundError, json.JSONDecodeError):
            processed_invoices = []

        # --------------------------------------------------
        # Calculate 30-day cutoff
        # --------------------------------------------------

        current_time = datetime.now()
        cutoff_date = (
            current_time - timedelta(days=30)
        )

        # --------------------------------------------------
        # Remove invoices older than 30 days
        # --------------------------------------------------

        recent_invoices = []
        for old_invoice in processed_invoices:
            try:
                processed_at = datetime.fromisoformat(
                    old_invoice["processed_at"]
                )
                if processed_at >= cutoff_date:
                    recent_invoices.append(old_invoice)
            except (KeyError, ValueError):
                continue

        # --------------------------------------------------
        # Check whether this invoice already exists
        # --------------------------------------------------

        for old_invoice in recent_invoices:
            if (
                old_invoice["invoice_number"]
                == invoice_number
                and
                old_invoice["vendor_id"]
                == vendor_id
            ):
                # Save cleaned 30-day history
                self._save_history(recent_invoices)

                return {
                    "stage": self.name,
                    "status": "FAILED",
                    "message": "Duplicate invoice found within the last 30 days",
                    "details": {
                        "invoice_id": invoice_id,
                        "invoice_number": invoice_number,
                        "vendor_id": vendor_id,
                        "previous_invoice_id":
                            old_invoice["invoice_id"],
                        "processed_at":
                            old_invoice["processed_at"]
                    }
                }

        # --------------------------------------------------
        # Invoice is NOT a duplicate
        # Add it to processed history
        # --------------------------------------------------

        new_invoice = {
            "invoice_id": invoice_id,
            "invoice_number": invoice_number,
            "vendor_id": vendor_id,
            "processed_at": current_time.isoformat()
        }

        recent_invoices.append(new_invoice)

        # --------------------------------------------------
        # Save updated processed invoice history
        # --------------------------------------------------

        self._save_history(recent_invoices)

        return {
            "stage": self.name,
            "status": "PASSED",
            "message": "No duplicate invoice found in the last 30 days",
            "details": {
                "invoice_id": invoice_id,
                "invoice_number": invoice_number,
                "vendor_id": vendor_id,
                "lookback_days": 30
            }

        }