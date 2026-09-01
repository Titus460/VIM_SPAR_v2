from importlib.resources import files
import mimetypes
import time
from pathlib import Path
from datetime import datetime

from flask import app, render_template, redirect, request, url_for, flash, session, Response
from yaml import load_all
from vim_database.models import User, Vendor, ValidationResult, RejectedDocument, Approval
from vim_database.models import SystemConfiguration
from vim_database.database import db
from functools import wraps
from vim_logger import get_logger

logger = get_logger("vim.controller")


def register_routes(app):

    # ---------------- AUTH HELPERS ----------------
    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapped

    def admin_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get('role') != 'admin':
                flash("Admin access required.", "danger")
                return redirect(url_for('login'))
            return view(*args, **kwargs)
        return wrapped

    # ---------------added for approver--------------------
    def approver_required(view):
       @wraps(view)
       def wrapped(*args, **kwargs):
           if session.get('role') != 'approver':
               flash("Approver access required.", "danger")
               return redirect(url_for('login'))
           return view(*args, **kwargs)
       return wrapped

    # ---------------- HOME ROUTE ----------------
    @app.route('/')
    def home():
        return render_template('home.html')

    # ---------------- USER HOME (post-login) ----------------
    @app.route('/home/<int:user_id>')
    @login_required
    def user_home(user_id):
        if session['user_id'] != user_id:
            flash("You don't have access to that page.", "danger")
            return redirect(url_for('user_home', user_id=session['user_id']))
        return render_template('home.html', user_id=user_id)

    # ---------------- LOGIN ----------------
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')

            this_user = User.query.filter_by(Email=email).first()

            if this_user:
                if this_user.PasswordHash == password:
                    session['user_id'] = this_user.UserID
                    session['role'] = this_user.Role
                    flash(f"Welcome back, {this_user.Username}!", "success")
                    if this_user.Role == 'admin':
                        return redirect(url_for('admin_activities'))
                    elif this_user.Role == 'approver':
                        return redirect(url_for('approver_approvals'))
                    else:
                        return redirect(url_for('user_home', user_id=this_user.UserID))
                else:
                    flash("Incorrect password. Please try again.", "danger")
            else:
                flash("User not found. Please register first.", "warning")

        return render_template('login.html')

    # ---------------- LOGOUT ----------------
    @app.route('/logout')
    def logout():
        session.clear()
        flash("You've been logged out.", "success")
        return redirect(url_for('login'))

    # ---------------- REGISTER ----------------
    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            email = request.form.get('email')
            password = request.form.get('password')

            this_user = User.query.filter_by(Email=email).first()

            if this_user:
                flash("User already registered. Please login instead.", "warning")
                return redirect(url_for('login'))
            else:
                flash("Registration requires an admin-created vendor account. Please contact your administrator.", "warning")
                return redirect(url_for('login'))

        return render_template('registration.html')

    # ---------------- ADMIN ----------------
    @app.route('/admin', methods=['GET', 'POST'])
    @admin_required
    def admin_activities():
        return render_template('vim_admin_dashboard.html')

    @app.route('/admin/dashboard')
    @admin_required
    def admin_kpi_dashboard():
        from vim.dashboard.service import get_dashboard_metrics
        metrics = get_dashboard_metrics()
        return render_template('vim_admin_kpi_dashboard.html', metrics=metrics)

    @app.route('/admin/issues', methods=['GET', 'POST'])
    @admin_required
    def admin_vim_issues():
        return render_template('vim_admin_events_dashboard.html')

    @app.route('/admin/pipeline')
    @admin_required
    def admin_pipeline_monitor():
        from vim.pipeline_parser import parse_log
        pipeline_rows = parse_log()
        return render_template('vim_admin_pipeline.html', pipeline_rows=pipeline_rows)

    @app.route('/admin/users')
    @admin_required
    def admin_user_activities():

        users = User.query.order_by(User.UserID.desc()).all()

        vendors = Vendor.query.order_by(
            Vendor.VendorName
        ).all()

        return render_template(
            'vim_admin_users.html',
            users=users,
            vendors=vendors
        )

    @app.route('/admin/users/add', methods=['POST'])
    @admin_required
    def admin_add_user():

        try:

            user = User(
                Username=request.form['username'],
                Email=request.form['email'],
                PasswordHash=request.form['password'],
                Role=request.form['role'],
                VendorID=int(request.form['vendor_id']),
                IsActive=bool(
                    int(request.form['is_active'])
                )
            )

            db.session.add(user)
            db.session.commit()

            flash(
                "User created successfully.",
                "success"
            )

        except Exception as ex:

            db.session.rollback()

            flash(
                f"Error : {str(ex)}",
                "danger"
            )

        return redirect(
            url_for('admin_user_activities')
        )
        
    @app.route('/admin/users/toggle/<int:user_id>', methods=['POST'])
    @admin_required
    def admin_toggle_user(user_id):

        user = User.query.get_or_404(user_id)

        user.IsActive = not user.IsActive

        db.session.commit()

        flash(
            "User status updated.",
            "success"
        )

        return redirect(
            url_for('admin_user_activities')
        )
        
    @app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
    @admin_required
    def admin_delete_user(user_id):

        user = User.query.get_or_404(user_id)

        try:
            db.session.delete(user)
            db.session.commit()
            flash(
                "User deleted successfully.",
                "success"
            )
        except Exception as ex:
            db.session.rollback()
            flash(f"Cannot delete user. {str(ex)}", "danger")

        return redirect(
            url_for('admin_user_activities')
        )
        
    @app.route(
        '/admin/users/edit/<int:user_id>',
        methods=['GET','POST']
    )
    @admin_required
    def admin_edit_user(user_id):

        user = User.query.get_or_404(user_id)

        vendors = Vendor.query.all()

        if request.method == 'POST':

            try:
                user.Username = request.form['username']
                user.Email = request.form['email']
                user.Role = request.form['role']
                user.VendorID = int(request.form['vendor_id'])  # Bug #7: cast to int

                db.session.commit()

                flash(
                    "User updated successfully.",
                    "success"
                )

                return redirect(
                    url_for('admin_user_activities')
                )

            except Exception as ex:
                db.session.rollback()
                flash(f"Error updating user: {str(ex)}", "danger")

        return render_template(
            'vim_admin_user_edit.html',
            user=user,
            vendors=vendors
        )

    # -----------added for approver-----------------
    @app.route('/admin/approval', methods=['GET', 'POST'])
    @admin_required
    def admin_approval():
 
        approvers = User.query.filter_by(
            Role='approver',
            IsActive=True
        ).all()
 
        if request.method == 'POST':
 
            invoice_id = request.form.get('invoice_id')
            approver_user_id = request.form.get('approver_user_id')
 
            approver = User.query.filter_by(
                UserID=approver_user_id,
                Role='approver',
                IsActive=True
            ).first()
 
            if not approver:
                flash("Selected user is not an active approver.", "danger")
                return redirect(url_for('admin_approval'))
           
            # -------Added ApprovalDate when the invoice is assigned to an approver--------
            approval = Approval(
                InvoiceID=invoice_id,
                ApproverUserID=approver.UserID,
                ApprovalStatus='Pending',
                ApprovalDate=datetime.now()
            )
 
            db.session.add(approval)
            db.session.commit()
 
            flash(
                f"Invoice assigned to {approver.Username}.",
                "success"
            )
 
            return redirect(url_for('admin_approval'))
 
        approvals = Approval.query.order_by(
            Approval.ApprovalID.desc()
        ).all()
 
        return render_template(
            'vim_admin_approval.html',
            approvers=approvers,
            approvals=approvals
        )
 
     # --------------------Added Approver Approval page----------------------------
    @app.route('/approver/approvals')
    @approver_required
    def approver_approvals():
 
        approver_user_id = session.get('user_id')
 
        approvals = Approval.query.filter_by(
            ApproverUserID=approver_user_id,
            ApprovalStatus='Pending'
        ).order_by(
            Approval.ApprovalID.desc()
        ).all()
 
        return render_template(
            'vim_approver_approvals.html',
            approvals=approvals
        )
    # ---------------Added Approve/Reject route--------------------
    @app.route('/approver/decision/<int:approval_id>', methods=['POST'])
    @approver_required
    def approver_decision(approval_id):
 
        approver_user_id = session.get('user_id')
 
        approval = Approval.query.filter_by(
            ApprovalID=approval_id,
            ApproverUserID=approver_user_id,
            ApprovalStatus='Pending'
        ).first_or_404()
 
        decision = request.form.get('decision')
 
        if decision not in ['Approved', 'Rejected']:
           flash("Invalid approval decision.", "danger")
           return redirect(url_for('approver_approvals'))
 
        approval.ApprovalStatus = decision
        approval.ApprovalDate = datetime.now()
 
        db.session.commit()
 
        flash(
             f"Invoice {decision.lower()} successfully.",
             "success"
        )
 
        return redirect(url_for('approver_approvals'))
        
    # -----------------VENDOR Management ------------------------
    
    @app.route('/admin/vendors')
    @admin_required
    def admin_vendor_activities():

        vendors = Vendor.query.order_by(
            Vendor.VendorID.desc()
        ).all()

        return render_template(
            'vim_admin_vendors.html',
            vendors=vendors
        )
    
    @app.route(
        '/admin/vendors/add',
        methods=['POST']
    )
    @admin_required
    def admin_add_vendor():

        try:

            vendor = Vendor(
                VendorName=request.form['vendor_name'],
                GSTNumber=request.form['gst_number'],
                Address=request.form['address'],
                Email=request.form['email'],
                PhoneNumber=request.form['phone'],
                Status=int(request.form['status'])
            )

            db.session.add(vendor)

            db.session.commit()

            flash(
                "Vendor added successfully.",
                "success"
            )

        except Exception as ex:

            db.session.rollback()

            flash(
                str(ex),
                "danger"
            )

        return redirect(
            url_for(
                'admin_vendor_activities'
            )
        )
    
    @app.route(
        '/admin/vendors/edit/<int:vendor_id>',
        methods=['GET', 'POST']
    )
    @admin_required
    def admin_edit_vendor(vendor_id):

        vendor = Vendor.query.get_or_404(
            vendor_id
        )

        if request.method == 'POST':

            try:
                vendor.VendorName = request.form['vendor_name']
                vendor.GSTNumber = request.form['gst_number']
                vendor.Address = request.form['address']
                vendor.Email = request.form['email']
                vendor.PhoneNumber = request.form['phone']
                vendor.Status = int(
                    request.form['status']
                )

                db.session.commit()

                flash(
                    "Vendor updated successfully.",
                    "success"
                )

                return redirect(
                    url_for(
                        'admin_vendor_activities'
                    )
                )

            except Exception as ex:
                db.session.rollback()
                flash(f"Error updating vendor: {str(ex)}", "danger")

        return render_template(
            'vim_admin_vendor_edit.html',
            vendor=vendor
        )
        
    @app.route(
        '/admin/vendors/toggle/<int:vendor_id>',
        methods=['POST']
    )
    @admin_required
    def admin_toggle_vendor(vendor_id):

        vendor = Vendor.query.get_or_404(
            vendor_id
        )

        if vendor.Status == 1:
            vendor.Status = 0
        else:
            vendor.Status = 1

        db.session.commit()

        flash(
            "Vendor status updated.",
            "success"
        )

        return redirect(
            url_for(
                'admin_vendor_activities'
            )
        )
    
    @app.route(
        '/admin/vendors/delete/<int:vendor_id>',
        methods=['POST']
    )
    @admin_required
    def admin_delete_vendor(vendor_id):

        vendor = Vendor.query.get_or_404(
            vendor_id
        )

        try:

            db.session.delete(vendor)

            db.session.commit()

            flash(
                "Vendor deleted successfully.",
                "success"
            )

        except Exception as ex:

            db.session.rollback()

            flash(
                f"Cannot delete vendor. {str(ex)}",
                "danger"
            )

        return redirect(
            url_for(
                'admin_vendor_activities'
            )
        )
    
    # -----------------SYSTEM CONFIGURATION ---------------------
    @app.route(
        '/admin/settings',
        methods=['GET','POST']
    )
    @admin_required
    def admin_settings():

        config = SystemConfiguration.query.first()

        if not config:

            config = SystemConfiguration()

            db.session.add(config)

            db.session.commit()

        if request.method == 'POST':

            config.AppName = request.form[
                'app_name'
            ]

            config.Environment = request.form[
                'environment'
            ]

            config.Currency = request.form[
                'currency'
            ]

            config.LLMProvider = request.form[
                'llm_provider'
            ]

            config.ModelName = request.form[
                'model_name'
            ]

            config.Temperature = float(
                request.form['temperature']
            )

            config.OCRProvider = request.form[
                'ocr_provider'
            ]

            config.ConfidenceThreshold = float(
                request.form[
                    'confidence_threshold'
                ]
            )

            config.ApprovalLevels = int(
                request.form[
                    'approval_levels'
                ]
            )

            config.AutoApproveLimit = float(
                request.form[
                    'auto_approve_limit'
                ]
            )

            config.SMTPServer = request.form[
                'smtp_server'
            ]

            config.SMTPPort = int(
                request.form[
                    'smtp_port'
                ]
            )

            config.OpenAIKey = request.form[
                'openai_key'
            ]

            config.GeminiKey = request.form[
                'gemini_key'
            ]

            db.session.commit()

            flash(
                "Configuration updated successfully.",
                "success"
            )

        return render_template(
            "vim_admin_settings.html",
            config=config
        )
    
