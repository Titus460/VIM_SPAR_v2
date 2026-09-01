# from datetime import datetime
# from vim_database.database import db
# # -------------------------------
# # USER MODEL
# # -------------------------------
# class User(db.Model):
#     __tablename__ = "user"

#     UserID = db.Column(db.Integer, primary_key=True)
#     Username = db.Column(db.String(100), nullable=False)
#     PasswordHash = db.Column(db.String(255), nullable=False)
#     Email = db.Column(db.String(100), nullable=False)
#     Role = db.Column(db.String(50), nullable=False)

#     VendorID = db.Column(
#         db.Integer,
#         db.ForeignKey("vendor.VendorID"),
#         nullable=False
#     )

#     IsActive = db.Column(db.Boolean, nullable=False)
#     CreatedDate = db.Column(db.DateTime, default=datetime.utcnow)

#     # Relationship
#     vendor = db.relationship("Vendor", back_populates="users")

#     approvals = db.relationship("Approval", back_populates="user", lazy=True)

#     def __repr__(self):
#         return f"<User {self.Username}>"

# # -------------------------------
# # VENDOR MODEL
# # -------------------------------
# class Vendor(db.Model):
#     __tablename__ = "vendor"

#     VendorID = db.Column(db.Integer, primary_key=True)
#     VendorName = db.Column(db.String(100), nullable=False)
#     GSTNumber = db.Column(db.String(50), nullable=False)
#     Address = db.Column(db.String(255))
#     Email = db.Column(db.String(100), nullable=False)
#     PhoneNumber = db.Column(db.String(20))
#     Status = db.Column(db.Integer, nullable=False)

#     # Relationships
#     users = db.relationship("User", back_populates="vendor", lazy=True)
#     purchase_orders = db.relationship("PurchaseOrder", back_populates="vendor", lazy=True)
#     invoices = db.relationship("Invoice", back_populates="vendor", lazy=True)

#     def __repr__(self):
#         return f"<Vendor {self.VendorName}>"
    

# # -------------------------------
# # PurchaseOrder
# # -------------------------------

# class PurchaseOrder(db.Model):
#     __tablename__ = "purchase_order"

#     PONumber = db.Column(db.String(50), primary_key=True)
#     VendorID = db.Column(
#         db.Integer,
#         db.ForeignKey("vendor.VendorID"),
#         nullable=False
#     )

#     PODate = db.Column(db.Date, nullable=False)
#     TotalAmount = db.Column(db.Numeric(12, 2), nullable=False)
#     Status = db.Column(db.String(30), nullable=False)

#     # Relationship
#     vendor = db.relationship("Vendor", back_populates="purchase_orders")

#     invoices = db.relationship(
#         "Invoice",
#         back_populates="purchase_order",
#         lazy=True
#     )

#     def __repr__(self):
#         return f"<PurchaseOrder {self.PONumber}>"
    
# # -------------------------------
# # Invoice
# # -------------------------------
# class Invoice(db.Model):
#     __tablename__ = "invoice"

#     InvoiceID = db.Column(db.Integer, primary_key=True)
#     InvoiceNumber = db.Column(db.String(50), nullable=False)
#     InvoiceDate = db.Column(db.Date, nullable=False)

#     VendorID = db.Column(
#         db.Integer,
#         db.ForeignKey("vendor.VendorID"),
#         nullable=False
#     )

#     PONumber = db.Column(
#         db.String(50),
#         db.ForeignKey("purchase_order.PONumber"),
#         nullable=False
#     )

#     InvoiceAmount = db.Column(db.Numeric(12, 2), nullable=False)
#     Currency = db.Column(db.String(10), nullable=False)
#     DueDate = db.Column(db.Date, nullable=False)
#     InvoiceStatus = db.Column(db.String(30), nullable=False)

#     # Relationships
#     vendor = db.relationship("Vendor", back_populates="invoices")

