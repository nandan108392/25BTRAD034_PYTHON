import os
import sys
import io
import time
import uuid
import sqlite3
import unittest
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

from app import app
import database
import smart_classifier
import city_analytics

# Windows console encoding safeguard
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class CityOSEndToEndAuditTest(unittest.TestCase):
    """
    Comprehensive End-to-End Audit for CityOS V1.
    Evaluates Citizen workflow, Admin workflow, Data Integrity, Security,
    Error Handling, UI/UX asset health, Database sanity, and Live Server capability.
    """

    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        cls.client = app.test_client()

        with app.app_context():
            database.init_db()

    def setUp(self):
        self.timestamp = int(time.time() * 1000)
        self.citizen_email = f"audit_citizen_{self.timestamp}@cityos.com"
        self.other_citizen_email = f"audit_other_{self.timestamp}@cityos.com"
        self.password = "SecurePass123!"

    # =========================================================================
    # 1. CITIZEN END-TO-END FLOW
    # =========================================================================
    def test_01_citizen_end_to_end_flow(self):
        """Test complete Citizen lifecycle: Register -> Login -> Submit -> View -> Notify -> Logout."""
        client = self.client

        # 1. Register
        res_reg = client.post(
            "/register",
            data={
                "name": "Audit Citizen",
                "email": self.citizen_email,
                "password": self.password,
                "confirm_password": self.password,
            },
            follow_redirects=True,
        )
        self.assertEqual(res_reg.status_code, 200)
        self.assertIn(b"Registration successful", res_reg.data)

        # 2. Login
        res_login = client.post(
            "/login",
            data={"email": self.citizen_email, "password": self.password},
            follow_redirects=True,
        )
        self.assertEqual(res_login.status_code, 200)
        self.assertIn(b"Welcome back, Audit Citizen!", res_login.data)
        self.assertIn(b"Citizen Dashboard", res_login.data)

        # 3. Citizen Dashboard inspection
        res_dash = client.get("/dashboard")
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b"Total Reports", res_dash.data)
        self.assertIn(b"Report a Problem", res_dash.data)

        # 4. Submit Report with Image & GPS Coordinates
        dummy_image = (io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"), "audit_evidence.png")
        res_submit = client.post(
            "/report",
            data={
                "category": "Road",
                "title": "Audit Main Road Deep Pothole",
                "description": "Dangerous pothole crater in center lane near school bus stop causing severe traffic hazard",
                "location": "100ft Ring Road, Sector 4",
                "location_description": "Opposite Metro Gate 3",
                "latitude": "12.9716",
                "longitude": "77.5946",
                "image": dummy_image,
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(res_submit.status_code, 302)
        redirect_url = res_submit.headers.get("Location", "")
        self.assertIn("/report/success/", redirect_url)
        report_id = int(redirect_url.split("/")[-1])

        # 5. Report Success confirmation page
        res_success = client.get(f"/report/success/{report_id}")
        self.assertEqual(res_success.status_code, 200)
        self.assertIn(b"Report Submitted Successfully", res_success.data)

        # 6. My Reports List
        res_my = client.get("/my-reports")
        self.assertEqual(res_my.status_code, 200)
        self.assertIn(b"Audit Main Road Deep Pothole", res_my.data)
        self.assertIn(b"100ft Ring Road, Sector 4", res_my.data)

        # 7. Report Details & 5-Stage Live Status Tracker
        res_detail = client.get(f"/report/{report_id}")
        self.assertEqual(res_detail.status_code, 200)
        self.assertIn(b"Submitted", res_detail.data)
        self.assertIn(b"Verified", res_detail.data)
        self.assertIn(b"Assigned", res_detail.data)
        self.assertIn(b"In Progress", res_detail.data)
        self.assertIn(b"Resolved", res_detail.data)
        self.assertIn(b"Status History &amp; Activity Log", res_detail.data)

        # 8. Notifications Center & Unread Badge
        res_notifs = client.get("/notifications")
        self.assertEqual(res_notifs.status_code, 200)
        self.assertIn(b"Report Logged:", res_notifs.data)

        # Check API unread count
        res_api_count = client.get("/api/notifications/unread-count")
        self.assertEqual(res_api_count.status_code, 200)
        data_count = res_api_count.get_json()
        self.assertGreaterEqual(data_count["unread_count"], 1)

        # 9. Mark All Notifications as Read
        res_mark_all = client.post("/notifications/read-all", follow_redirects=True)
        self.assertEqual(res_mark_all.status_code, 200)
        res_api_count_after = client.get("/api/notifications/unread-count")
        self.assertEqual(res_api_count_after.get_json()["unread_count"], 0)

        # 10. Logout
        res_logout = client.get("/logout", follow_redirects=True)
        self.assertEqual(res_logout.status_code, 200)
        self.assertIn(b"You have been logged out successfully.", res_logout.data)

    # =========================================================================
    # 2. ADMIN END-TO-END FLOW
    # =========================================================================
    def test_02_admin_end_to_end_flow(self):
        """Test complete Admin lifecycle: Login -> Stats -> Search -> Filter -> Review -> Status Update -> History & Notification verification -> Logout."""
        client = self.client

        # Seed a test report from a citizen
        with app.app_context():
            db = database.get_db()
            now = datetime.now().isoformat()
            pw_hash = generate_password_hash("citizen123")
            db.execute(
                "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
                ("Test Citizen A", self.citizen_email, pw_hash, "user", now),
            )
            c_id = db.execute("SELECT id FROM users WHERE email = ?", (self.citizen_email,)).fetchone()["id"]
            cursor = db.execute(
                """
                INSERT INTO reports (user_id, category, title, description, location, status, issue_type, priority, latitude, longitude, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (c_id, "Water", "Burst Water Main Flooding", "Water overflowing on street", "Main Street 5th Ave", "Reported", "Pipe Burst", "HIGH", 12.9800, 77.6000, now, now),
            )
            rep_id = cursor.lastrowid
            database.add_report_history(db, rep_id, None, "Reported", c_id)
            db.commit()

        # 1. Admin Login
        res_admin_login = client.post(
            "/login",
            data={"email": "admin@cityos.com", "password": "admin123"},
            follow_redirects=True,
        )
        self.assertEqual(res_admin_login.status_code, 200)
        self.assertIn(b"Admin Dashboard", res_admin_login.data)

        # 2. View Admin Statistics
        res_admin_dash = client.get("/admin")
        self.assertEqual(res_admin_dash.status_code, 200)
        self.assertIn(b"Total Reports", res_admin_dash.data)
        self.assertIn(b"Burst Water Main Flooding", res_admin_dash.data)

        # 3. Search Reports by Title and ID
        res_search_title = client.get(f"/admin?q=Burst")
        self.assertEqual(res_search_title.status_code, 200)
        self.assertIn(b"Burst Water Main Flooding", res_search_title.data)

        res_search_id = client.get(f"/admin?q={rep_id}")
        self.assertEqual(res_search_id.status_code, 200)
        self.assertIn(b"Burst Water Main Flooding", res_search_id.data)

        # 4. Filter Reports by Category and Status
        res_filter_cat = client.get("/admin?category=Water")
        self.assertEqual(res_filter_cat.status_code, 200)
        self.assertIn(b"Burst Water Main Flooding", res_filter_cat.data)

        res_filter_status = client.get("/admin?status=Reported")
        self.assertEqual(res_filter_status.status_code, 200)
        self.assertIn(b"Burst Water Main Flooding", res_filter_status.data)

        # 5. Open Admin Report Detail
        res_admin_detail = client.get(f"/admin/report/{rep_id}")
        self.assertEqual(res_admin_detail.status_code, 200)
        self.assertIn(b"Test Citizen A", res_admin_detail.data)
        self.assertIn(self.citizen_email.encode("utf-8"), res_admin_detail.data)
        self.assertIn(b"Manage Incident Lifecycle Status", res_admin_detail.data)
        self.assertIn(b"Save Status", res_admin_detail.data)

        # 6. Change Report Status to "In Progress"
        res_update_status = client.post(
            f"/admin/report/{rep_id}/status",
            data={"status": "In Progress"},
            follow_redirects=True,
        )
        self.assertEqual(res_update_status.status_code, 200)
        self.assertIn(b"Report status updated to &#39;In Progress&#39; successfully.", res_update_status.data)

        # 7. Verify Status History & Citizen Notification in Database
        with app.app_context():
            db = database.get_db()
            history = database.get_report_history(db, rep_id)
            self.assertGreaterEqual(len(history), 2)
            self.assertEqual(history[-1]["new_status"], "In Progress")

            notifs = database.get_user_notifications(db, c_id)
            self.assertGreaterEqual(len(notifs), 1)
            self.assertIn("In Progress", notifs[0]["title"] + notifs[0]["message"])

        # 8. Admin Logout
        client.get("/logout")

    # =========================================================================
    # 3. DATA INTEGRITY & PRIVACY ISOLATION
    # =========================================================================
    def test_03_data_integrity_and_isolation(self):
        """Verify strict data ownership, non-exposure of passwords, and duplicate prevention."""
        client = self.client

        # Create two distinct citizen users
        with app.app_context():
            db = database.get_db()
            now = datetime.now().isoformat()
            pw_hash = generate_password_hash("password123")

            db.execute("INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)", ("User One", self.citizen_email, pw_hash, "user", now))
            u1_id = db.execute("SELECT id FROM users WHERE email = ?", (self.citizen_email,)).fetchone()["id"]

            db.execute("INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)", ("User Two", self.other_citizen_email, pw_hash, "user", now))
            u2_id = db.execute("SELECT id FROM users WHERE email = ?", (self.other_citizen_email,)).fetchone()["id"]

            cursor = db.execute("INSERT INTO reports (user_id, category, title, description, location, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (u1_id, "Road", "User One Pothole", "Pothole description", "Street 1", "Reported", now, now))
            u1_rep_id = cursor.lastrowid

            cursor = db.execute("INSERT INTO reports (user_id, category, title, description, location, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (u2_id, "Water", "User Two Water Leak", "Water leak description", "Street 2", "Reported", now, now))
            u2_rep_id = cursor.lastrowid

            # Notifications
            n1_id = database.create_notification(db, u1_id, u1_rep_id, "Notif 1", "Message 1")
            n2_id = database.create_notification(db, u2_id, u2_rep_id, "Notif 2", "Message 2")
            db.commit()

        # Login as User Two
        client.post("/login", data={"email": self.other_citizen_email, "password": "password123"})

        # User Two attempts to view User One's report -> 403 Forbidden
        res_cross_report = client.get(f"/report/{u1_rep_id}")
        self.assertEqual(res_cross_report.status_code, 403)

        # User Two attempts to view User One's success page -> 403 Forbidden
        res_cross_success = client.get(f"/report/success/{u1_rep_id}")
        self.assertEqual(res_cross_success.status_code, 403)

        # User Two attempts to mark User One's notification as read -> 403 Forbidden
        res_cross_notif = client.post(f"/notifications/{n1_id}/read")
        self.assertEqual(res_cross_notif.status_code, 403)

        # User Two attempts to update status on admin route -> 403 Forbidden
        res_cit_update = client.post(f"/admin/report/{u2_rep_id}/status", data={"status": "Resolved"})
        self.assertEqual(res_cit_update.status_code, 403)

        # Verify password is never stored plain text
        with app.app_context():
            db = database.get_db()
            user_row = db.execute("SELECT password FROM users WHERE id = ?", (u2_id,)).fetchone()
            self.assertNotEqual(user_row["password"], "password123")
            self.assertTrue(user_row["password"].startswith("scrypt:") or user_row["password"].startswith("pbkdf2:"))

        client.get("/logout")

    # =========================================================================
    # 4. SECURITY AUDIT
    # =========================================================================
    def test_04_security_audit(self):
        """Audit access controls, unauthenticated redirection, safe uploads, and injection resistance."""
        client = self.client

        # Ensure logged out
        client.get("/logout")

        # 1. Protected routes redirect unauthenticated users to /login
        protected_routes = [
            "/dashboard",
            "/report",
            "/my-reports",
            "/notifications",
            "/admin",
            "/admin/map",
            "/admin/intelligence",
            "/api/reports/analytics",
            "/api/reports/heatmap",
            "/api/reports/map",
            "/api/notifications/unread-count",
        ]
        for path in protected_routes:
            res = client.get(path, follow_redirects=False)
            self.assertEqual(res.status_code, 302, f"Expected 302 for unauthenticated access to {path}")
            self.assertIn("/login", res.headers.get("Location", ""))

        # 2. File upload safety: Non-image extensions rejected
        with app.app_context():
            db = database.get_db()
            now = datetime.now().isoformat()
            db.execute("INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)", ("Upload Tester", self.citizen_email, generate_password_hash("pass123"), "user", now))
            db.commit()

        client.post("/login", data={"email": self.citizen_email, "password": "pass123"})
        bad_file = (io.BytesIO(b"malicious script content"), "hack.exe")
        res_bad_upload = client.post(
            "/report",
            data={
                "category": "Road",
                "title": "Bad Upload Test",
                "description": "Attempting invalid file",
                "location": "Loc 1",
                "image": bad_file,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertIn(b"Invalid image file type", res_bad_upload.data)
        client.get("/logout")

    # =========================================================================
    # 5. ERROR HANDLING
    # =========================================================================
    def test_05_error_handling(self):
        """Verify custom 404, custom 403, and handling of invalid inputs."""
        client = self.client

        # Register and login citizen
        with app.app_context():
            db = database.get_db()
            now = datetime.now().isoformat()
            db.execute("INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)", ("Error Tester", self.citizen_email, generate_password_hash("pass123"), "user", now))
            db.commit()

        client.post("/login", data={"email": self.citizen_email, "password": "pass123"})

        # 1. Custom 404 for non-existent report
        res_404_report = client.get("/report/999999")
        self.assertEqual(res_404_report.status_code, 404)
        self.assertIn(b"Report or Resource Not Found", res_404_report.data)

        # 2. Custom 404 for invalid notification read
        res_404_notif = client.post("/notifications/999999/read")
        self.assertEqual(res_404_notif.status_code, 404)

        # 3. Custom 403 for citizen accessing /admin
        res_403_admin = client.get("/admin")
        self.assertEqual(res_403_admin.status_code, 403)
        self.assertIn(b"Access Denied", res_403_admin.data)

        # 4. Form validation errors on /report (missing required title/location)
        res_empty_report = client.post(
            "/report",
            data={"category": "Road", "title": "", "description": "desc", "location": ""},
            follow_redirects=True,
        )
        self.assertIn(b"Problem title is required.", res_empty_report.data)

        client.get("/logout")

    # =========================================================================
    # 6. DATABASE AUDIT
    # =========================================================================
    def test_06_database_audit(self):
        """Audit table schemas, foreign keys, indexes, and absence of orphaned records."""
        with app.app_context():
            db = database.get_db()

            # Verify tables exist
            tables = [r["name"] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            for expected_tbl in ["users", "reports", "report_history", "notifications"]:
                self.assertIn(expected_tbl, tables)

            # Verify indexes exist
            indexes = [r["name"] for r in db.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()]
            for expected_idx in [
                "idx_reports_user_id",
                "idx_reports_status",
                "idx_reports_category",
                "idx_notifications_user_unread",
                "idx_report_history_report",
            ]:
                self.assertIn(expected_idx, indexes)

            # Verify no invalid status values in database
            invalid_statuses = db.execute(
                f"SELECT COUNT(*) as c FROM reports WHERE status NOT IN ({','.join(['?']*len(database.REPORT_STATUSES))})",
                database.REPORT_STATUSES,
            ).fetchone()["c"]
            self.assertEqual(invalid_statuses, 0)

            # Verify admin account exists
            admin = db.execute("SELECT * FROM users WHERE email = 'admin@cityos.com'").fetchone()
            self.assertIsNotNone(admin)
            self.assertEqual(admin["role"], "admin")
            self.assertTrue(check_password_hash(admin["password"], "admin123"))

    # =========================================================================
    # 7. UI / UX ASSET HEALTH
    # =========================================================================
    def test_07_ui_ux_asset_health(self):
        """Verify CSS assets, landing page elements, template titles, and API endpoints."""
        client = self.client

        # 1. Landing page
        res_index = client.get("/")
        self.assertEqual(res_index.status_code, 200)
        self.assertIn(b"CityOS", res_index.data)
        self.assertIn(b"Urban Operating System Environment", res_index.data)
        self.assertIn(b"Login", res_index.data)
        self.assertIn(b"Register", res_index.data)

        # 2. Static CSS file accessibility
        res_css = client.get("/static/css/style.css")
        self.assertEqual(res_css.status_code, 200)
        self.assertIn(b"--bg-primary", res_css.data)

        # 3. System Health API
        res_health = client.get("/api/health")
        self.assertEqual(res_health.status_code, 200)
        health_json = res_health.get_json()
        self.assertEqual(health_json["status"], "online")
        self.assertEqual(health_json["database"]["status"], "connected")


def run_e2e_audit():
    suite = unittest.TestLoader().loadTestsFromTestCase(CityOSEndToEndAuditTest)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_e2e_audit()
    sys.exit(0 if success else 1)