#     # ---------------- INTELLIGENT INVOICE UPLOAD ----------------
#     @app.route('/admin/invoice_upload', methods=['GET', 'POST'])
#     @admin_required
#     def admin_invoice_upload():
#         from flask import current_app
#         from vim.extraction import config as extraction_config

#         results = []

#         # Read directly from ..env file (avoids stale app.config from wrong server instance)
#         llama_key, groq_key = extraction_config._read_keys()
#         current_app.config["LLAMA_CLOUD_API_KEY"] = llama_key
#         current_app.config["GROQ_API_KEY"] = groq_key
#         extraction_config.LLAMA_CLOUD_API_KEY = llama_key
#         extraction_config.GROQ_API_KEY = groq_key
#         keys_ok = bool(llama_key and groq_key)

#         if request.method == 'POST' and keys_ok:
#             files = request.files.getlist('invoice_files')
#             if not files or all(not f.filename for f in files):
#                 flash("Please select at least one invoice file.", "warning")
#                 return redirect(url_for('admin_invoice_upload'))

#             from vim.extraction.service import process_uploaded_file

#             processed_count = 0
#             processed_invoice_ids = []
#             total_files = sum(1 for f in files if f.filename)
#             logger.info("[UPLOAD ROUTE] Received %d file(s) for processing", total_files)