#     purchase_order = db.relationship(
#         "PurchaseOrder",
#         back_populates="invoices"
#     )

#     documents = db.relationship(
#         "InvoiceDocument",
#         back_populates="invoice",
#         lazy=True
#     )

#     line_items = db.relationship(
#         "InvoiceLineItem",
#         back_populates="invoice",
#         lazy=True
#     )

#     validations = db.relationship(
#         "ValidationResult",
#         back_populates="invoice",
#         lazy=True
#     )

#     fraud_checks = db.relationship(
#         "FraudCheck",
#         back_populates="invoice",
#         lazy=True
#     )

#     approvals = db.relationship(
#         "Approval",
#         back_populates="invoice",
#         lazy=True
#     )

#     payments = db.relationship(
#         "Payment",
#         back_populates="invoice",
#         lazy=True
#     )

#     workflow_history = db.relationship(
#         "WorkflowHistory",
#         back_populates="invoice",
#         lazy=True
#     )

#     audit_logs = db.relationship(
#         "AuditLog",
#         back_populates="invoice",
#         lazy=True
#     )

#     exception_cases = db.relationship(
#         "ExceptionCase",
#         back_populates="invoice",
#         lazy=True
#     )

#     def __repr__(self):
#         return f"<Invoice {self.InvoiceNumber}>"



# # -------------------------------
# # InvoiceDocument
# # -------------------------------
# class InvoiceDocument(db.Model):
#     __tablename__ = "invoice_document"

#     DocumentID = db.Column(db.Integer, primary_key=True)

#     InvoiceID = db.Column(
#         db.Integer,
#         db.ForeignKey("invoice.InvoiceID"),
#         nullable=False
#     )

#     FileName = db.Column(db.String(255), nullable=False)
#     FileType = db.Column(db.String(20), nullable=False)
#     UploadDate = db.Column(db.DateTime, default=datetime.utcnow)
#     StoragePath = db.Column(db.String(500), nullable=False)

#     # Relationship
#     invoice = db.relationship(
#         "Invoice",
#         back_populates="documents"
#     )

#     ocr_extraction = db.relationship(
#         "OCRExtraction",
#         back_populates="document",
#         uselist=False
#     )

#     def __repr__(self):
#         return f"<InvoiceDocument {self.FileName}>"


# # -------------------------------
# # OCRExtraction
# # -------------------------------
# class OCRExtraction(db.Model):
#     __tablename__ = "ocr_extraction"

#     ExtractionID = db.Column(db.Integer, primary_key=True)

#     DocumentID = db.Column(
#         db.Integer,
#         db.ForeignKey("invoice_document.DocumentID"),
#         nullable=False
#     )

#     ExtractedVendorName = db.Column(db.String(255), nullable=False)
#     ExtractedInvoiceNumber = db.Column(db.String(100), nullable=False)
#     ExtractedInvoiceDate = db.Column(db.Date, nullable=False)
#     ExtractedAmount = db.Column(db.Numeric(12, 2), nullable=False)
#     ConfidenceScore = db.Column(db.Numeric(5, 2), nullable=False)
#     ExtractionStatus = db.Column(db.String(30), nullable=False)

#     # Relationship
#     document = db.relationship(
#         "InvoiceDocument",
#         back_populates="ocr_extraction"
#     )

#     def __repr__(self):
#         return f"<OCRExtraction {self.ExtractionID}>"


# # -------------------------------
# # InvoiceLineItem
# # -------------------------------
# class InvoiceLineItem(db.Model):
#     __tablename__ = "invoice_line_item"

#     LineItemID = db.Column(db.Integer, primary_key=True)

#     InvoiceID = db.Column(
#         db.Integer,
#         db.ForeignKey("invoice.InvoiceID"),
#         nullable=False
#     )

