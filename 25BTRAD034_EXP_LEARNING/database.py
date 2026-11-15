import os
import sqlite3
from datetime import datetime
import logging
from flask import g, current_app
from werkzeug.security import generate_password_hash

logger = logging.getLogger("cityos.database")

# Supported smart categories & legacy report categories
SMART_CATEGORIES = [
    "Road",
    "Water",
    "Waste",
    "Electricity",
    "Traffic",
    "Public Safety",
    "Other",
]

REPORT_CATEGORIES = [
    "Road",
    "Water",
    "Waste",
    "Electricity",
    "Traffic",
    "Public Safety",
    "Pothole",
    "Garbage",
    "Streetlight",
    "Water Leakage",
    "Road Damage",
    "Drainage",
    "Traffic Problem",
    "Other",
]

# Extended municipal operational statuses
REPORT_STATUSES = [
    "Reported",
    "Under Review",
    "Assigned",
    "Accepted",
    "In Progress",
    "Work Completed",
    "Verification Required",
    "Verified",
    "Resolved",
    "Rejected",
]

# Standard Municipal Departments
MUNICIPAL_DEPARTMENTS = [
    {
        "name": "Roads & Infrastructure",
        "code": "ROADS",
        "description": "Maintenance and repair of roads, bridges, pavements, potholes, and public civil infrastructure.",
    },
    {
        "name": "Water Supply",
        "code": "WATER",
        "description": "Potable water distribution, pipeline leak repairs, drainage, and pressure management.",
    },
    {
        "name": "Sanitation",
        "code": "SANITATION",
        "description": "Public cleanliness, sewer line management, drainage clearance, and street sweeping.",
    },
    {
        "name": "Street Lighting",
        "code": "LIGHTING",
        "description": "Installation, repair, and maintenance of municipal streetlights and dark road illumination.",
    },
    {
        "name": "Traffic",
        "code": "TRAFFIC",
        "description": "Traffic flow management, road signage, bottleneck remediation, and traffic signal repair.",
    },
    {
        "name": "Parks & Public Spaces",
        "code": "PARKS",
        "description": "Upkeep of municipal parks, public gardens, fallen trees, and civic recreational spaces.",
    },
    {
        "name": "Waste Management",
        "code": "WASTE",
        "description": "Garbage collection, waste dumping remediation, bin management, and recycling operations.",
    },
    {
        "name": "Electrical",
        "code": "ELECTRICAL",
        "description": "Power grid safety, exposed wire hazard resolution, and civic electrical infrastructure.",
    },
    {
        "name": "Other",
        "code": "OTHER",
        "description": "General civic issues and unclassified municipal operations.",
    },
]

# Default Field Teams Seed Data
DEFAULT_FIELD_TEAMS = [
    {"dept_code": "ROADS", "name": "Roads Rapid Repair Team Alpha", "leader_name": "Rajesh Kumar", "contact_number": "+91 98765 43210"},
    {"dept_code": "ROADS", "name": "Asphalt & Pavement Crew 1", "leader_name": "Amit Sharma", "contact_number": "+91 98765 43211"},
    {"dept_code": "WATER", "name": "Pipeline Leakage Squad 1", "leader_name": "Suresh Patil", "contact_number": "+91 98765 43212"},
    {"dept_code": "WATER", "name": "Drainage Operations Unit", "leader_name": "Deepak Rao", "contact_number": "+91 98765 43213"},
    {"dept_code": "SANITATION", "name": "Sanitation Response Unit North", "leader_name": "Manoj Verma", "contact_number": "+91 98765 43214"},
    {"dept_code": "LIGHTING", "name": "Streetlight Electrical Crew A", "leader_name": "Anil Sharma", "contact_number": "+91 98765 43215"},
    {"dept_code": "TRAFFIC", "name": "Traffic Sign & Signal Squad", "leader_name": "Vikram Singh", "contact_number": "+91 98765 43216"},
    {"dept_code": "PARKS", "name": "Parks Maintenance Unit", "leader_name": "Pooja Reddy", "contact_number": "+91 98765 43217"},
    {"dept_code": "WASTE", "name": "Waste Clearance Taskforce 1", "leader_name": "Sunil Das", "contact_number": "+91 98765 43218"},
    {"dept_code": "ELECTRICAL", "name": "Civic Electrical Safety Squad", "leader_name": "Karthik Nair", "contact_number": "+91 98765 43219"},
    {"dept_code": "OTHER", "name": "General Municipal Response Team", "leader_name": "Ramesh Joshi", "contact_number": "+91 98765 43220"},
]