#             for f in files:
#                 if not f.filename:
#                     continue

#                 logger.info("[UPLOAD ROUTE] Processing file: '%s'", f.filename)
#                 try:
#                     record = process_uploaded_file(f)
#                     results.append(record)
#                     invoice_id = record.get("invoice_id")
#                     if record.get("invoice_id") is not None:
#                         processed_count += 1
#                         processed_invoice_ids.append(int(invoice_id))
#                     logger.info(
#                         "[UPLOAD ROUTE] '%s' → status=%s  invoice_id=%s",
#                         f.filename, record.get("status"), record.get("invoice_id")
#                     )

#                 except ValueError as e:
#                     logger.warning("[UPLOAD ROUTE] ValueError for '%s': %s", f.filename, e)
#                     flash(str(e), "danger")

#                 except OSError as e:
#                     logger.error("[UPLOAD ROUTE] OSError for '%s': %s", f.filename, e)
#                     flash(str(e).strip(), "danger")
#                     break
#                 except Exception as e:
#                     logger.exception("[UPLOAD ROUTE] Unexpected error for '%s'", f.filename)
#                     flash(f"Failed to process {f.filename}: {e}","danger")

# # --------------------------------------------------
# # STORE CURRENT UPLOAD IN SESSION
# # --------------------------------------------------
#             if processed_invoice_ids:
#                 session["current_invoice_ids"] = processed_invoice_ids
#                 session.modified = True
#                 logger.info(
#                     "[UPLOAD ROUTE] Stored %d invoice ID(s) in session: %s",
#                     len(processed_invoice_ids), processed_invoice_ids
#                 )

# # --------------------------------------------------
# # RUN VALIDATION AFTER ALL UPLOADS ARE PROCESSED
# # --------------------------------------------------

#             if processed_count:
#                 try:
#                     from vim.validation_setup.validation.run_validation import (
#                         run_validation)

#                     logger.info(
#                         "[UPLOAD ROUTE] Triggering validation for %d invoice(s): %s",
#                         len(processed_invoice_ids), processed_invoice_ids
#                     )
#                     validation_ok = run_validation(
#                         invoice_ids=processed_invoice_ids or None
#                     )

#                     if validation_ok:
#                         flash(
#                             f"Successfully extracted and validated "
#                             f"{processed_count} invoice(s).", "success")
#                     else:
#                         flash(
#                             f"{processed_count} invoice(s) extracted. "
#                             "Validation completed with warnings — check the event browser.",
#                             "warning")

#                 except Exception as e:
#                     logger.exception("[UPLOAD ROUTE] Validation crashed: %s", e)
#                     flash(f"Invoices were extracted, but validation failed: {e}", "danger")

#         elif request.method == 'POST' and not keys_ok:
#             flash(
#                 "API keys not loaded. Save .env in the project root and restart the server.",
#                 "danger",
#             )

#         return render_template('invoice_upload.html', results=results, keys_ok=keys_ok)

#     # ---------------- INVOICE DATA EXTRACTION REVIEW ----------------
#     @app.route('/admin/invoice_extraction', methods=['GET'])
#     @admin_required
#     def admin_invoice_extraction():
#         from vim.extraction.json_store import load_all, ENRICHED_PATH

#         records = load_all()
#         rows = []
#         for i, rec in enumerate(reversed(records)):
#             rows.append({
#                 "index": len(records) - 1 - i,
#                 "file_name": rec.get("file_name") or rec.get("stored_file_name") or "—",
#                 "vendor_name": rec.get("vendor_name") or "—",
#                 "invoice_number": rec.get("invoice_number") or "—",
#                 "invoice_date": rec.get("invoice_date") or "—",
#                 "amount": rec.get("total_due") or "—",
#                 "currency": rec.get("currency") or "",
#                 "status": "Failed" if rec.get("_extraction_error") else (
#                     "NeedsReview" if rec.get("_validation_issues") else "Success"
#                 ),
#                 "line_item_count": len(rec.get("line_items") or []),
#             })

#         return render_template(
#             'invoice_extraction.html',
#             extractions=rows,
#             json_path=str(ENRICHED_PATH),
#         )

#     @app.route('/admin/invoice_extraction/<int:record_index>', methods=['GET'])
#     @admin_required
#     def admin_invoice_extraction_detail(record_index):
#         import json
#         from vim.extraction.json_store import load_all

#         records = load_all()
#         if record_index < 0 or record_index >= len(records):
#             flash("Extraction record not found.", "warning")
#             return redirect(url_for('admin_invoice_extraction'))