#     Description = db.Column(db.String(255), nullable=False)
#     Quantity = db.Column(db.Numeric(10, 2), nullable=False)
#     CostAmount = db.Column(db.Numeric(12, 2), nullable=False)
#     DiscountAmount = db.Column(db.Numeric(12, 2), nullable=False)
#     LineAmount = db.Column(db.Numeric(12, 2), nullable=False)

#     # Relationship
#     invoice = db.relationship(
#         "Invoice",
#         back_populates="line_items"
#     )

#     def __repr__(self):
#         return f"<InvoiceLineItem {self.LineItemID}>"


# # -------------------------------
# # ValidationResult
# # -------------------------------
# class ValidationResult(db.Model):
#     __tablename__ = "validation_result"

#     ValidationID = db.Column(db.Integer,primary_key=True)
#     InvoiceID = db.Column(db.Integer,db.ForeignKey("invoice.InvoiceID"),nullable=False)
#     InvoiceNumber = db.Column(db.String(100),nullable=False,index=True)
#     ValidationType = db.Column(db.String(50),nullable=False)
#     ValidationStatus = db.Column(db.String(30),nullable=False)
#     ValidationMessage = db.Column(db.String(255))
#     ValidationDetails = db.Column(db.JSON,nullable=True)
#     ValidationDate = db.Column(db.DateTime,default=datetime.utcnow)
#     invoice = db.relationship("Invoice", back_populates="validations")
#     StageStatus = db.Column(db.String(20),nullable=True,default="started")

#     def __repr__(self):
#         return f"<ValidationResult {self.ValidationID}>"

# # -------------------------------
# # FraudCheck
# # -------------------------------
# class FraudCheck(db.Model):
#     __tablename__ = "fraud_check"

#     FraudCheckID = db.Column(db.Integer, primary_key=True)

#     InvoiceID = db.Column(
#         db.Integer,
#         db.ForeignKey("invoice.InvoiceID"),
#         nullable=False
#     )

#     DuplicateFlag = db.Column(db.Boolean, nullable=False)
#     RiskScore = db.Column(db.Numeric(5, 2), nullable=False)
#     CheckDate = db.Column(db.DateTime, default=datetime.utcnow)

#     # Relationship
#     invoice = db.relationship(
#         "Invoice",
#         back_populates="fraud_checks"
#     )

#     def __repr__(self):
#         return f"<FraudCheck {self.FraudCheckID}>"




# # -------------------------------
# # Approval
# # -------------------------------
# class Approval(db.Model):
#     __tablename__ = "approval"

#     ApprovalID = db.Column(db.Integer, primary_key=True)

#     InvoiceID = db.Column(
#         db.Integer,
#         db.ForeignKey("invoice.InvoiceID"),
#         nullable=False
#     )

#     ApproverUserID = db.Column(
#         db.Integer,
#         db.ForeignKey("user.UserID"),
#         nullable=False
#     )

#     ApprovalStatus = db.Column(db.String(30), nullable=False)
#     ApprovalDate = db.Column(db.DateTime)
#     Comments = db.Column(db.String(255))

#     # Relationships
#     invoice = db.relationship(
#         "Invoice",
#         back_populates="approvals"
#     )

#     user = db.relationship(
#         "User",
#         back_populates="approvals"
#     )

#     def __repr__(self):
#         return f"<Approval {self.ApprovalID}>"



# # -------------------------------
# # Payment
# # -------------------------------

# class Payment(db.Model):
#     __tablename__ = "payment"

#     PaymentID = db.Column(db.Integer, primary_key=True)

#     InvoiceID = db.Column(
#         db.Integer,
#         db.ForeignKey("invoice.InvoiceID"),
#         nullable=False
#     )

#     PaymentDate = db.Column(db.DateTime, default=datetime.utcnow)
#     PaymentAmount = db.Column(db.Numeric(12, 2), nullable=False)
#     PaymentMethod = db.Column(db.String(50), nullable=False)
#     PaymentReference = db.Column(db.String(100))
#     PaymentStatus = db.Column(db.String(30), nullable=False)

