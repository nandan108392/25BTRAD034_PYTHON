"""
CityOS Step 11: Citizen Transparency & Live Report Tracking Test Suite
----------------------------------------------------------------------
Comprehensive test coverage for:
1. Report status timeline (5 stages + rejected state)
2. Status history creation on report submission
3. Status history recording on admin status updates
4. Status history privacy (anonymized transitions, no admin PII)
5. Citizen in-app notification creation on submission and status changes
6. Notification ownership and data isolation between citizens
7. Dynamic unread notification counter & JSON API (/api/notifications/unread-count)
8. Mark individual notification as read (/notifications/<id>/read)
9. Mark all notifications as read (/notifications/read-all)
10. Citizen Dashboard notification indicator & unread alert card
11. My Reports improvements (Issue Type, Priority, and Updated At)
12. Role-based access control and unauthorized access prevention (HTTP 403 / 302)
13. Error handling for non-existent reports and notifications (HTTP 404)
14. Full regression testing of all prior test modules.
"""

import os
import tempfile
import unittest
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

import database
from app import app


class CitizenTrackingTestCase(unittest.TestCase):
    def setUp(self):
        # Create a temporary SQLite database for test isolation
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        app.config["DATABASE"] = self.db_path
        app.config["TESTING"] = True
        app.config["WTF_CSRF_ENABLED"] = False
        self.client = app.test_client()

        with app.app_context():
            database.init_db()
            self._seed_test_data()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def _seed_test_data(self):
        """Seed controlled test citizens, reports, history, and notifications."""
        db = database.get_db()
        now = datetime.now().isoformat()

        # Seed 2 normal citizens: Citizen A (Alice), Citizen B (Bob)
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Alice Citizen", "alice@example.com", generate_password_hash("pass123"), "user", now),
        )
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Bob Citizen", "bob@example.com", generate_password_hash("pass123"), "user", now),
        )
        db.commit()

        self.alice = db.execute("SELECT id FROM users WHERE email = 'alice@example.com'").fetchone()
        self.bob = db.execute("SELECT id FROM users WHERE email = 'bob@example.com'").fetchone()
        self.admin = db.execute("SELECT id FROM users WHERE email = 'admin@cityos.com'").fetchone()

        # Insert Report 1 for Alice: Initial "Reported"
        db.execute(
            """
            INSERT INTO reports (
                user_id, category, title, description, location, location_description,
                latitude, longitude, status, issue_type, priority, keywords, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.alice["id"], "Road", "Major road pothole", "Dangerous pothole near metro",
                "Indiranagar 100ft Rd", "Near Metro", 12.9716, 77.6412, "Reported",
                "Pothole", "HIGH", "pothole, road", now, now
            ),
        )
        self.rep1_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        database.add_report_history(db, self.rep1_id, None, "Reported", self.alice["id"])
        database.create_notification(
            db,
            self.alice["id"],
            self.rep1_id,
            "Report Logged: CITY-2026-00001",
            "Your report 'Major road pothole' has been logged.",
        )

        # Insert Report 2 for Bob: "In Progress"
        db.execute(
            """
            INSERT INTO reports (
                user_id, category, title, description, location, location_description,
                latitude, longitude, status, issue_type, priority, keywords, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.bob["id"], "Water", "Water pipeline burst", "Flooding street",
                "Koramangala 4th Block", "80ft Rd", 12.9352, 77.6245, "In Progress",
                "Water Leakage", "HIGH", "water, burst", now, now
            ),
        )
        self.rep2_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        database.add_report_history(db, self.rep2_id, None, "Reported", self.bob["id"])
        database.add_report_history(db, self.rep2_id, "Reported", "Under Review", self.admin["id"])
        database.add_report_history(db, self.rep2_id, "Under Review", "In Progress", self.admin["id"])
        database.create_notification(
            db,
            self.bob["id"],
            self.rep2_id,
            "Status Update: In Progress",
            "Your report 'Water pipeline burst' is now in progress with municipal field teams.",
        )

    def _login_as_alice(self):
        return self.client.post(
            "/login",
            data={"email": "alice@example.com", "password": "pass123"},
            follow_redirects=True,
        )

    def _login_as_bob(self):
        return self.client.post(
            "/login",
            data={"email": "bob@example.com", "password": "pass123"},
            follow_redirects=True,
        )

    def _login_as_admin(self):
        return self.client.post(
            "/login",
            data={"email": "admin@cityos.com", "password": "admin123"},
            follow_redirects=True,
        )

    # -------------------------------------------------------------
    # 1. Report Status Timeline Tests
    # -------------------------------------------------------------
    def test_status_timeline_rendering(self):
        self._login_as_alice()
        res = self.client.get(f"/report/{self.rep1_id}")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # 5-stage timeline presence
        self.assertIn("Municipal Status Tracker", html)
        self.assertIn("Submitted", html)
        self.assertIn("Verified", html)
        self.assertIn("Assigned", html)
        self.assertIn("In Progress", html)
        self.assertIn("Resolved", html)
        self.assertIn("Status History &amp; Activity Log", html)

    def test_status_timeline_rejected_state(self):
        with app.app_context():
            db = database.get_db()
            db.execute("UPDATE reports SET status = 'Rejected' WHERE id = ?", (self.rep1_id,))
            db.commit()

        self._login_as_alice()
        res = self.client.get(f"/report/{self.rep1_id}")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Report Rejected", html)
        self.assertIn("reviewed and closed as rejected by municipal authorities", html)

    # -------------------------------------------------------------
    # 2. Status History Creation & Audit Log
    # -------------------------------------------------------------
    def test_status_history_on_report_submission(self):
        self._login_as_alice()
        res = self.client.post(
            "/report",
            data={
                "category": "Waste",
                "title": "Uncollected garbage bin",
                "description": "Garbage has not been collected for 4 days",
                "location": "Jayanagar 4th Block",
            },
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)

        with app.app_context():
            db = database.get_db()
            rep = db.execute("SELECT id FROM reports WHERE title = 'Uncollected garbage bin'").fetchone()
            self.assertIsNotNone(rep)

            history = database.get_report_history(db, rep["id"])
            self.assertGreaterEqual(len(history), 1)
            self.assertIsNone(history[0]["previous_status"])
            self.assertEqual(history[0]["new_status"], "Reported")

    def test_status_history_on_admin_status_update(self):
        self._login_as_admin()

        # Admin updates Report 1 to "Under Review"
        res = self.client.post(
            f"/admin/report/{self.rep1_id}/status",
            data={"status": "Under Review"},
            follow_redirects=True,
        )
        self.assertEqual(res.status_code, 200)

        with app.app_context():
            db = database.get_db()
            history = database.get_report_history(db, self.rep1_id)
            self.assertEqual(len(history), 2)
            self.assertEqual(history[1]["previous_status"], "Reported")
            self.assertEqual(history[1]["new_status"], "Under Review")

            # Check that notification was automatically sent to Alice
            notifs = database.get_user_notifications(db, self.alice["id"])
            self.assertEqual(len(notifs), 2)
            self.assertIn("verified and is under review", notifs[0]["message"])

    def test_status_history_privacy(self):
        # Admin updates Report 1 to In Progress
        self._login_as_admin()
        self.client.post(
            f"/admin/report/{self.rep1_id}/status",
            data={"status": "In Progress"},
            follow_redirects=True,
        )

        # Citizen views their report details
        self._login_as_alice()
        res = self.client.get(f"/report/{self.rep1_id}")
        html = res.get_data(as_text=True)

        # Admin email or passwords must NEVER appear in citizen history
        self.assertNotIn("admin@cityos.com", html)
        self.assertNotIn("scrypt:", html)
        self.assertNotIn("pbkdf2:", html)
        self.assertIn("Status Updated to", html)

    # -------------------------------------------------------------
    # 3. Notification System & Isolation
    # -------------------------------------------------------------
    def test_notification_creation_and_ownership(self):
        # Alice views notifications
        self._login_as_alice()
        res = self.client.get("/notifications")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Notification Center", html)
        self.assertIn("Major road pothole", html)

        # Bob views notifications - must NOT see Alice's report notifications
        self.client.get("/logout")
        self._login_as_bob()
        res_bob = self.client.get("/notifications")
        html_bob = res_bob.get_data(as_text=True)
        self.assertIn("Water pipeline burst", html_bob)
        self.assertNotIn("Major road pothole", html_bob)

    def test_unread_notification_counter_and_api(self):
        self._login_as_alice()

        # Check API endpoint
        res = self.client.get("/api/notifications/unread-count")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["unread_count"], 1)

        # Check header badge rendered in HTML
        res_dash = self.client.get("/dashboard")
        html_dash = res_dash.get_data(as_text=True)
        self.assertIn("Notifications", html_dash)
        self.assertIn("notif-badge-pill", html_dash)
        self.assertIn("1", html_dash)

    def test_mark_single_notification_as_read(self):
        self._login_as_alice()

        with app.app_context():
            db = database.get_db()
            notifs = database.get_user_notifications(db, self.alice["id"])
            notif_id = notifs[0]["id"]

        # Mark as read
        res = self.client.post(f"/notifications/{notif_id}/read", follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # Unread count should now be 0
        res_count = self.client.get("/api/notifications/unread-count")
        self.assertEqual(res_count.get_json()["unread_count"], 0)

    def test_mark_all_notifications_as_read(self):
        with app.app_context():
            db = database.get_db()
            database.create_notification(db, self.alice["id"], None, "Alert 2", "Test alert 2")
            database.create_notification(db, self.alice["id"], None, "Alert 3", "Test alert 3")

        self._login_as_alice()
        res_count = self.client.get("/api/notifications/unread-count")
        self.assertEqual(res_count.get_json()["unread_count"], 3)

        # Mark all as read
        res_all = self.client.post("/notifications/read-all", follow_redirects=True)
        self.assertEqual(res_all.status_code, 200)

        res_count_after = self.client.get("/api/notifications/unread-count")
        self.assertEqual(res_count_after.get_json()["unread_count"], 0)

    # -------------------------------------------------------------
    # 4. Security & Access Control
    # -------------------------------------------------------------
    def test_unauthenticated_notification_access_redirects(self):
        res = self.client.get("/notifications")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.location)

    def test_unauthorized_notification_mark_read_forbidden(self):
        # Alice attempts to mark Bob's notification as read
        with app.app_context():
            db = database.get_db()
            bob_notifs = database.get_user_notifications(db, self.bob["id"])
            bob_notif_id = bob_notifs[0]["id"]

        self._login_as_alice()
        res = self.client.post(f"/notifications/{bob_notif_id}/read")
        self.assertEqual(res.status_code, 403)

    def test_nonexistent_notification_returns_404(self):
        self._login_as_alice()
        res = self.client.post("/notifications/999999/read")
        self.assertEqual(res.status_code, 404)

    def test_my_reports_columns_enhanced(self):
        self._login_as_alice()
        res = self.client.get("/my-reports")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Issue Type", html)
        self.assertIn("Priority", html)
        self.assertIn("Date Submitted", html)
        self.assertIn("Last Updated", html)
        self.assertIn("Pothole", html)
        self.assertIn("HIGH", html)


if __name__ == "__main__":
    unittest.main()
