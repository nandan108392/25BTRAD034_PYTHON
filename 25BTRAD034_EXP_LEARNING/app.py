import os
import uuid
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import (
    Flask,
    jsonify,
    render_template,
    session,
    redirect,
    url_for,
    flash,
    request,
    send_from_directory,
    abort,
)
from werkzeug.utils import secure_filename
import database
import smart_classifier
import city_analytics
from auth import auth_bp, login_required, admin_required

# Load environment variables from .env file if present
load_dotenv()

# Configure production logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cityos")

app = Flask(__name__)

# Environment & Secret Key configuration
flask_env = os.environ.get("FLASK_ENV", "development").lower()
secret_key = os.environ.get("SECRET_KEY")

if flask_env == "production":
    insecure_keys = {
        "cityos-dev-key-default",
        "dev-secret-key-change-in-production",
        "replace-with-a-secure-random-64-character-hex-key-in-production",
    }
    if not secret_key or secret_key in insecure_keys:
        raise RuntimeError(
            "CRITICAL SECURITY ERROR: A secure, unique SECRET_KEY environment variable is mandatory in production mode."
        )
    app.config["SECRET_KEY"] = secret_key
else:
    app.config["SECRET_KEY"] = secret_key or "cityos-dev-key-default"

# Session & Cookie Security Hardening
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
is_secure_cookie = os.environ.get("SESSION_COOKIE_SECURE", "0").lower() in ("true", "1", "yes")
app.config["SESSION_COOKIE_SECURE"] = is_secure_cookie
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)

# File upload configuration
UPLOAD_FOLDER = os.path.join(app.root_path, "uploads")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB max upload

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize SQLite database and tables automatically on startup
database.init_app(app)

# Register Authentication Blueprint
app.register_blueprint(auth_bp)

# Status tracker ordered lifecycle steps
TRACKER_STAGES = ["Reported", "Under Review", "In Progress", "Resolved"]


def allowed_file(filename):
    """Check if the uploaded file has an allowed image extension."""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.after_request
def add_security_headers(response):
    """Inject standard defensive HTTP security response headers."""
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.template_filter("format_report_id")
def jinja_format_report_id(db_id, created_at=None):
    """Jinja template filter to format report ID as CITY-YYYY-00001."""
    return database.format_report_id(db_id, created_at)


@app.errorhandler(403)
def forbidden_error(e):
    """Render friendly 403 Forbidden page."""
    return render_template("403.html"), 403


@app.errorhandler(404)
def not_found_error(e):
    """Render friendly 404 Not Found page."""
    return render_template("404.html"), 404


@app.errorhandler(413)
def payload_too_large_error(e):
    """Render friendly 413 Payload Too Large page."""
    return render_template("413.html"), 413


@app.errorhandler(500)
def internal_server_error(e):
    """Render friendly 500 Internal Server Error page and log incident."""
    logger.error(f"Internal Server Error: {str(e)}", exc_info=True)
    return render_template("500.html"), 500


@app.context_processor
def inject_notifications():
    """Inject unread notification count globally for authenticated users."""
    user_id = session.get("user_id")
    unread_count = 0
    if user_id:
        try:
            db = database.get_db()
            unread_count = database.get_unread_notification_count(db, user_id)
        except Exception:
            unread_count = 0
    return {"unread_notifications_count": unread_count}


@app.route("/")
def index():
    """Renders the CityOS dashboard landing view."""
    return render_template(
        "index.html",
        system_name="CityOS",
        version="0.1.0",
        server_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    ) 


@app.route("/dashboard")
@login_required
def citizen_dashboard():
    """
    Citizen Dashboard view displaying real-time personal statistics,
    latest reports, in-app notifications, and municipal service links.
    Redirects admin accounts to /admin.
    """
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))

    user_id = session.get("user_id")
    db = database.get_db()

    # Dynamic statistics for logged-in citizen
    stats = {
        "total": 0,
        "reported": 0,
        "in_progress": 0,
        "resolved": 0,
    }

    # Query total reports count
    total_row = db.execute(
        "SELECT COUNT(*) as count FROM reports WHERE user_id = ?", (user_id,)
    ).fetchone()
    stats["total"] = total_row["count"] if total_row else 0

    # Query count grouped by status
    status_rows = db.execute(
        "SELECT status, COUNT(*) as count FROM reports WHERE user_id = ? GROUP BY status",
        (user_id,),
    ).fetchall()

    for row in status_rows:
        st = row["status"]
        if st == "Reported":
            stats["reported"] = row["count"]
        elif st == "In Progress":
            stats["in_progress"] = row["count"]
        elif st == "Resolved":
            stats["resolved"] = row["count"]

    # Retrieve latest 5 reports for the current user
    recent_reports = db.execute(
        """
        SELECT *
        FROM reports
        WHERE user_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT 5
        """,
        (user_id,),
    ).fetchall()

    # Retrieve recent notifications & unread count
    recent_notifications = database.get_user_notifications(db, user_id, limit=3)
    unread_count = database.get_unread_notification_count(db, user_id)

    return render_template(
        "dashboard.html",
        user_name=session.get("name"),
        user_email=session.get("email"),
        user_role=session.get("role"),
        stats=stats,
        recent_reports=recent_reports,
        recent_notifications=recent_notifications,
        unread_count=unread_count,
    )