#         record = records[record_index]
#         return render_template(
#             'invoice_extraction_detail.html',
#             record=record,
#             record_index=record_index,
#             record_json=json.dumps(record, indent=2, default=str),
#         )

#     @app.route('/admin/invoice_extraction/download', methods=['GET'])
#     @admin_required
#     def admin_invoice_extraction_download():
#         from flask import send_file
#         from vim.extraction.json_store import ENRICHED_PATH, load_all, save_all

#         if not ENRICHED_PATH.exists():
#             save_all(load_all())
#         if not ENRICHED_PATH.exists():
#             flash("No extractions yet. Upload an invoice first.", "warning")
#             return redirect(url_for('admin_invoice_upload'))

#         return send_file(ENRICHED_PATH, as_attachment=True, download_name="enriched.json")

    # ---------------- INTELLIGENT INVOICE UPLOAD ----------------
    @app.route('/admin/invoice_upload', methods=['GET', 'POST'])
    @admin_required
    def admin_invoice_upload():
        from flask import current_app
        from vim.extraction import config as extraction_config

        results = []

        # Read directly from ..env file (avoids stale app.config from wrong server instance)
        llama_key, groq_key = extraction_config._read_keys()
        current_app.config["LLAMA_CLOUD_API_KEY"] = llama_key
        current_app.config["GROQ_API_KEY"] = groq_key
        extraction_config.LLAMA_CLOUD_API_KEY = llama_key
        extraction_config.GROQ_API_KEY = groq_key
        keys_ok = bool(llama_key and groq_key)

        if request.method == 'POST' and keys_ok:
            files = request.files.getlist('invoice_files')
            if not files or all(not f.filename for f in files):
                flash("Please select at least one invoice file.", "warning")
                return redirect(url_for('admin_invoice_upload'))

            from vim.extraction import jobs
            from vim.extraction.service import stage_upload