def format_report_id(db_id, created_at_str=None):
    """
    Formats a database integer ID into a human-readable unique CityOS report ID.
    Format: CITY-YYYY-00001
    """
    year = datetime.now().year
    if created_at_str:
        try:
            year = str(created_at_str)[:4]
        except Exception:
            year = datetime.now().year
    return f"CITY-{year}-{int(db_id):05d}"


def get_db():
    """
    Opens a new database connection if there is none yet for the
    current application context, and configures row access by column name.
    Includes timeout=30.0 for robust multi-threaded/WSGI concurrency.
    """
    if "db" not in g:
        db_path = current_app.config.get("DATABASE")
        g.db = sqlite3.connect(db_path, timeout=30.0)
        # Enable access to columns by name like a dictionary (e.g. row['email'])
        g.db.row_factory = sqlite3.Row
        # Enable foreign key support in SQLite
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db


def close_db(e=None):
    """Closes the database connection at the end of the request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """
    Initializes the database schema and creates default tables & admin account.
    """
    db = get_db()

    # Create users table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'citizen',
            created_at TEXT NOT NULL
        );
        """
    )

    # Create reports table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            location TEXT NOT NULL,
            image TEXT,
            status TEXT NOT NULL DEFAULT 'Reported',
            issue_type TEXT DEFAULT 'General Issue',
            priority TEXT DEFAULT 'MEDIUM',
            keywords TEXT DEFAULT '',
            latitude REAL,
            longitude REAL,
            location_description TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        );
        """
    )

    # Create report_history table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS report_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            previous_status TEXT,
            new_status TEXT NOT NULL,
            changed_by_user_id INTEGER,
            created_at TEXT NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE,
            FOREIGN KEY (changed_by_user_id) REFERENCES users (id) ON DELETE SET NULL
        );
        """
    )

    # Create notifications table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            report_id INTEGER,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE SET NULL
        );
        """
    )

    # Phase 3: Create departments table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            code TEXT UNIQUE NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL
        );
        """
    )

    # Phase 3: Create field_teams table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS field_teams (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            department_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            leader_name TEXT NOT NULL,
            contact_number TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE CASCADE
        );
        """
    )

    # Phase 3: Create report_assignments table
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS report_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            department_id INTEGER NOT NULL,
            field_team_id INTEGER,
            assigned_by_user_id INTEGER,
            assignment_notes TEXT,
            status TEXT NOT NULL DEFAULT 'Assigned',
            assigned_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE,
            FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE CASCADE,
            FOREIGN KEY (field_team_id) REFERENCES field_teams (id) ON DELETE SET NULL,
            FOREIGN KEY (assigned_by_user_id) REFERENCES users (id) ON DELETE SET NULL
        );
        """
    )

    # Phase 3: Create report_updates table (Work Progress Updates)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS report_updates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            update_text TEXT NOT NULL,
            operational_status TEXT NOT NULL,
            is_public INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
        );
        """
    )

    # Phase 3: Create resolution_evidence table (Resolution Evidence & Verification)
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS resolution_evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id INTEGER NOT NULL,
            uploaded_by_user_id INTEGER NOT NULL,
            image_path TEXT NOT NULL,
            caption TEXT,
            verified INTEGER NOT NULL DEFAULT 0,
            verified_by_user_id INTEGER,
            verified_at TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (report_id) REFERENCES reports (id) ON DELETE CASCADE,
            FOREIGN KEY (uploaded_by_user_id) REFERENCES users (id) ON DELETE SET NULL,
            FOREIGN KEY (verified_by_user_id) REFERENCES users (id) ON DELETE SET NULL
        );
        """
    )

    # Create performance indexes on high-frequency query and foreign key columns
    db.execute("CREATE INDEX IF NOT EXISTS idx_reports_user_id ON reports (user_id);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_reports_status ON reports (status);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_reports_category ON reports (category);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications (user_id, is_read);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_report_history_report ON report_history (report_id);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_field_teams_dept ON field_teams (department_id);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_report_assignments_report ON report_assignments (report_id);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_report_assignments_dept ON report_assignments (department_id);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_report_updates_report ON report_updates (report_id);")
    db.execute("CREATE INDEX IF NOT EXISTS idx_resolution_evidence_report ON resolution_evidence (report_id);")

    # Non-destructive column migration for existing database instances
    cursor = db.execute("PRAGMA table_info(reports);")
    cols = [row["name"] for row in cursor.fetchall()]
    if cols:
        if "issue_type" not in cols:
            db.execute("ALTER TABLE reports ADD COLUMN issue_type TEXT DEFAULT 'General Issue';")
        if "priority" not in cols:
            db.execute("ALTER TABLE reports ADD COLUMN priority TEXT DEFAULT 'MEDIUM';")
        if "keywords" not in cols:
            db.execute("ALTER TABLE reports ADD COLUMN keywords TEXT DEFAULT '';")
        if "latitude" not in cols:
            db.execute("ALTER TABLE reports ADD COLUMN latitude REAL;")
        if "longitude" not in cols:
            db.execute("ALTER TABLE reports ADD COLUMN longitude REAL;")
        if "location_description" not in cols:
            db.execute("ALTER TABLE reports ADD COLUMN location_description TEXT;")
        db.commit()

    # Seed initial Admin user if not present (environment-configurable)
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@cityos.com").strip().lower()
    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")

    cursor = db.execute("SELECT id FROM users WHERE LOWER(email) = ?", (admin_email,))
    admin_user = cursor.fetchone()

    now = datetime.now().isoformat()

    if admin_user is None:
        hashed_password = generate_password_hash(admin_password)
        db.execute(
            """
            INSERT INTO users (name, email, password, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("System Admin", admin_email, hashed_password, "admin", now),
        )
        db.commit()
        logger.info(f"Initial administrator account seeded: {admin_email}")

    # Seed Municipal Departments
    for dept in MUNICIPAL_DEPARTMENTS:
        row = db.execute("SELECT id FROM departments WHERE code = ?", (dept["code"],)).fetchone()
        if row is None:
            db.execute(
                """
                INSERT INTO departments (name, code, description, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (dept["name"], dept["code"], dept["description"], now),
            )
    db.commit()

    # Seed Default Field Teams
    for team in DEFAULT_FIELD_TEAMS:
        dept_row = db.execute("SELECT id FROM departments WHERE code = ?", (team["dept_code"],)).fetchone()
        if dept_row:
            dept_id = dept_row["id"]
            existing_team = db.execute(
                "SELECT id FROM field_teams WHERE department_id = ? AND name = ?",
                (dept_id, team["name"]),
            ).fetchone()
            if existing_team is None:
                db.execute(
                    """
                    INSERT INTO field_teams (department_id, name, leader_name, contact_number, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (dept_id, team["name"], team["leader_name"], team["contact_number"], now),
                )
    db.commit()


# ==============================================================================
# Helper Methods: Report History & Notifications
# ==============================================================================

def add_report_history(db, report_id, previous_status, new_status, changed_by_user_id=None):
    """Records a status transition in the report_history audit trail."""
    now = datetime.now().isoformat()
    db.execute(
        """
        INSERT INTO report_history (report_id, previous_status, new_status, changed_by_user_id, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (report_id, previous_status, new_status, changed_by_user_id, now),
    )
    db.commit()


def get_report_history(db, report_id):
    """Retrieves chronological history records for a specific report."""
    rows = db.execute(
        """
        SELECT id, report_id, previous_status, new_status, changed_by_user_id, created_at
        FROM report_history
        WHERE report_id = ?
        ORDER BY datetime(created_at) ASC, id ASC
        """,
        (report_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def create_notification(db, user_id, report_id, title, message):
    """Creates a new in-app notification for a user."""
    if not user_id:
        return None
    now = datetime.now().isoformat()
    cursor = db.execute(
        """
        INSERT INTO notifications (user_id, report_id, title, message, is_read, created_at)
        VALUES (?, ?, ?, ?, 0, ?)
        """,
        (user_id, report_id, title, message, now),
    )
    db.commit()
    return cursor.lastrowid


def get_user_notifications(db, user_id, limit=50):
    """Retrieves all notifications for a specific user, newest first."""
    rows = db.execute(
        """
        SELECT id, user_id, report_id, title, message, is_read, created_at
        FROM notifications
        WHERE user_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def get_unread_notification_count(db, user_id):
    """Returns the total number of unread notifications for a user."""
    if not user_id:
        return 0
    row = db.execute(
        "SELECT COUNT(*) as count FROM notifications WHERE user_id = ? AND is_read = 0",
        (user_id,),
    ).fetchone()
    return row["count"] if row else 0


def mark_notification_as_read(db, notification_id, user_id):
    """Marks an individual notification as read, ensuring ownership."""
    db.execute(
        "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
        (notification_id, user_id),
    )
    db.commit()


def mark_all_notifications_as_read(db, user_id):
    """Marks all notifications for a user as read."""
    db.execute(
        "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
        (user_id,),
    )
    db.commit()


# ==============================================================================
# Helper Methods: Phase 3 Municipal Operations
# ==============================================================================

def get_departments(db):
    """Returns all municipal departments ordered by name."""
    rows = db.execute("SELECT * FROM departments ORDER BY name ASC").fetchall()
    return [dict(r) for r in rows]


def get_department_by_id(db, dept_id):
    """Fetches a department by its primary key ID."""
    row = db.execute("SELECT * FROM departments WHERE id = ?", (dept_id,)).fetchone()
    return dict(row) if row else None


def get_department_by_code(db, code):
    """Fetches a department by its unique uppercase code."""
    row = db.execute("SELECT * FROM departments WHERE UPPER(code) = UPPER(?)", (code,)).fetchone()
    return dict(row) if row else None


def get_field_teams_by_department(db, department_id):
    """Returns all field teams assigned to a specific department."""
    rows = db.execute(
        "SELECT * FROM field_teams WHERE department_id = ? ORDER BY name ASC",
        (department_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_field_teams(db):
    """Returns all field teams with department details joined."""
    rows = db.execute(
        """
        SELECT field_teams.*, departments.name as department_name, departments.code as department_code
        FROM field_teams
        JOIN departments ON field_teams.department_id = departments.id
        ORDER BY departments.name ASC, field_teams.name ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def assign_report_department(db, report_id, department_id, field_team_id=None, assigned_by_user_id=None, notes=None, status="Assigned"):
    """
    Assigns or re-assigns a report to a municipal department and optional field team.
    Updates or inserts the latest assignment record.
    """
    now = datetime.now().isoformat()

    # Check if existing assignment exists
    existing = db.execute(
        "SELECT id FROM report_assignments WHERE report_id = ?",
        (report_id,),
    ).fetchone()

    if existing:
        db.execute(
            """
            UPDATE report_assignments
            SET department_id = ?, field_team_id = ?, assigned_by_user_id = ?,
                assignment_notes = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (department_id, field_team_id, assigned_by_user_id, notes, status, now, existing["id"]),
        )
        assignment_id = existing["id"]
    else:
        cursor = db.execute(
            """
            INSERT INTO report_assignments (
                report_id, department_id, field_team_id, assigned_by_user_id,
                assignment_notes, status, assigned_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (report_id, department_id, field_team_id, assigned_by_user_id, notes, status, now, now),
        )
        assignment_id = cursor.lastrowid

    db.commit()
    return assignment_id


def get_report_assignment_details(db, report_id):
    """
    Retrieves complete assignment details for a report, including department name,
    code, team name, and leader information.
    """
    row = db.execute(
        """
        SELECT ra.*,
               d.name as department_name, d.code as department_code, d.description as department_desc,
               ft.name as field_team_name, ft.leader_name as team_leader_name, ft.contact_number as team_contact,
               u.name as assigned_by_name, u.email as assigned_by_email
        FROM report_assignments ra
        JOIN departments d ON ra.department_id = d.id
        LEFT JOIN field_teams ft ON ra.field_team_id = ft.id
        LEFT JOIN users u ON ra.assigned_by_user_id = u.id
        WHERE ra.report_id = ?
        ORDER BY ra.id DESC
        LIMIT 1
        """,
        (report_id,),
    ).fetchone()
    return dict(row) if row else None


def add_report_update(db, report_id, user_id, update_text, operational_status=None, is_public=1):
    """Records an operational work progress update for a report."""
    now = datetime.now().isoformat()
    if not operational_status:
        rep = db.execute("SELECT status FROM reports WHERE id = ?", (report_id,)).fetchone()
        operational_status = rep["status"] if rep else "In Progress"

    cursor = db.execute(
        """
        INSERT INTO report_updates (report_id, user_id, update_text, operational_status, is_public, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (report_id, user_id, update_text, operational_status, int(is_public), now),
    )
    db.commit()
    return cursor.lastrowid


def get_report_updates(db, report_id, public_only=False):
    """
    Retrieves chronological progress updates for a report.
    If public_only is True, filters to is_public = 1.
    """
    if public_only:
        rows = db.execute(
            """
            SELECT ru.id, ru.report_id, ru.user_id, ru.update_text, ru.operational_status, ru.is_public, ru.created_at,
                   u.name as author_name
            FROM report_updates ru
            LEFT JOIN users u ON ru.user_id = u.id
            WHERE ru.report_id = ? AND ru.is_public = 1
            ORDER BY datetime(ru.created_at) ASC, ru.id ASC
            """,
            (report_id,),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT ru.id, ru.report_id, ru.user_id, ru.update_text, ru.operational_status, ru.is_public, ru.created_at,
                   u.name as author_name, u.role as author_role
            FROM report_updates ru
            LEFT JOIN users u ON ru.user_id = u.id
            WHERE ru.report_id = ?
            ORDER BY datetime(ru.created_at) ASC, ru.id ASC
            """,
            (report_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def add_resolution_evidence(db, report_id, user_id, image_path, caption=None):
    """Inserts a new resolution evidence photo entry."""
    now = datetime.now().isoformat()
    cursor = db.execute(
        """
        INSERT INTO resolution_evidence (
            report_id, uploaded_by_user_id, image_path, caption, verified, created_at
        ) VALUES (?, ?, ?, ?, 0, ?)
        """,
        (report_id, user_id, image_path, caption, now),
    )
    db.commit()
    return cursor.lastrowid


def get_resolution_evidence(db, report_id, verified_only=False):
    """Retrieves resolution evidence entries for a specific report."""
    if verified_only:
        rows = db.execute(
            """
            SELECT re.*,
                   u_up.name as uploader_name,
                   u_ver.name as verifier_name
            FROM resolution_evidence re
            LEFT JOIN users u_up ON re.uploaded_by_user_id = u_up.id
            LEFT JOIN users u_ver ON re.verified_by_user_id = u_ver.id
            WHERE re.report_id = ? AND re.verified = 1
            ORDER BY datetime(re.created_at) ASC, re.id ASC
            """,
            (report_id,),
        ).fetchall()
    else:
        rows = db.execute(
            """
            SELECT re.*,
                   u_up.name as uploader_name,
                   u_ver.name as verifier_name
            FROM resolution_evidence re
            LEFT JOIN users u_up ON re.uploaded_by_user_id = u_up.id
            LEFT JOIN users u_ver ON re.verified_by_user_id = u_ver.id
            WHERE re.report_id = ?
            ORDER BY datetime(re.created_at) ASC, re.id ASC
            """,
            (report_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def verify_resolution_evidence(db, evidence_id, admin_user_id):
    """Marks a resolution evidence record as verified by an authorized administrator."""
    now = datetime.now().isoformat()
    db.execute(
        """
        UPDATE resolution_evidence
        SET verified = 1, verified_by_user_id = ?, verified_at = ?
        WHERE id = ?
        """,
        (admin_user_id, now, evidence_id),
    )
    db.commit()


def get_operational_statistics(db, department_id=None):
    """
    Computes comprehensive municipal operational metrics:
    Total, Awaiting Review, Awaiting Assignment, Assigned, Active Field Work,
    Verification Pending, Resolved, and Rejected.
    Supports department-level filtering.
    """
    stats = {
        "total": 0,
        "awaiting_review": 0,       # Reported
        "awaiting_assignment": 0,   # Under Review
        "assigned": 0,              # Assigned, Accepted
        "in_progress": 0,           # In Progress, Work Completed
        "verification_pending": 0,  # Verification Required
        "resolved": 0,              # Resolved, Verified
        "rejected": 0,              # Rejected
    }

    if department_id:
        # Filter reports assigned to this department
        query = """
            SELECT reports.status, COUNT(*) as count
            FROM reports
            JOIN report_assignments ON reports.id = report_assignments.report_id
            WHERE report_assignments.department_id = ?
            GROUP BY reports.status
        """
        rows = db.execute(query, (department_id,)).fetchall()
        total_row = db.execute(
            """
            SELECT COUNT(*) as count
            FROM reports
            JOIN report_assignments ON reports.id = report_assignments.report_id
            WHERE report_assignments.department_id = ?
            """,
            (department_id,),
        ).fetchone()
        stats["total"] = total_row["count"] if total_row else 0
    else:
        rows = db.execute("SELECT status, COUNT(*) as count FROM reports GROUP BY status").fetchall()
        total_row = db.execute("SELECT COUNT(*) as count FROM reports").fetchone()
        stats["total"] = total_row["count"] if total_row else 0

    for r in rows:
        st = r["status"]
        c = r["count"]
        if st == "Reported":
            stats["awaiting_review"] += c
        elif st == "Under Review":
            stats["awaiting_assignment"] += c
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

    return stats


def init_app(app):
    """
    Registers database functions with the Flask app and initializes tables.
    """
    # Ensure instance directory exists for database file
    os.makedirs(app.instance_path, exist_ok=True)

    # Configure default database file path inside the instance folder if not specified
    if not app.config.get("DATABASE"):
        app.config["DATABASE"] = os.path.join(app.instance_path, "cityos.db")

    # Register teardown function to close DB connection after requests
    app.teardown_appcontext(close_db)

    # Automatically initialize tables and seed data on startup
    with app.app_context():
        init_db()