@app.route("/report", methods=["GET", "POST"])
@login_required
def report_problem():
    """
    Citizen Report Submission view.
    Validates form data, processes optional image uploads, attaches GPS coordinates,
    runs offline Smart Classifier, persists to SQLite, logs initial status history,
    and dispatches initial citizen notification.
    """
    if request.method == "POST":
        category = request.form.get("category", "").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        location = request.form.get("location", "").strip()
        location_desc = request.form.get("location_description", "").strip()
        latitude_raw = request.form.get("latitude", "").strip()
        longitude_raw = request.form.get("longitude", "").strip()

        error = None

        # Field validation
        if not title:
            error = "Problem title is required."
        elif not description:
            error = "Problem description is required."
        elif not location:
            error = "Location is required."
        elif category and category not in database.REPORT_CATEGORIES and category != "Auto-Detect":
            error = "Please select a valid report category from the list."

        # Parse and validate optional coordinates
        lat = None
        lon = None
        if error is None:
            if latitude_raw:
                try:
                    lat_val = float(latitude_raw)
                    if not (-90 <= lat_val <= 90):
                        error = "Latitude must be between -90 and 90 degrees."
                    else:
                        lat = lat_val
                except ValueError:
                    error = "Latitude must be a valid numerical value."

            if error is None and longitude_raw:
                try:
                    lon_val = float(longitude_raw)
                    if not (-180 <= lon_val <= 180):
                        error = "Longitude must be between -180 and 180 degrees."
                    else:
                        lon = lon_val
                except ValueError:
                    error = "Longitude must be a valid numerical value."

            if error is None:
                if (lat is not None and lon is None) or (lat is None and lon is not None):
                    error = "Both latitude and longitude are required to attach GPS coordinates."

        # Run Smart Complaint Intelligence Engine
        classification = smart_classifier.classify_complaint(description, title)

        # If category is omitted or "Auto-Detect", use smart-detected category
        if not category or category == "Auto-Detect":
            category = classification["category"]
        elif category not in database.REPORT_CATEGORIES:
            category = classification["category"]

        issue_type = classification["issue_type"]
        priority = classification["priority"]
        keywords_str = ", ".join(classification["keywords"])

        # Image upload validation & processing
        image_path = None
        if error is None and "image" in request.files:
            file = request.files["image"]
            if file and file.filename != "":
                if not allowed_file(file.filename):
                    error = "Invalid image file type. Allowed formats: PNG, JPG, JPEG."
                else:
                    orig_filename = secure_filename(file.filename)
                    unique_filename = f"{uuid.uuid4().hex[:12]}_{orig_filename}"
                    file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_filename))
                    image_path = f"/uploads/{unique_filename}"

        if error is not None:
            flash(error, "danger")
            return render_template(
                "report.html",
                categories=database.REPORT_CATEGORIES,
                smart_categories=database.SMART_CATEGORIES,
                category=category,
                title=title,
                description=description,
                location=location,
                location_description=location_desc,
                latitude=latitude_raw,
                longitude=longitude_raw,
            )

        # Database insertion with automatic initial status "Reported" and location metadata
        user_id = session.get("user_id")
        now = datetime.now().isoformat()
        initial_status = "Reported"

        db = database.get_db()
        cursor = db.execute(
            """
            INSERT INTO reports (user_id, category, title, description, location, image, status, issue_type, priority, keywords, latitude, longitude, location_description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, category, title, description, location, image_path, initial_status, issue_type, priority, keywords_str, lat, lon, location_desc, now, now),
        )
        db.commit()
        report_id = cursor.lastrowid
        formatted_id = database.format_report_id(report_id, now)

        # Record initial status in report_history
        database.add_report_history(db, report_id, None, initial_status, user_id)

        # Dispatch initial in-app notification to citizen
        database.create_notification(
            db,
            user_id,
            report_id,
            f"Report Logged: {formatted_id}",
            f"Your complaint '{title}' has been successfully received and logged into the municipal system.",
        )

        flash("Your report has been submitted and analyzed successfully.", "success")
        return redirect(url_for("report_success", report_id=report_id))

    return render_template(
        "report.html",
        categories=database.REPORT_CATEGORIES,
        smart_categories=database.SMART_CATEGORIES,
    )


@app.route("/report/success/<int:report_id>")
@login_required
def report_success(report_id):
    """Confirmation page shown immediately after successful report submission."""
    user_id = session.get("user_id")
    user_role = session.get("role")
    db = database.get_db()

    report = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
    if report is None:
        abort(404)
    if report["user_id"] != user_id and user_role != "admin":
        abort(403)

    formatted_id = database.format_report_id(report["id"], report["created_at"])
    return render_template("report_success.html", report=report, formatted_id=formatted_id)


@app.route("/my-reports")
@login_required
def my_reports():
    """View all reports submitted by the logged-in citizen, sorted newest first."""
    user_id = session.get("user_id")
    db = database.get_db()

    reports = db.execute(
        """
        SELECT * FROM reports
        WHERE user_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        """,
        (user_id,),
    ).fetchall()

    return render_template(
        "my_reports.html",
        reports=reports,
        user_name=session.get("name"),
    )


@app.route("/report/<int:report_id>")
@app.route("/reports/<int:report_id>")
@login_required
def view_report(report_id):
    """
    Detailed report view with visual multi-step status tracking,
    status transition history audit log, smart analysis,
    image evidence display, municipal operations progress, and ownership access security.
    """
    user_id = session.get("user_id")
    user_role = session.get("role")
    db = database.get_db()

    report = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()

    if report is None:
        abort(404)

    # Enforce strict ownership / role check
    if report["user_id"] != user_id and user_role != "admin":
        abort(403)

    formatted_id = database.format_report_id(report["id"], report["created_at"])

    # 5-Stage Citizen Transparency Lifecycle:
    # 1. Submitted (Reported)
    # 2. Verified (Under Review)
    # 3. Assigned (Assigned / Accepted)
    # 4. In Progress (In Progress / Work Completed / Verification Required)
    # 5. Resolved (Verified / Resolved)
    TIMELINE_5_STAGES = [
        {"name": "Submitted", "label": "Submitted", "desc": "Complaint logged"},
        {"name": "Verified", "label": "Verified", "desc": "Municipal review"},
        {"name": "Assigned", "label": "Assigned", "desc": "Field team dispatched"},
        {"name": "In Progress", "label": "In Progress", "desc": "Active resolution"},
        {"name": "Resolved", "label": "Resolved", "desc": "Issue addressed"},
    ]

    current_status = report["status"]
    is_rejected = current_status == "Rejected"
    is_resolved = current_status in ("Resolved", "Verified")

    # Stage level mapping
    status_order_map = {
        "Reported": 0,
        "Under Review": 1,
        "Assigned": 2,
        "Accepted": 2,
        "In Progress": 3,
        "Work Completed": 3,
        "Verification Required": 3,
        "Verified": 4,
        "Resolved": 4,
    }
    current_level = status_order_map.get(current_status, 0)

    tracker_info = []
    for idx, stage in enumerate(TIMELINE_5_STAGES):
        if is_rejected:
            state = "rejected"
        elif is_resolved:
            state = "completed"
        elif idx < current_level:
            state = "completed"
        elif idx == current_level:
            state = "active"
        else:
            state = "upcoming"
        tracker_info.append({
            "name": stage["name"],
            "label": stage["label"],
            "desc": stage["desc"],
            "state": state,
            "step": idx + 1,
        })

    # Retrieve status transition history audit trail
    status_history = database.get_report_history(db, report_id)

    # Phase 3: Retrieve municipal operations data
    assignment_details = database.get_report_assignment_details(db, report_id)
    public_updates = database.get_report_updates(db, report_id, public_only=True)
    resolution_evidence = database.get_resolution_evidence(db, report_id, verified_only=False)

    keywords_raw = report["keywords"] if "keywords" in report.keys() and report["keywords"] else ""
    keywords_list = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    issue_type = report["issue_type"] if "issue_type" in report.keys() and report["issue_type"] else "General Issue"
    priority = (report["priority"] if "priority" in report.keys() and report["priority"] else "MEDIUM").upper()

    return render_template(
        "report_detail.html",
        report=report,
        formatted_id=formatted_id,
        tracker_info=tracker_info,
        status_history=status_history,
        assignment_details=assignment_details,
        public_updates=public_updates,
        resolution_evidence=resolution_evidence,
        is_rejected=is_rejected,
        current_status=current_status,
        keywords_list=keywords_list,
        issue_type=issue_type,
        priority=priority,
    )


@app.route("/notifications")
@login_required
def notifications_view():
    """
    Citizen Notifications Center.
    Displays in-app lifecycle status notifications, newest first.
    """
    user_id = session.get("user_id")
    db = database.get_db()
    notifs = database.get_user_notifications(db, user_id, limit=50)
    unread_count = database.get_unread_notification_count(db, user_id)

    return render_template(
        "notifications.html",
        notifications=notifs,
        unread_count=unread_count,
        user_name=session.get("name"),
    )


@app.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    """Marks a single notification as read, ensuring citizen ownership."""
    user_id = session.get("user_id")
    db = database.get_db()

    notif = db.execute("SELECT * FROM notifications WHERE id = ?", (notification_id,)).fetchone()
    if notif is None:
        abort(404)
    if notif["user_id"] != user_id:
        abort(403)

    database.mark_notification_as_read(db, notification_id, user_id)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({"success": True, "id": notification_id})

    flash("Notification marked as read.", "success")
    return redirect(url_for("notifications_view"))


@app.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_notifications_read():
    """Marks all notifications as read for the logged-in citizen."""
    user_id = session.get("user_id")
    db = database.get_db()

    database.mark_all_notifications_as_read(db, user_id)

    if request.headers.get("X-Requested-With") == "XMLHttpRequest" or request.is_json:
        return jsonify({"success": True})

    flash("All notifications marked as read.", "success")
    return redirect(url_for("notifications_view"))


@app.route("/api/notifications/unread-count")
@login_required
def api_unread_notifications_count():
    """JSON API endpoint returning unread notifications count for live UI badge."""
    user_id = session.get("user_id")
    db = database.get_db()
    count = database.get_unread_notification_count(db, user_id)
    return jsonify({"unread_count": count})


@app.route("/admin")
@admin_required
def admin_dashboard():
    """
    CityOS Administration Dashboard.
    Provides system-wide operational statistics, parameterized search & filtering,
    department-level filtering, and report triage table.
    """
    db = database.get_db()

    # Dynamic system-wide statistics (covers all operational stages)
    stats = {
        "total": 0,
        "reported": 0,
        "under_review": 0,
        "assigned": 0,
        "in_progress": 0,
        "verification_pending": 0,
        "resolved": 0,
        "rejected": 0,
    }

    # Query total count
    row_total = db.execute("SELECT COUNT(*) as count FROM reports").fetchone()
    stats["total"] = row_total["count"] if row_total else 0

    # Query status distribution
    status_counts = db.execute(
        "SELECT status, COUNT(*) as count FROM reports GROUP BY status"
    ).fetchall()

    for row in status_counts:
        st = row["status"]
        c = row["count"]
        if st == "Reported":
            stats["reported"] += c
        elif st == "Under Review":
            stats["under_review"] += c
        elif st in ("Assigned", "Accepted"):
            stats["assigned"] += c
        elif st in ("In Progress", "Work Completed"):
            stats["in_progress"] += c
        elif st == "Verification Required":
            stats["verification_pending"] += c
        elif st in ("Resolved", "Verified"):
            stats["resolved"] += c
        elif st == "Rejected":
            stats["rejected"] += c

    # Search and filter parameters
    q = request.args.get("q", "").strip()
    category_filter = request.args.get("category", "All").strip()
    status_filter = request.args.get("status", "All").strip()
    department_filter = request.args.get("department", "All").strip()

    # Build parameterized query joining departments & field teams
    query = """
        SELECT reports.*,
               users.name as citizen_name, users.email as citizen_email,
               departments.id as department_id, departments.name as department_name, departments.code as department_code,
               field_teams.name as field_team_name
        FROM reports
        LEFT JOIN users ON reports.user_id = users.id
        LEFT JOIN report_assignments ON reports.id = report_assignments.report_id
        LEFT JOIN departments ON report_assignments.department_id = departments.id
        LEFT JOIN field_teams ON report_assignments.field_team_id = field_teams.id
        WHERE 1=1
    """
    params = []

    if category_filter and category_filter != "All":
        query += " AND reports.category = ?"
        params.append(category_filter)

    if status_filter and status_filter != "All":
        if status_filter == "Assigned":
            query += " AND reports.status IN ('Assigned', 'Accepted')"
        elif status_filter == "In Progress":
            query += " AND reports.status IN ('In Progress', 'Work Completed')"
        elif status_filter == "Resolved":
            query += " AND reports.status IN ('Resolved', 'Verified')"
        else:
            query += " AND reports.status = ?"
            params.append(status_filter)

    if department_filter and department_filter != "All":
        if department_filter.isdigit():
            query += " AND departments.id = ?"
            params.append(int(department_filter))
        else:
            query += " AND (departments.code = ? OR departments.name = ?)"
            params.extend([department_filter, department_filter])

    if q:
        # Check if search term represents a numeric report ID or CITY-YYYY-XXXXX format
        id_match = None
        if q.isdigit():
            id_match = int(q)
        elif q.upper().startswith("CITY-") and q.split("-")[-1].isdigit():
            try:
                id_match = int(q.split("-")[-1])
            except ValueError:
                id_match = None

        wildcard = f"%{q}%"
        if id_match is not None:
            query += """
                AND (
                    reports.id = ?
                    OR reports.title LIKE ?
                    OR reports.location LIKE ?
                    OR reports.category LIKE ?
                    OR reports.issue_type LIKE ?
                    OR reports.priority LIKE ?
                    OR users.name LIKE ?
                    OR users.email LIKE ?
                    OR departments.name LIKE ?
                )
            """
            params.extend([id_match, wildcard, wildcard, wildcard, wildcard, wildcard, wildcard, wildcard, wildcard])
        else:
            query += """
                AND (
                    reports.title LIKE ?
                    OR reports.location LIKE ?
                    OR reports.category LIKE ?
                    OR reports.issue_type LIKE ?
                    OR reports.priority LIKE ?
                    OR users.name LIKE ?
                    OR users.email LIKE ?
                    OR departments.name LIKE ?
                )
            """
            params.extend([wildcard, wildcard, wildcard, wildcard, wildcard, wildcard, wildcard, wildcard])

    query += " ORDER BY datetime(reports.created_at) DESC, reports.id DESC"
    reports = db.execute(query, params).fetchall()
    departments = database.get_departments(db)

    return render_template(
        "admin.html",
        stats=stats,
        reports=reports,
        categories=database.REPORT_CATEGORIES,
        statuses=database.REPORT_STATUSES,
        departments=departments,
        current_q=q,
        current_category=category_filter,
        current_status=status_filter,
        current_department=department_filter,
        user_name=session.get("name"),
    )


@app.route("/admin/report/<int:report_id>")
@admin_required
def admin_report_detail(report_id):
    """
    Admin detailed report view with citizen information,
    municipal operations panel (department/field team assignment,
    work progress log, resolution evidence, and quality verification).
    """
    db = database.get_db()

    report = db.execute(
        """
        SELECT reports.*, users.name as citizen_name, users.email as citizen_email
        FROM reports
        LEFT JOIN users ON reports.user_id = users.id
        WHERE reports.id = ?
        """,
        (report_id,),
    ).fetchone()

    if report is None:
        abort(404)

    formatted_id = database.format_report_id(report["id"], report["created_at"])

    # Calculate status tracker info
    current_status = report["status"]
    is_rejected = current_status == "Rejected"
    current_step_idx = TRACKER_STAGES.index(current_status) if current_status in TRACKER_STAGES else 0

    tracker_info = []
    for idx, stage in enumerate(TRACKER_STAGES):
        if is_rejected:
            state = "rejected"
        elif idx < current_step_idx:
            state = "completed"
        elif idx == current_step_idx:
            state = "active"
        else:
            state = "upcoming"
        tracker_info.append({"name": stage, "state": state, "step": idx + 1})

    keywords_raw = report["keywords"] if "keywords" in report.keys() and report["keywords"] else ""
    keywords_list = [k.strip() for k in keywords_raw.split(",") if k.strip()]
    issue_type = report["issue_type"] if "issue_type" in report.keys() and report["issue_type"] else "General Issue"
    priority = (report["priority"] if "priority" in report.keys() and report["priority"] else "MEDIUM").upper()

    # Municipal operations data
    departments = database.get_departments(db)
    field_teams = database.get_all_field_teams(db)
    assignment_details = database.get_report_assignment_details(db, report_id)
    report_updates = database.get_report_updates(db, report_id, public_only=False)
    resolution_evidence = database.get_resolution_evidence(db, report_id, verified_only=False)
    status_history = database.get_report_history(db, report_id)

    return render_template(
        "admin_report_detail.html",
        report=report,
        formatted_id=formatted_id,
        tracker_info=tracker_info,
        is_rejected=is_rejected,
        current_status=current_status,
        statuses=database.REPORT_STATUSES,
        departments=departments,
        field_teams=field_teams,
        assignment_details=assignment_details,
        report_updates=report_updates,
        resolution_evidence=resolution_evidence,
        status_history=status_history,
        user_name=session.get("name"),
        keywords_list=keywords_list,
        issue_type=issue_type,
        priority=priority,
    )


@app.route("/admin/report/<int:report_id>/status", methods=["POST"])
@admin_required
def update_report_status(report_id):
    """
    Admin action to update a report's lifecycle status.
    Updates reports.status and updated_at timestamp, records transition in
    report_history, and creates an in-app notification for the citizen owner.
    """
    db = database.get_db()

    # Check report existence
    report = db.execute("SELECT id, user_id, title, status, created_at FROM reports WHERE id = ?", (report_id,)).fetchone()
    if report is None:
        abort(404)

    new_status = request.form.get("status", "").strip()

    if new_status not in database.REPORT_STATUSES:
        flash("Invalid status selected.", "danger")
        return redirect(url_for("admin_report_detail", report_id=report_id))

    old_status = report["status"]
    now = datetime.now().isoformat()
    db.execute(
        "UPDATE reports SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, now, report_id),
    )
    db.commit()

    # Record in report_history if status changed
    if new_status != old_status:
        database.add_report_history(db, report_id, old_status, new_status, session.get("user_id"))

        # Formulate citizen notification
        formatted_id = database.format_report_id(report["id"], report["created_at"])
        if new_status == "Under Review":
            msg = f"Your report {formatted_id} ('{report['title']}') has been verified and is under review."
        elif new_status == "Assigned":
            msg = f"Your report {formatted_id} ('{report['title']}') has been assigned to municipal operations."
        elif new_status == "In Progress":
            msg = f"Work has started on your reported issue {formatted_id} ('{report['title']}')."
        elif new_status in ("Work Completed", "Verification Required"):
            msg = f"Work has been completed on report {formatted_id} and is awaiting municipal verification."
        elif new_status in ("Resolved", "Verified"):
            msg = f"Your report {formatted_id} ('{report['title']}') has been successfully resolved. Thank you for your civic contribution!"
        elif new_status == "Rejected":
            msg = f"Your report {formatted_id} ('{report['title']}') was reviewed and rejected by municipal authorities."
        else:
            msg = f"Your report {formatted_id} status has been updated to '{new_status}'."

        if report["user_id"]:
            database.create_notification(
                db,
                report["user_id"],
                report_id,
                f"Status Update: {new_status}",
                msg,
            )

    flash(f"Report status updated to '{new_status}' successfully.", "success")
    return redirect(url_for("admin_report_detail", report_id=report_id))


@app.route("/admin/report/<int:report_id>/assign", methods=["POST"])
@admin_required
def assign_report(report_id):
    """
    Assigns a report to a municipal department and optional field team.
    Updates report status to 'Assigned', records history, logs public progress update,
    and dispatches an in-app notification to the citizen owner.
    """
    db = database.get_db()
    report = db.execute("SELECT id, user_id, title, status, created_at FROM reports WHERE id = ?", (report_id,)).fetchone()
    if report is None:
        abort(404)

    dept_id_raw = request.form.get("department_id", "").strip()
    if not dept_id_raw or not dept_id_raw.isdigit():
        flash("Please select a valid municipal department.", "danger")
        return redirect(url_for("admin_report_detail", report_id=report_id))

    dept_id = int(dept_id_raw)
    dept = database.get_department_by_id(db, dept_id)
    if dept is None:
        flash("Selected department does not exist.", "danger")
        return redirect(url_for("admin_report_detail", report_id=report_id))

    field_team_id_raw = request.form.get("field_team_id", "").strip()
    field_team_id = int(field_team_id_raw) if field_team_id_raw.isdigit() else None
    field_team_name = None
    if field_team_id:
        team_row = db.execute("SELECT name FROM field_teams WHERE id = ?", (field_team_id,)).fetchone()
        if team_row:
            field_team_name = team_row["name"]

    notes = request.form.get("assignment_notes", "").strip()
    admin_user_id = session.get("user_id")

    # Record assignment in report_assignments table
    database.assign_report_department(
        db,
        report_id=report_id,
        department_id=dept_id,
        field_team_id=field_team_id,
        assigned_by_user_id=admin_user_id,
        notes=notes,
        status="Assigned",
    )

    # Transition report status to 'Assigned' if currently 'Reported' or 'Under Review'
    old_status = report["status"]
    new_status = "Assigned"
    now = datetime.now().isoformat()

    if old_status in ("Reported", "Under Review"):
        db.execute(
            "UPDATE reports SET status = ?, updated_at = ? WHERE id = ?",
            (new_status, now, report_id),
        )
        db.commit()
        database.add_report_history(db, report_id, old_status, new_status, admin_user_id)
    else:
        db.execute("UPDATE reports SET updated_at = ? WHERE id = ?", (now, report_id))
        db.commit()

    # Log public progress update for citizen transparency
    update_text = f"Report assigned to {dept['name']}"
    if field_team_name:
        update_text += f" (Field Team: {field_team_name})"
    if notes:
        update_text += f" — {notes}"
    database.add_report_update(db, report_id, admin_user_id, update_text, operational_status=new_status, is_public=1)

    # Dispatch citizen notification
    formatted_id = database.format_report_id(report["id"], report["created_at"])
    if report["user_id"]:
        database.create_notification(
            db,
            report["user_id"],
            report_id,
            f"Department Assigned: {dept['name']}",
            f"Your report {formatted_id} ('{report['title']}') has been assigned to the {dept['name']} department.",
        )

    flash(f"Report successfully assigned to {dept['name']}.", "success")
    return redirect(url_for("admin_report_detail", report_id=report_id))


@app.route("/admin/report/<int:report_id>/update", methods=["POST"])
@admin_required
def add_progress_update(report_id):
    """
    Adds an operational work progress update note to a report.
    Supports toggling public visibility and advancing operational status.
    """
    db = database.get_db()
    report = db.execute("SELECT id, user_id, title, status, created_at FROM reports WHERE id = ?", (report_id,)).fetchone()
    if report is None:
        abort(404)

    update_text = request.form.get("update_text", "").strip()
    if not update_text:
        flash("Progress update message cannot be empty.", "danger")
        return redirect(url_for("admin_report_detail", report_id=report_id))

    is_public = 1 if request.form.get("is_public") in ("1", "true", "on", "yes") else 0
    operational_status = request.form.get("operational_status", "").strip() or report["status"]
    admin_user_id = session.get("user_id")
    now = datetime.now().isoformat()

    # If status is being transitioned via this update
    old_status = report["status"]
    if operational_status in database.REPORT_STATUSES and operational_status != old_status:
        db.execute(
            "UPDATE reports SET status = ?, updated_at = ? WHERE id = ?",
            (operational_status, now, report_id),
        )
        db.commit()
        database.add_report_history(db, report_id, old_status, operational_status, admin_user_id)

        # Trigger notification on status transition
        formatted_id = database.format_report_id(report["id"], report["created_at"])
        if operational_status == "In Progress":
            msg = f"Work has started on your reported issue {formatted_id} ('{report['title']}')."
        elif operational_status in ("Work Completed", "Verification Required"):
            msg = f"Work has been completed and is awaiting municipal verification for {formatted_id}."
        elif operational_status in ("Resolved", "Verified"):
            msg = f"Your reported issue {formatted_id} ('{report['title']}') has been successfully resolved."
        else:
            msg = f"Your report {formatted_id} status updated to '{operational_status}'."

        if report["user_id"]:
            database.create_notification(
                db,
                report["user_id"],
                report_id,
                f"Status Update: {operational_status}",
                msg,
            )
    else:
        db.execute("UPDATE reports SET updated_at = ? WHERE id = ?", (now, report_id))
        db.commit()

    database.add_report_update(
        db,
        report_id=report_id,
        user_id=admin_user_id,
        update_text=update_text,
        operational_status=operational_status,
        is_public=is_public,
    )

    flash("Progress update logged successfully.", "success")
    return redirect(url_for("admin_report_detail", report_id=report_id))


@app.route("/admin/report/<int:report_id>/evidence", methods=["POST"])
@admin_required
def upload_evidence(report_id):
    """
    Uploads photographic resolution evidence for a report.
    Validates file extension, size, and sanitizes filename.
    Transitions report to 'Verification Required' / 'Work Completed'.
    """
    db = database.get_db()
    report = db.execute("SELECT id, user_id, title, status, created_at FROM reports WHERE id = ?", (report_id,)).fetchone()
    if report is None:
        abort(404)

    if "evidence_image" not in request.files:
        flash("No evidence photo provided.", "danger")
        return redirect(url_for("admin_report_detail", report_id=report_id))

    file = request.files["evidence_image"]
    if file.filename == "":
        flash("No file selected for evidence upload.", "danger")
        return redirect(url_for("admin_report_detail", report_id=report_id))

    if not allowed_file(file.filename):
        flash("Invalid image file type. Allowed formats: PNG, JPG, JPEG.", "danger")
        return redirect(url_for("admin_report_detail", report_id=report_id))

    orig_filename = secure_filename(file.filename)
    unique_filename = f"resolution_{uuid.uuid4().hex[:12]}_{orig_filename}"
    file.save(os.path.join(app.config["UPLOAD_FOLDER"], unique_filename))
    image_path = f"/uploads/{unique_filename}"

    caption = request.form.get("caption", "").strip() or "Field remediation photo evidence"
    admin_user_id = session.get("user_id")
    now = datetime.now().isoformat()

    # Save resolution evidence record
    database.add_resolution_evidence(
        db,
        report_id=report_id,
        user_id=admin_user_id,
        image_path=image_path,
        caption=caption,
    )

    # Transition report status to 'Verification Required'
    old_status = report["status"]
    new_status = "Verification Required"
    db.execute(
        "UPDATE reports SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, now, report_id),
    )
    db.commit()

    if old_status != new_status:
        database.add_report_history(db, report_id, old_status, new_status, admin_user_id)

    # Log public update
    database.add_report_update(
        db,
        report_id=report_id,
        user_id=admin_user_id,
        update_text=f"Resolution evidence attached: {caption}. Awaiting municipal verification.",
        operational_status=new_status,
        is_public=1,
    )

    # Dispatch citizen notification
    formatted_id = database.format_report_id(report["id"], report["created_at"])
    if report["user_id"]:
        database.create_notification(
            db,
            report["user_id"],
            report_id,
            "Work Completed — Awaiting Verification",
            f"Work has been completed on report {formatted_id} and is awaiting municipal verification.",
        )

    flash("Resolution evidence photo uploaded successfully.", "success")
    return redirect(url_for("admin_report_detail", report_id=report_id))


@app.route("/admin/report/<int:report_id>/verify", methods=["POST"])
@admin_required
def verify_and_resolve(report_id):
    """
    Admin verification step: Verifies resolution evidence and permanently marks
    the report as 'Resolved', recording history and notifying the citizen.
    """
    db = database.get_db()
    report = db.execute("SELECT id, user_id, title, status, created_at FROM reports WHERE id = ?", (report_id,)).fetchone()
    if report is None:
        abort(404)

    admin_user_id = session.get("user_id")
    now = datetime.now().isoformat()

    # Mark evidence records as verified
    evidence_id_raw = request.form.get("evidence_id", "").strip()
    if evidence_id_raw.isdigit():
        database.verify_resolution_evidence(db, int(evidence_id_raw), admin_user_id)
    else:
        # Verify all pending evidence for this report
        db.execute(
            "UPDATE resolution_evidence SET verified = 1, verified_by_user_id = ?, verified_at = ? WHERE report_id = ?",
            (admin_user_id, now, report_id),
        )
        db.commit()

    # Update report status to Resolved
    old_status = report["status"]
    new_status = "Resolved"
    db.execute(
        "UPDATE reports SET status = ?, updated_at = ? WHERE id = ?",
        (new_status, now, report_id),
    )
    db.commit()

    if old_status != new_status:
        database.add_report_history(db, report_id, old_status, new_status, admin_user_id)

    # Log public progress update
    database.add_report_update(
        db,
        report_id=report_id,
        user_id=admin_user_id,
        update_text="Resolution verified by municipal administration. Problem confirmed resolved.",
        operational_status=new_status,
        is_public=1,
    )

    # Dispatch citizen notification
    formatted_id = database.format_report_id(report["id"], report["created_at"])
    if report["user_id"]:
        database.create_notification(
            db,
            report["user_id"],
            report_id,
            "Issue Resolved",
            f"Your reported issue {formatted_id} ('{report['title']}') has been successfully resolved.",
        )

    flash("Report resolution verified and closed successfully.", "success")
    return redirect(url_for("admin_report_detail", report_id=report_id))


@app.route("/api/departments/<int:dept_id>/teams")
@admin_required
def api_department_teams(dept_id):
    """JSON API endpoint returning field teams for a specific department."""
    db = database.get_db()
    teams = database.get_field_teams_by_department(db, dept_id)
    return jsonify(teams)


@app.route("/admin/map")
@admin_required
def admin_city_map():
    """
    CityOS Administration Interactive City Map.
    Renders an interactive geospatial map plotting geo-tagged citizen incident reports.
    """
    return render_template(
        "admin_map.html",
        categories=database.REPORT_CATEGORIES,
        smart_categories=database.SMART_CATEGORIES,
        statuses=database.REPORT_STATUSES,
        priorities=["HIGH", "MEDIUM", "LOW"],
        user_name=session.get("name"),
    )


@app.route("/api/reports/map")
@login_required
def api_reports_map():
    """
    JSON API endpoint providing geo-referenced complaint reports.
    Supports filtering by category, priority, and status.
    Omits citizen personal information for privacy.
    """
    category_filter = request.args.get("category", "All").strip()
    priority_filter = request.args.get("priority", "All").strip()
    status_filter = request.args.get("status", "All").strip()

    db = database.get_db()
    query = """
        SELECT id, category, title, description, location, location_description,
               latitude, longitude, status, issue_type, priority, created_at
        FROM reports
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """
    params = []

    if category_filter and category_filter != "All":
        query += " AND category = ?"
        params.append(category_filter)

    if priority_filter and priority_filter != "All":
        query += " AND UPPER(priority) = ?"
        params.append(priority_filter.upper())

    if status_filter and status_filter != "All":
        # Support "Submitted" matching "Reported"
        if status_filter == "Submitted":
            query += " AND status = 'Reported'"
        else:
            query += " AND status = ?"
            params.append(status_filter)

    query += " ORDER BY datetime(created_at) DESC"
    rows = db.execute(query, params).fetchall()

    features = []
    for r in rows:
        prio = (r["priority"] or "MEDIUM").upper()
        desc = r["description"] or ""
        short_desc = (desc[:100] + "...") if len(desc) > 100 else desc
        features.append({
            "id": r["id"],
            "formatted_id": database.format_report_id(r["id"], r["created_at"]),
            "category": r["category"],
            "issue_type": r["issue_type"] or "General Issue",
            "priority": prio,
            "status": r["status"],
            "title": r["title"],
            "description": short_desc,
            "location": r["location"],
            "location_description": r["location_description"] or "",
            "latitude": float(r["latitude"]),
            "longitude": float(r["longitude"]),
            "created_at": r["created_at"][:10],
            "report_url": url_for("admin_report_detail", report_id=r["id"]),
        })

    return jsonify(features)


@app.route("/admin/intelligence")
@admin_required
def admin_intelligence():
    """
    CityOS Administration Intelligence & Analytics Dashboard.
    Provides city-wide KPIs, category/priority/status analytics, spatial problem hotspots,
    resolution turnaround metrics, and deterministic smart city insights.
    """
    db = database.get_db()

    # Optional URL query filters (category, priority, status, days)
    cat_filter = request.args.get("category", "All").strip()
    prio_filter = request.args.get("priority", "All").strip()
    status_filter = request.args.get("status", "All").strip()
    days_filter = request.args.get("days", "All").strip()

    filters = {
        "category": cat_filter,
        "priority": prio_filter,
        "status": status_filter,
        "days": days_filter,
    }

    stats = city_analytics.compute_city_statistics(db, filters)
    cat_analytics = city_analytics.compute_category_analytics(db, filters)
    prio_analytics = city_analytics.compute_priority_analytics(db, filters)
    status_analytics = city_analytics.compute_status_analytics(db, filters)
    hotspots = city_analytics.detect_problem_hotspots(db, filters)
    top_areas = city_analytics.get_top_problem_areas(db, limit=5)
    res_analytics = city_analytics.compute_resolution_analytics(db)
    insights = city_analytics.generate_smart_insights(db, stats, hotspots, cat_analytics)

    return render_template(
        "admin_intelligence.html",
        stats=stats,
        cat_analytics=cat_analytics,
        prio_analytics=prio_analytics,
        status_analytics=status_analytics,
        hotspots=hotspots,
        top_areas=top_areas,
        res_analytics=res_analytics,
        insights=insights,
        categories=database.REPORT_CATEGORIES,
        smart_categories=database.SMART_CATEGORIES,
        statuses=database.REPORT_STATUSES,
        priorities=["HIGH", "MEDIUM", "LOW"],
        current_filters=filters,
        user_name=session.get("name"),
    )


@app.route("/api/reports/analytics")
@login_required
def api_reports_analytics():
    """
    JSON API endpoint providing computed city statistics, category/priority/status
    breakdowns, hotspots, resolution times, and smart insights.
    Supports filtering by category, priority, status, days.
    """
    cat_filter = request.args.get("category", "All").strip()
    prio_filter = request.args.get("priority", "All").strip()
    status_filter = request.args.get("status", "All").strip()
    days_filter = request.args.get("days", "All").strip()

    filters = {
        "category": cat_filter,
        "priority": prio_filter,
        "status": status_filter,
        "days": days_filter,
    }

    db = database.get_db()
    stats = city_analytics.compute_city_statistics(db, filters)
    cat_analytics = city_analytics.compute_category_analytics(db, filters)
    prio_analytics = city_analytics.compute_priority_analytics(db, filters)
    status_analytics = city_analytics.compute_status_analytics(db, filters)
    hotspots = city_analytics.detect_problem_hotspots(db, filters)
    top_areas = city_analytics.get_top_problem_areas(db, limit=5)
    res_analytics = city_analytics.compute_resolution_analytics(db)
    insights = city_analytics.generate_smart_insights(db, stats, hotspots, cat_analytics)

    return jsonify({
        "stats": stats,
        "category_analytics": cat_analytics,
        "priority_analytics": prio_analytics,
        "status_analytics": status_analytics,
        "hotspots": hotspots,
        "top_areas": top_areas,
        "resolution_analytics": res_analytics,
        "insights": insights,
        "filters": filters,
    })


@app.route("/api/reports/heatmap")
@login_required
def api_reports_heatmap():
    """
    JSON API endpoint providing weighted coordinates for Leaflet heatmap layer.
    Returns: [[lat, lon, intensity], ...]
    """
    cat_filter = request.args.get("category", "All").strip()
    prio_filter = request.args.get("priority", "All").strip()
    status_filter = request.args.get("status", "All").strip()
    days_filter = request.args.get("days", "All").strip()

    filters = {
        "category": cat_filter,
        "priority": prio_filter,
        "status": status_filter,
        "days": days_filter,
    }

    db = database.get_db()
    points = city_analytics.get_heatmap_points(db, filters)
    return jsonify(points)


@app.route("/uploads/<filename>")
def uploaded_file(filename):
    """Securely serve uploaded report images."""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/api/health")
def health_check():
    """Basic health check and system status endpoint."""
    db_status = "connected"
    try:
        db = database.get_db()
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [
            row["name"]
            for row in cursor.fetchall()
            if not row["name"].startswith("sqlite_")
        ]
    except Exception as e:
        db_status = f"error: {str(e)}"
        tables = []

    return jsonify(
        {
            "status": "online",
            "system": "CityOS",
            "version": "0.1.0",
            "database": {
                "status": db_status,
                "tables": tables,
            },
            "timestamp": datetime.now().isoformat(),
            "message": "CityOS core service is operational.",
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("true", "1", "yes")
    logger.info(f"Starting CityOS Flask server on port {port} (debug={debug}, env={flask_env})...")
    app.run(host="127.0.0.1", port=port, debug=debug)