#     # Relationship
#     invoice = db.relationship(
#         "Invoice",
#         back_populates="payments"
#     )

#     def __repr__(self):
#         return f"<Payment {self.PaymentID}>"

# # -------------------------------
# # WorkflowHistory
# # -------------------------------

# class WorkflowHistory(db.Model):
#     __tablename__ = "workflow_history"

#     WorkflowHistoryID = db.Column(db.Integer, primary_key=True)

#     InvoiceID = db.Column(
#         db.Integer,
#         db.ForeignKey("invoice.InvoiceID"),
#         nullable=False
#     )

#     PreviousStatus = db.Column(db.String(30))
#     CurrentStatus = db.Column(db.String(30), nullable=False)
#     ActionBy = db.Column(db.Integer, nullable=False)
#     ActionDate = db.Column(db.DateTime, default=datetime.utcnow)

#     # Relationship
#     invoice = db.relationship(
#         "Invoice",
#         back_populates="workflow_history"
#     )

#     def __repr__(self):
#         return f"<WorkflowHistory {self.WorkflowHistoryID}>"


# # -------------------------------
# # AuditLog
# # -------------------------------

# class AuditLog(db.Model):
#     __tablename__ = "audit_log"

#     AuditLogID = db.Column(db.Integer, primary_key=True)

#     InvoiceID = db.Column(
#         db.Integer,
#         db.ForeignKey("invoice.InvoiceID"),
#         nullable=False
#     )

#     UserID = db.Column(db.Integer, nullable=False)
#     ActionType = db.Column(db.String(50), nullable=False)
#     ActionTimestamp = db.Column(db.DateTime, default=datetime.utcnow)
#     Comments = db.Column(db.String(255))

#     # Relationship
#     invoice = db.relationship(
#         "Invoice",
#         back_populates="audit_logs"
#     )

#     def __repr__(self):
#         return f"<AuditLog {self.AuditLogID}>"

# # -------------------------------
# # ExceptionCase
# # -------------------------------
# class ExceptionCase(db.Model):
#     __tablename__ = "exception_case"

#     ExceptionID = db.Column(db.Integer, primary_key=True)

#     InvoiceID = db.Column(
#         db.Integer,
#         db.ForeignKey("invoice.InvoiceID"),
#         nullable=False
#     )

#     ExceptionType = db.Column(db.String(50), nullable=False)
#     Description = db.Column(db.String(255))
#     Status = db.Column(db.String(30), nullable=False)
#     CreatedDate = db.Column(db.DateTime, default=datetime.utcnow)

#     # Relationship
#     invoice = db.relationship(
#         "Invoice",
#         back_populates="exception_cases"
#     )

#     def __repr__(self):
#         return f"<ExceptionCase {self.ExceptionID}>"
        
        
# class SystemConfiguration(db.Model):

#     __tablename__ = "system_configuration"

#     ConfigID = db.Column(
#         db.Integer,
#         primary_key=True
#     )

#     AppName = db.Column(
#         db.String(200)
#     )

#     Environment = db.Column(
#         db.String(20)
#     )

#     Currency = db.Column(
#         db.String(10)
#     )

#     LLMProvider = db.Column(
#         db.String(100)
#     )

#     ModelName = db.Column(
#         db.String(100)
#     )

#     Temperature = db.Column(
#         db.Float
#     )

#     OCRProvider = db.Column(
#         db.String(100)
#     )

#     ConfidenceThreshold = db.Column(
#         db.Float
#     )

#     ApprovalLevels = db.Column(
#         db.Integer
#     )

#     AutoApproveLimit = db.Column(
#         db.Numeric(12,2)
#     )

#     SMTPServer = db.Column(
#         db.String(200)
#     )

#     SMTPPort = db.Column(
#         db.Integer
#     )

#     OpenAIKey = db.Column(
#         db.String(500)
#     )

#     GeminiKey = db.Column(
#         db.String(500)
#     )

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
 