# --------------------------------------------------
# SAVE THE FILES, THEN EXTRACT IN THE BACKGROUND
#
# Extraction waits on three external APIs per document, so doing it inside
# this request left the browser on a blank page for the whole batch. The
# request now only stores the bytes and redirects to a progress page.
# --------------------------------------------------
            staged = []
            for f in files:
                if not f.filename:
                    continue
                try:
                    staged.append(stage_upload(f))
                except ValueError as e:
                    flash(str(e), "danger")
                except OSError as e:
                    flash(str(e).strip(), "danger")
                    break
                except Exception as e:
                    flash(f"Could not save {f.filename}: {e}", "danger")

            if not staged:
                return redirect(url_for('admin_invoice_upload'))

            job_id = jobs.create_job(staged)
            jobs.start_job(current_app._get_current_object(), job_id, staged)

            return redirect(url_for('admin_invoice_upload_progress', job_id=job_id))

        elif request.method == 'POST' and not keys_ok:
            flash(
                "API keys not loaded. Save .env in the project root and restart the server.",
                "danger",
            )

        return render_template(
            'invoice_upload.html',
            results=results,
            keys_ok=keys_ok,
            gemini_ok=bool(extraction_config.read_gemini_key()),
            gemini_model=extraction_config.GEMINI_MODEL,
            pending_not_invoice=_pending_with_content(),
            pending_new_vendor=_pending_new_vendors(),
        )

    @app.route('/admin/invoice_upload/progress/<job_id>', methods=['GET'])
    @admin_required
    def admin_invoice_upload_progress(job_id):
        """Progress page for a background upload job; polls the status endpoint."""
        from vim.extraction import jobs

        job = jobs.get_job(job_id)
        if not job:
            flash("That upload has expired. Please upload again.", "warning")
            return redirect(url_for('admin_invoice_upload'))

        if job["status"] != "complete":
            return render_template('invoice_upload_progress.html', job=job)

        # Finished: apply the same session and flash handling the synchronous
        # version used to do, then show the results.
        results = job["results"]

        if job.get("invoice_ids"):
            session["current_invoice_ids"] = job["invoice_ids"]
            session.modified = True

        if job.get("validation_error"):
            flash(
                f"Invoices were extracted, but validation failed: "
                f"{job['validation_error']}",
                "danger",
            )
        elif job.get("invoice_ids"):
            elapsed = job.get("elapsed_seconds")
            timing = f" in {elapsed}s" if elapsed is not None else ""
            flash(
                f"Successfully extracted and validated "
                f"{len(job['invoice_ids'])} invoice(s){timing}.",
                "success",
            )

        for entry in job["files"]:
            if entry["status"] in ("error", "extraction_failed", "db_error"):
                flash(
                    f"{entry['file_name']}: {entry.get('detail') or entry['status']}",
                    "danger",
                )

        _flash_vendor_registrations(results)
        _remember_pending_not_invoice(results)
        _remember_pending_new_vendor(results)

        from vim.extraction import config as extraction_config

        return render_template(
            'invoice_upload.html',
            results=results,
            keys_ok=True,
            gemini_ok=bool(extraction_config.read_gemini_key()),
            gemini_model=extraction_config.GEMINI_MODEL,
            pending_not_invoice=_pending_with_content(),
            elapsed_seconds=job.get("elapsed_seconds"),
            pending_new_vendor=_pending_new_vendors(),
        )

    @app.route('/admin/invoice_upload/status/<job_id>', methods=['GET'])
    @admin_required
    def admin_invoice_upload_status(job_id):
        """JSON status polled by the progress page."""
        from flask import jsonify
        from vim.extraction import jobs

        job = jobs.get_job(job_id)
        if not job:
            return jsonify({"status": "expired"}), 404

        elapsed = round(time.time() - job["created_at"], 1)
        return jsonify({
            "status": job["status"],
            "total": job["total"],
            "finished": job["finished"],
            "elapsed_seconds": job.get("elapsed_seconds") if job["status"] == "complete" else elapsed,
            "created_at": job.get("created_at"),
            "files": [
                {
                    "file_name": f["file_name"],
                    "status": f["status"],
                    "detail": f.get("detail"),
                    "elapsed_seconds": f.get("elapsed_seconds"),
                }
                for f in job["files"]
            ],
        })

    def _flash_vendor_registrations(records):
        """Tell the admin which vendors the upload added to the register."""
        created = []
        reactivated = []
        for r in records:
            name = r.get("vendor_name")
            if not name or r.get("invoice_id") is None:
                continue
            if r.get("_vendor_action") == "created":
                created.append(name)
            elif r.get("_vendor_action") == "reactivated":
                reactivated.append(name)

        if created:
            flash(
                "Registered new vendor(s) from the uploaded invoice(s): "
                f"{', '.join(sorted(set(created)))}. "
                "Review their GST number and contact details under Admin → Vendors.",
                "info",
            )
        if reactivated:
            flash(
                "Reactivated inactive vendor(s) found on the uploaded invoice(s): "
                f"{', '.join(sorted(set(reactivated)))}.",
                "info",
            )

    def _remember_pending_not_invoice(records):
        """Queue classifier-rejected uploads for an explicit user decision."""
        pending = [
            {
                "file_name": r.get("file_name"),
                "stored_file_name": r.get("stored_file_name"),
                "document_type": r.get("_document_type"),
                "reason": r.get("_not_invoice_reason"),
                "confidence": (r.get("_classification") or {}).get("confidence"),
            }
            for r in records
            if r.get("status") == "not_invoice" and r.get("stored_file_name")
        ]
        if pending:
            session['pending_not_invoice'] = pending
            session.modified = True

    def _remember_pending_new_vendor(records):
        """Queue unknown-vendor invoices for an explicit register-or-stop decision."""
        incoming = [
            {
                "file_name": r.get("file_name"),
                "stored_file_name": r.get("stored_file_name"),
                "vendor_name": r.get("vendor_name"),
                "invoice_number": r.get("invoice_number"),
                "total_due": r.get("total_due"),
                "currency": r.get("currency"),
            }
            for r in records
            if r.get("status") == "vendor_not_registered" and r.get("stored_file_name")
        ]
        if not incoming:
            return

        existing = {
            p.get("stored_file_name"): p
            for p in (session.get("pending_new_vendor") or [])
            if p.get("stored_file_name")
        }
        for item in incoming:
            existing[item["stored_file_name"]] = item
        session["pending_new_vendor"] = list(existing.values())
        session.modified = True
        flash(
            f"{len(incoming)} invoice(s) extracted from a vendor that is not "
            "registered. Choose whether to register them or stop.",
            "warning",
        )

    def _pending_new_vendors():
        """Queued unknown-vendor invoices plus details from enriched.json."""
        from vim.extraction.json_store import find_by_stored_name

        items = []
        for p in session.get("pending_new_vendor") or []:
            rec = find_by_stored_name(p.get("stored_file_name")) or {}
            items.append({
                **p,
                "vendor_name": rec.get("vendor_name") or p.get("vendor_name"),
                "vendor_gst_number": rec.get("vendor_gst_number"),
                "vendor_vat_number": rec.get("vendor_vat_number"),
                "vendor_address": rec.get("vendor_address"),
                "vendor_email": rec.get("vendor_email"),
                "vendor_phone_number": rec.get("vendor_phone_number"),
                "vendor_code": rec.get("vendor_code"),
                "invoice_number": rec.get("invoice_number") or p.get("invoice_number"),
                "invoice_date": rec.get("invoice_date"),
                "total_due": rec.get("total_due") if rec.get("total_due") is not None else p.get("total_due"),
                "currency": rec.get("currency") or p.get("currency"),
            })
        return items

    # Document text lives in enriched.json, not the session — the session is a
    # signed cookie and would overflow its ~4KB limit.
    PENDING_PREVIEW_CHARS = 4000

    def _pending_record_text(file_name, stored_file_name):
        """Fetch the parsed text of a queued document from enriched.json."""
        from vim.extraction.json_store import load_all

        for rec in load_all():
            key = rec.get("file_name") or rec.get("stored_file_name")
            if key and key in (file_name, stored_file_name):
                return (rec.get("raw_text") or "").strip()
        return ""

    def _pending_with_content():
        """Queued documents plus a preview of what the classifier read."""
        from vim.extraction import config as extraction_config

        items = []
        for p in session.get('pending_not_invoice') or []:
            text = _pending_record_text(
                p.get("file_name"), p.get("stored_file_name")
            )
            suffix = Path(p.get("stored_file_name") or "").suffix.lower()
            items.append({
                **p,
                "is_image": suffix in extraction_config.IMAGE_EXTENSIONS,
                "preview": text[:PENDING_PREVIEW_CHARS],
                "preview_truncated": len(text) > PENDING_PREVIEW_CHARS,
                "char_count": len(text),
            })
        return items

    # ---------------- IMAGE PREVIEW OF A QUEUED DOCUMENT ----------------
    @app.route('/admin/invoice_upload/pending_image')
    @admin_required
    def admin_invoice_upload_pending_image():
        from vim.extraction.service import resolve_pending_upload

        stored_name = request.args.get('stored_file_name')

        queued = any(
            p.get('stored_file_name') == stored_name
            for p in (session.get('pending_not_invoice') or [])
        )
        if not queued:
            return Response("Not awaiting a decision.", status=404,
                            mimetype='text/plain')

        path = resolve_pending_upload(stored_name)
        if path is None or path.suffix.lower() not in (
            '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.tif'
        ):
            return Response("No image available.", status=404,
                            mimetype='text/plain')

        # Served from memory rather than send_file: Windows keeps a handle on
        # the open file, which can block deleting it on "Stop & discard".
        mime = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        return Response(path.read_bytes(), mimetype=mime)

    # ---------------- FULL TEXT OF A QUEUED DOCUMENT ----------------
    @app.route('/admin/invoice_upload/pending_text')
    @admin_required
    def admin_invoice_upload_pending_text():
        stored_name = request.args.get('stored_file_name')

        entry = next(
            (
                p for p in (session.get('pending_not_invoice') or [])
                if p.get('stored_file_name') == stored_name
            ),
            None,
        )
        if entry is None:
            return Response(
                "That upload is no longer awaiting a decision.",
                status=404,
                mimetype='text/plain',
            )

        text = _pending_record_text(
            entry.get('file_name'), entry.get('stored_file_name')
        )
        header = f"--- {entry.get('file_name')} - text read by the AI check ---\n\n"
        return Response(
            header + (text or "(no text was extracted from this document)"),
            content_type='text/plain; charset=utf-8',
        )

    # ---------------- NOT-AN-INVOICE DECISION ----------------
    @app.route('/admin/invoice_upload/decide', methods=['POST'])
    @admin_required
    def admin_invoice_upload_decide():
        from vim.extraction.service import (
            discard_pending_upload,
            resolve_pending_upload,
        )

        action = request.form.get('action')
        stored_name = request.form.get('stored_file_name')

        pending = session.get('pending_not_invoice') or []
        entry = next(
            (p for p in pending if p.get('stored_file_name') == stored_name),
            None,
        )

        # Only files this session flagged are actionable, so a forged
        # stored_file_name cannot be pushed through the pipeline.
        if entry is None:
            flash("That upload is no longer awaiting a decision.", "warning")
            return redirect(url_for('admin_invoice_upload'))

        original_name = entry.get('file_name') or stored_name

        if action == 'stop':
            discard_pending_upload(
                stored_name, original_name, user_id=session.get("user_id")
            )
            flash(
                f"Stopped '{original_name}'. It was kept in Rejected Documents "
                "for later review and was not saved as an invoice.",
                "info",
            )

        elif action == 'proceed':
            saved_path = resolve_pending_upload(stored_name)
            if saved_path is None:
                flash(
                    f"'{original_name}' is no longer available on disk. "
                    "Please upload it again.",
                    "danger",
                )
            else:
                _force_process(saved_path, original_name)

        else:
            flash("Unknown action.", "warning")

        session['pending_not_invoice'] = [
            p for p in pending if p.get('stored_file_name') != stored_name
        ]
        session.modified = True

        return redirect(url_for('admin_invoice_upload'))

    @app.route('/admin/invoice_upload/vendor_decide', methods=['POST'])
    @admin_required
    def admin_invoice_upload_vendor_decide():
        from vim.extraction.service import (
            discard_pending_upload,
            persist_approved_vendor,
        )

        action = request.form.get('action')
        stored_name = request.form.get('stored_file_name')

        pending = session.get('pending_new_vendor') or []
        entry = next(
            (p for p in pending if p.get('stored_file_name') == stored_name),
            None,
        )
        if entry is None:
            flash("That upload is no longer awaiting a vendor decision.", "warning")
            return redirect(url_for('admin_invoice_upload'))

        original_name = entry.get('file_name') or stored_name
        vendor_name = entry.get('vendor_name') or 'this vendor'

        if action == 'stop':
            discard_pending_upload(
                stored_name, original_name, user_id=session.get("user_id")
            )
            flash(
                f"Stopped '{original_name}'. {vendor_name} was not registered. "
                "The document was kept in Rejected Documents for later review.",
                "info",
            )

        elif action == 'proceed':
            try:
                record = persist_approved_vendor(
                    stored_name, original_name, user_id=session.get("user_id")
                )
            except Exception as e:
                flash(f"Could not register {vendor_name}: {e}", "danger")
                return redirect(url_for('admin_invoice_upload'))

            invoice_id = record.get("invoice_id")
            if invoice_id is None:
                flash(
                    f"Registered '{vendor_name}' but the invoice was not saved: "
                    f"{record.get('_db_error') or record.get('status')}",
                    "warning",
                )
            else:
                session["current_invoice_ids"] = [int(invoice_id)]
                session.modified = True
                try:
                    from vim.validation_setup.validation.run_validation import (
                        run_validation,
                    )
                    run_validation()
                    flash(
                        f"Registered '{vendor_name}' and saved invoice "
                        f"{record.get('invoice_number') or invoice_id}.",
                        "success",
                    )
                except Exception as e:
                    flash(
                        f"Registered '{vendor_name}' and saved the invoice, "
                        f"but validation failed: {e}",
                        "danger",
                    )
        else:
            flash("Unknown action.", "warning")

        session['pending_new_vendor'] = [
            p for p in pending if p.get('stored_file_name') != stored_name
        ]
        session.modified = True
        return redirect(url_for('admin_invoice_upload'))

    def _force_process(saved_path, original_name):
        """Run the pipeline on a rejected document the user chose to keep."""
        from vim.extraction.service import process_saved_file

        try:
            record = process_saved_file(
                saved_path, original_name, skip_invoice_check=True
            )
        except Exception as e:
            flash(f"Failed to process '{original_name}': {e}", "danger")
            return

        invoice_id = record.get("invoice_id")
        if invoice_id is None:
            if record.get("status") == "vendor_not_registered":
                _remember_pending_new_vendor([record])
                return
            reason = (
                record.get("_extraction_error")
                or record.get("_db_error")
                or record.get("status")
                or "unknown error"
            )
            flash(
                f"Processed '{original_name}' but nothing was saved: {reason}",
                "warning",
            )
            return

        session["current_invoice_ids"] = [int(invoice_id)]
        session.modified = True
        _flash_vendor_registrations([record])
        from vim.extraction.rejections import DECISION_PROCEEDED, mark_decision
        mark_decision(
            saved_path.name, DECISION_PROCEEDED, user_id=session.get("user_id")
        )

        try:
            from vim.validation_setup.validation.run_validation import run_validation
            run_validation()
            flash(
                f"Processed '{original_name}' as an invoice and saved it "
                f"(invoice ID {invoice_id}).",
                "success",
            )
        except Exception as e:
            flash(
                f"Saved '{original_name}' (invoice ID {invoice_id}), "
                f"but validation failed: {e}",
                "danger",
            )

    def _document_type_label(record):
        """Prefer the label printed on the document, fall back to the code."""
        from vim.extraction.schema import DOCUMENT_TYPE_CODES

        label = (record.get("document_type") or "").strip()
        if label:
            return label

        code = record.get("document_type_code")
        return DOCUMENT_TYPE_CODES.get(code, "—")

    # ---------------- INVOICE DATA EXTRACTION REVIEW ----------------
    @app.route('/admin/invoice_extraction', methods=['GET'])
    @admin_required
    def admin_invoice_extraction():
        from vim.extraction.json_store import load_all, ENRICHED_PATH

        records = load_all()
        rows = []
        for i, rec in enumerate(reversed(records)):
            rows.append({
                "index": len(records) - 1 - i,
                "file_name": rec.get("file_name") or rec.get("stored_file_name") or "—",
                "document_type": _document_type_label(rec),
                "vendor_name": rec.get("vendor_name") or "—",
                "invoice_number": rec.get("invoice_number") or "—",
                "invoice_date": rec.get("invoice_date") or "—",
                "amount": rec.get("total_due") or "—",
                "currency": rec.get("currency") or "",
                "status": "Failed" if rec.get("_extraction_error") else (
                    "NeedsReview" if rec.get("_validation_issues") else "Success"
                ),
                "line_item_count": len(rec.get("line_items") or []),
            })

        return render_template(
            'invoice_extraction.html',
            extractions=rows,
            json_path=str(ENRICHED_PATH),
        )

    @app.route('/admin/invoice_extraction/<int:record_index>', methods=['GET'])
    @admin_required
    def admin_invoice_extraction_detail(record_index):
        import json
        from vim.extraction.json_store import load_all

        records = load_all()
        if record_index < 0 or record_index >= len(records):
            flash("Extraction record not found.", "warning")
            return redirect(url_for('admin_invoice_extraction'))

        from vim.extraction.schema import HEADER_FIELD_GROUPS

        record = records[record_index]
        return render_template(
            'invoice_extraction_detail.html',
            record=record,
            record_index=record_index,
            record_json=json.dumps(record, indent=2, default=str),
            header_field_groups=HEADER_FIELD_GROUPS,
        )

    @app.route('/admin/invoice_extraction/download', methods=['GET'])
    @admin_required
    def admin_invoice_extraction_download():
        from flask import send_file
        from vim.extraction.json_store import ENRICHED_PATH, load_all, save_all

        if not ENRICHED_PATH.exists():
            save_all(load_all())
        if not ENRICHED_PATH.exists():
            flash("No extractions yet. Upload an invoice first.", "warning")
            return redirect(url_for('admin_invoice_upload'))

        return send_file(ENRICHED_PATH, as_attachment=True, download_name="enriched.json")

    # ---------------- REJECTED DOCUMENTS ----------------
    @app.route('/admin/rejected_documents', methods=['GET'])
    @admin_required
    def admin_rejected_documents():
        rows = (
            RejectedDocument.query
            .order_by(RejectedDocument.CreatedDate.desc())
            .all()
        )
        return render_template('rejected_documents.html', rows=rows)

    @app.route('/admin/rejected_documents/<int:rejection_id>', methods=['GET'])
    @admin_required
    def admin_rejected_document_detail(rejection_id):
        import json

        row = db.session.get(RejectedDocument, rejection_id)
        if row is None:
            flash("Rejected document not found.", "warning")
            return redirect(url_for('admin_rejected_documents'))

        payload = row.ExtractedJson or {}
        return render_template(
            'rejected_document_detail.html',
            row=row,
            payload=payload,
            payload_json=json.dumps(payload, indent=2, default=str),
        )


    # ---------------- INVOICE VALIDATION ----------------
    @app.route('/admin/invoice_validation', methods=['GET'])
    @admin_required
    def admin_invoice_validation():
    # --------------------------------------------------
    # GET ONLY THE LATEST UPLOADED INVOICE IDS
    # --------------------------------------------------
        current_invoice_ids = session.get(
            "current_invoice_ids",[])

        print(
            "Invoice Validation - current invoice IDs:",current_invoice_ids)

    # --------------------------------------------------
    # NO CURRENT UPLOAD
    # --------------------------------------------------
        if not current_invoice_ids:
            return render_template("invoice_validation.html",validation_results=[])

    # --------------------------------------------------
    # FETCH ONLY VALIDATION RESULTS FOR CURRENT UPLOAD
    # --------------------------------------------------

        validation_results = (ValidationResult.query.filter(ValidationResult.InvoiceID.in_(current_invoice_ids))
                              .order_by(ValidationResult.ValidationID.desc()).all())

    # --------------------------------------------------
    # CONVERT DB RESULTS TO FRONTEND ROWS
    # --------------------------------------------------

        rows = []
        for result in validation_results:
            rows.append({
                "validation_id": result.ValidationID,
                "invoice_id": result.InvoiceID,
                "invoice_number": result.InvoiceNumber,
                "validation_type": result.ValidationType,
                "status": result.ValidationStatus,
                "message": result.ValidationMessage,
                "validation_date": result.ValidationDate})

        print("Invoice Validation - records displayed:",len(rows))

        return render_template("invoice_validation.html",validation_results=rows)


    # ─────────────────────────────────────────────────────────────────────────────
    # RAG — AI Assistant  (ChromaDB + CrewAI + Gemini)
    # ─────────────────────────────────────────────────────────────────────────────

    @app.route('/admin/ai_assistant', methods=['GET'])
    @admin_required
    def admin_ai_assistant():
        """Landing page: vendor selector + per-vendor RAG stats."""
        from vim.rag.store import get_vendor_data
        vendors = Vendor.query.order_by(Vendor.VendorName).all()

        vendor_id = request.args.get('vendor_id', '').strip().lower().replace(' ', '_')
        data = None
        selected_vendor = None
        if vendor_id:
            try:
                data = get_vendor_data(vendor_id)
            except Exception as e:
                flash(f"RAG store error: {e}", "danger")
            selected_vendor = vendor_id

        return render_template(
            'vim_rag_assistant.html',
            vendors=vendors,
            selected_vendor=selected_vendor,
            data=data,
        )

    @app.route('/admin/rag_ingest', methods=['POST'])
    @admin_required
    def admin_rag_ingest():
        """Ingest PDF/TXT invoice files or pasted text into ChromaDB."""
        import io as _io
        from pathlib import Path as _Path
        from vim.rag.store import ingest_invoice

        vendor_id = request.form.get('vendor_id', '').strip().lower().replace(' ', '_')
        invoice_number = request.form.get('invoice_number', '').strip()
        raw_text = request.form.get('raw_text', '').strip()
        files = request.files.getlist('invoice_files')
        results = []

        if files:
            for f in files:
                if not f.filename:
                    continue
                stem = _Path(f.filename).stem
                inv_num = invoice_number if invoice_number else stem
                content = f.read()

                text = ""
                if f.filename.lower().endswith('.pdf'):
                    try:
                        from pypdf import PdfReader
                        reader = PdfReader(_io.BytesIO(content))
                        text = "\n".join(page.extract_text() or "" for page in reader.pages)
                    except Exception as e:
                        results.append(f"❌ <b>{f.filename}</b>: PDF extraction error — {e}")
                        continue
                elif f.filename.lower().endswith('.txt'):
                    text = content.decode('utf-8', errors='replace')
                else:
                    results.append(f"❌ <b>{f.filename}</b>: Unsupported format (use PDF or TXT).")
                    continue

                if not text.strip():
                    results.append(f"❌ <b>{f.filename}</b>: File was empty.")
                    continue

                try:
                    chunks = ingest_invoice(tenant_id=vendor_id, invoice_number=inv_num, text=text)
                    results.append(
                        f"✅ <b>{f.filename}</b> (Invoice: <code>{inv_num}</code>) "
                        f"→ Indexed <b>{chunks}</b> chunk(s) under <code>vendor_id='{vendor_id}'</code>"
                    )
                except Exception as e:
                    results.append(f"❌ <b>{f.filename}</b>: Ingestion error — {e}")

        if raw_text:
            inv_num = invoice_number if invoice_number else "PASTED-INV"
            try:
                chunks = ingest_invoice(tenant_id=vendor_id, invoice_number=inv_num, text=raw_text)
                results.append(
                    f"✅ Pasted Text (Invoice: <code>{inv_num}</code>) "
                    f"→ Indexed <b>{chunks}</b> chunk(s) under <code>vendor_id='{vendor_id}'</code>"
                )
            except Exception as e:
                results.append(f"❌ Pasted Text Error: {e}")

        if not results:
            results.append("⚠️ No files or text were provided.")

        vendors = Vendor.query.order_by(Vendor.VendorName).all()
        return render_template(
            'vim_rag_ingest_results.html',
            vendor_id=vendor_id,
            results=results,
            vendors=vendors,
        )

    @app.route('/admin/rag_query', methods=['POST'])
    @admin_required
    def admin_rag_query():
        """Query the RAG — retrieves from ChromaDB then synthesizes via CrewAI."""
        from vim.rag.store import retrieve_chunks
        from vim.rag.query_crew import QueryCrew

        vendor_id = request.form.get('vendor_id', '').strip().lower().replace(' ', '_')
        query = request.form.get('query', '').strip()
        invoice_filter = request.form.get('invoice_filter', '').strip() or None

        if not vendor_id or not query:
            flash("Vendor and question are required.", "warning")
            return redirect(url_for('admin_ai_assistant'))

        # Retrieve raw chunks
        raw_chunks = []
        try:
            raw_chunks = retrieve_chunks(
                tenant_id=vendor_id,
                query=query,
                invoice_number=invoice_filter,
                top_k=3,
            )
            for c in raw_chunks:
                dist = c.get("distance")
                c["score_str"] = f"{1 - dist:.3f}" if dist is not None else "N/A"
        except Exception as e:
            flash(f"Retrieval error: {e}", "danger")

        # Synthesize with CrewAI
        answer = ""
        try:
            crew = QueryCrew()
            answer = crew.run(
                tenant_id=vendor_id,
                query=query,
                invoice_number=invoice_filter,
            )
        except Exception as e:
            answer = f"Agent execution error: {e}"

        vendors = Vendor.query.order_by(Vendor.VendorName).all()
        return render_template(
            'vim_rag_query_results.html',
            vendor_id=vendor_id,
            query=query,
            filter_display=invoice_filter or "All Invoices",
            answer=answer,
            raw_chunks=raw_chunks,
            vendors=vendors,
        )

    # ─────────────────────────────────────────────────────────────────────────────
    # VALIDATION ISSUES API  (serves the Event Browser on /admin/issues)
    # Reads from the main vim_database.sqlite → validation_result table
    # ─────────────────────────────────────────────────────────────────────────────

    @app.route('/api/validation/results', methods=['GET'])
    @admin_required
    def api_validation_list():
        """Paginated, filtered list of ValidationResult records."""
        from vim_database.models import ValidationResult
        from datetime import datetime, timedelta
        from sqlalchemy import or_

        q           = request.args.get('q', '').strip()
        status      = request.args.get('status', '').strip()
        vtype       = request.args.get('type', '').strip()
        time_range  = request.args.get('time', '').strip()
        page        = max(1, int(request.args.get('page', 1)))
        page_size   = min(500, max(1, int(request.args.get('page_size', 25))))

        from flask import jsonify as _jsonify
        query = db.session.query(ValidationResult)

        if q:
            like = f"%{q}%"
            query = query.filter(
                or_(
                    ValidationResult.InvoiceNumber.ilike(like),
                    ValidationResult.ValidationID.cast(db.String).ilike(like),
                )
            )
        if status:
            query = query.filter(ValidationResult.ValidationStatus == status)
        if vtype:
            query = query.filter(ValidationResult.ValidationType == vtype)
        if time_range:
            time_map = {
                '15m': timedelta(minutes=15),
                '1h':  timedelta(hours=1),
                '24h': timedelta(hours=24),
                '3d':  timedelta(days=3),
            }
            delta = time_map.get(time_range)
            if delta:
                cutoff = datetime.utcnow() - delta
                query = query.filter(ValidationResult.ValidationDate >= cutoff)

        total = query.count()
        records = (
            query.order_by(ValidationResult.ValidationDate.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        items = []
        for r in records:
            items.append({
                'id':              r.ValidationID,
                'invoice_id':      r.InvoiceID,
                'invoice_number':  r.InvoiceNumber,
                'validation_type': r.ValidationType,
                'status':          r.ValidationStatus,
                'message':         r.ValidationMessage,
                'details':         r.ValidationDetails,
                'validation_date': r.ValidationDate.isoformat() if r.ValidationDate else None,
            })

        return _jsonify({
            'total':     total,
            'page':      page,
            'page_size': page_size,
            'items':     items,
        })

    @app.route('/api/validation/results/<int:validation_id>', methods=['GET'])
    @admin_required
    def api_validation_detail(validation_id):
        """Return full detail for a single ValidationResult record."""
        from vim_database.models import ValidationResult
        from flask import jsonify as _jsonify

        r = db.session.get(ValidationResult, validation_id)
        if not r:
            return _jsonify({'error': 'Validation result not found'}), 404

        return _jsonify({
            'id':              r.ValidationID,
            'invoice_id':      r.InvoiceID,
            'invoice_number':  r.InvoiceNumber,
            'validation_type': r.ValidationType,
            'status':          r.ValidationStatus,
            'message':         r.ValidationMessage,
            'details':         r.ValidationDetails,
            'validation_date': r.ValidationDate.isoformat() if r.ValidationDate else None,
        })

    @app.route('/api/validation/facets', methods=['GET'])
    @admin_required
    def api_validation_facets():
        """Distinct values for ValidationStatus and ValidationType filter dropdowns."""
        from vim_database.models import ValidationResult
        from flask import jsonify as _jsonify

        statuses = [
            r[0] for r in
            db.session.query(ValidationResult.ValidationStatus).distinct().all()
            if r[0]
        ]
        types = [
            r[0] for r in
            db.session.query(ValidationResult.ValidationType).distinct().all()
            if r[0]
        ]

        return _jsonify({'statuses': statuses, 'types': types})
