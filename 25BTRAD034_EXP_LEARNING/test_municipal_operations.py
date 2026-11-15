"""
CityOS Phase 3: Municipal Operations & Resolution Workflow Test Suite
---------------------------------------------------------------------
Comprehensive test coverage for:
1. Municipal department structure & default seeding (9 departments + field teams)
2. Report department assignment workflow
3. Field team assignment workflow
4. Role-based access control (RBAC) & unauthorized operation prevention (HTTP 403 / 302)
5. Operational status transitions across all lifecycle states
6. Work progress update logging (public vs. internal)
7. Citizen visibility of public updates & data isolation from internal notes
8. Resolution evidence photo upload & file security validation
9. Invalid / executable evidence file rejection
10. Municipal quality verification & formal resolution workflow
11. Real-time citizen in-app lifecycle notifications
12. Citizen data isolation and privacy protection (no admin/staff PII leakage)
13. Admin operations dashboard KPIs and department-level filtering
14. Non-existent report handling (HTTP 404)
15. Cascading department field teams API (/api/departments/<id>/teams)
"""

import os
import io
import tempfile
import unittest
from datetime import datetime
from werkzeug.security import generate_password_hash

import database
from app import app


class MunicipalOperationsTestCase(unittest.TestCase):
    def setUp(self):
        # Create isolated temporary SQLite database for test execution
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
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def _seed_test_data(self):
        """Seed controlled test citizens, reports, and admin accounts."""
        db = database.get_db()
        now = datetime.now().isoformat()

        # Create Citizen 1 (Alice)
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Alice Citizen", "alice@example.com", generate_password_hash("pass123"), "user", now),
        )
        # Create Citizen 2 (Bob)
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Bob Citizen", "bob@example.com", generate_password_hash("pass123"), "user", now),
        )
        db.commit()

        self.alice = db.execute("SELECT * FROM users WHERE email = 'alice@example.com'").fetchone()
        self.bob = db.execute("SELECT * FROM users WHERE email = 'bob@example.com'").fetchone()
        self.admin = db.execute("SELECT * FROM users WHERE email = 'admin@cityos.com'").fetchone()

        # Seed Report 1 for Alice (Pothole issue)
        db.execute(
            """
            INSERT INTO reports (
                user_id, category, title, description, location, location_description,
                latitude, longitude, status, issue_type, priority, keywords, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.alice["id"], "Road", "Dangerous Road Pothole", "Large deep pothole on main road",
                "MG Road Junction", "Near Metro Pillar 42", 12.9716, 77.6412, "Reported",
                "Pothole", "HIGH", "pothole, road", now, now
            ),
        )
        self.rep1_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        database.add_report_history(db, self.rep1_id, None, "Reported", self.alice["id"])

        # Seed Report 2 for Bob (Water leakage)
        db.execute(
            """
            INSERT INTO reports (
                user_id, category, title, description, location, location_description,
                latitude, longitude, status, issue_type, priority, keywords, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.bob["id"], "Water", "Burst Water Pipe", "Water flooding street",
                "Brigade Road", "Opposite Cafe", 12.9730, 77.6080, "Under Review",
                "Water Leakage", "HIGH", "water, leak", now, now
            ),
        )
        self.rep2_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]
        database.add_report_history(db, self.rep2_id, None, "Reported", self.bob["id"])
        database.add_report_history(db, self.rep2_id, "Reported", "Under Review", self.admin["id"])

    # --------------------------------------------------------------------------
    # 1. Department Structure & Initial Seeding
    # --------------------------------------------------------------------------
    def test_department_seeding(self):
        """Verify all 9 municipal departments and field teams are initialized."""
        with app.app_context():
            db = database.get_db()
            departments = database.get_departments(db)
            dept_names = [d["name"] for d in departments]

            expected_depts = [
                "Roads & Infrastructure",
                "Water Supply",
                "Sanitation",
                "Street Lighting",
                "Traffic",
                "Parks & Public Spaces",
                "Waste Management",
                "Electrical",
                "Other",
            ]
            for ed in expected_depts:
                self.assertIn(ed, dept_names)

            # Check field teams exist
            teams = database.get_all_field_teams(db)
            self.assertGreater(len(teams), 0)
            road_teams = [t for t in teams if t["department_name"] == "Roads & Infrastructure"]
            self.assertGreater(len(road_teams), 0)

    # --------------------------------------------------------------------------
    # 2. Report Department & Field Team Assignment
    # --------------------------------------------------------------------------
    def test_assign_report_to_department_and_team(self):
        """Admin assigns a report to a department and field team."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin["id"]
            sess["role"] = "admin"
            sess["name"] = "System Admin"

        with app.app_context():
            db = database.get_db()
            roads_dept = database.get_department_by_code(db, "ROADS")
            teams = database.get_field_teams_by_department(db, roads_dept["id"])
            team_id = teams[0]["id"] if teams else None

        resp = self.client.post(
            f"/admin/report/{self.rep1_id}/assign",
            data={
                "department_id": roads_dept["id"],
                "field_team_id": team_id or "",
                "assignment_notes": "Priority road patch required",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Report successfully assigned", resp.data)

        # Verify assignment stored in database
        with app.app_context():
            db = database.get_db()
            assignment = database.get_report_assignment_details(db, self.rep1_id)
            self.assertIsNotNone(assignment)
            self.assertEqual(assignment["department_name"], "Roads & Infrastructure")
            self.assertEqual(assignment["assignment_notes"], "Priority road patch required")

            # Verify report status transitioned to 'Assigned'
            rep = db.execute("SELECT status FROM reports WHERE id = ?", (self.rep1_id,)).fetchone()
            self.assertEqual(rep["status"], "Assigned")

            # Verify notification created for citizen
            notifs = database.get_user_notifications(db, self.alice["id"])
            self.assertTrue(any("Roads & Infrastructure" in n["title"] or "Roads & Infrastructure" in n["message"] for n in notifs))

    # --------------------------------------------------------------------------
    # 3. Unauthorized Operations / RBAC
    # --------------------------------------------------------------------------
    def test_unauthorized_operations_rejected(self):
        """Citizens cannot access municipal operational endpoints."""
        # Logged in as citizen (Alice)
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.alice["id"]
            sess["role"] = "user"
            sess["name"] = "Alice Citizen"

        # 1. Assignment attempt
        resp_assign = self.client.post(
            f"/admin/report/{self.rep1_id}/assign",
            data={"department_id": 1},
        )
        self.assertEqual(resp_assign.status_code, 403)

        # 2. Progress update attempt
        resp_update = self.client.post(
            f"/admin/report/{self.rep1_id}/update",
            data={"update_text": "Hacked note"},
        )
        self.assertEqual(resp_update.status_code, 403)

        # 3. Evidence upload attempt
        resp_ev = self.client.post(
            f"/admin/report/{self.rep1_id}/evidence",
            data={"caption": "Unauthorized"},
        )
        self.assertEqual(resp_ev.status_code, 403)

        # 4. Verification attempt
        resp_ver = self.client.post(f"/admin/report/{self.rep1_id}/verify")
        self.assertEqual(resp_ver.status_code, 403)

        # 5. Admin Dashboard access
        resp_admin = self.client.get("/admin")
        self.assertEqual(resp_admin.status_code, 403)

    # --------------------------------------------------------------------------
    # 4. Operational Status Workflow Transitions
    # --------------------------------------------------------------------------
    def test_operational_status_transitions(self):
        """Admin can transition through all operational workflow states."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin["id"]
            sess["role"] = "admin"
            sess["name"] = "System Admin"

        lifecycle = [
            "Under Review",
            "Assigned",
            "Accepted",
            "In Progress",
            "Work Completed",
            "Verification Required",
            "Verified",
            "Resolved",
        ]

        for st in lifecycle:
            resp = self.client.post(
                f"/admin/report/{self.rep1_id}/status",
                data={"status": st},
                follow_redirects=True,
            )
            self.assertEqual(resp.status_code, 200)

            with app.app_context():
                db = database.get_db()
                rep = db.execute("SELECT status FROM reports WHERE id = ?", (self.rep1_id,)).fetchone()
                self.assertEqual(rep["status"], st)

        # Check report_history audit trail contains all transitions
        with app.app_context():
            db = database.get_db()
            history = database.get_report_history(db, self.rep1_id)
            history_statuses = [h["new_status"] for h in history]
            for st in lifecycle:
                self.assertIn(st, history_statuses)

    # --------------------------------------------------------------------------
    # 5. Work Progress Updates (Public vs. Internal)
    # --------------------------------------------------------------------------
    def test_progress_updates_and_citizen_visibility(self):
        """Verify public updates are visible to citizens while internal notes remain private."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin["id"]
            sess["role"] = "admin"
            sess["name"] = "System Admin"

        # 1. Log Public Update
        resp_pub = self.client.post(
            f"/admin/report/{self.rep1_id}/update",
            data={
                "update_text": "Public: Asphalt compaction crew deployed on site.",
                "operational_status": "In Progress",
                "is_public": "1",
            },
            follow_redirects=True,
        )
        self.assertEqual(resp_pub.status_code, 200)

        # 2. Log Internal Admin Update
        resp_priv = self.client.post(
            f"/admin/report/{self.rep1_id}/update",
            data={
                "update_text": "Internal: Contractor delayed by 20 minutes due to machinery refuel.",
                "operational_status": "In Progress",
                # Unchecked is_public
            },
            follow_redirects=True,
        )
        self.assertEqual(resp_priv.status_code, 200)

        # 3. Citizen Alice views her report
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.alice["id"]
            sess["role"] = "user"
            sess["name"] = "Alice Citizen"

        resp_citizen = self.client.get(f"/report/{self.rep1_id}")
        self.assertEqual(resp_citizen.status_code, 200)

        # Citizen MUST see public update
        self.assertIn(b"Asphalt compaction crew deployed on site.", resp_citizen.data)

        # Citizen MUST NOT see internal private note
        self.assertNotIn(b"Contractor delayed by 20 minutes due to machinery refuel", resp_citizen.data)

    # --------------------------------------------------------------------------
    # 6. Resolution Evidence Upload & Validation
    # --------------------------------------------------------------------------
    def test_resolution_evidence_upload_valid(self):
        """Admin uploads valid resolution evidence photo."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin["id"]
            sess["role"] = "admin"
            sess["name"] = "System Admin"

        # Create dummy image file in memory
        fake_image = (io.BytesIO(b"FakePNGDataForTestingResolutionImage"), "completed_road.png")

        resp = self.client.post(
            f"/admin/report/{self.rep1_id}/evidence",
            data={
                "evidence_image": fake_image,
                "caption": "Pothole filled and hot-rolled asphalt sealed",
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Resolution evidence photo uploaded successfully", resp.data)

        # Verify evidence recorded in DB
        with app.app_context():
            db = database.get_db()
            evidence = database.get_resolution_evidence(db, self.rep1_id)
            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0]["caption"], "Pothole filled and hot-rolled asphalt sealed")
            self.assertEqual(evidence[0]["verified"], 0)

            # Report status updated to Verification Required
            rep = db.execute("SELECT status FROM reports WHERE id = ?", (self.rep1_id,)).fetchone()
            self.assertEqual(rep["status"], "Verification Required")

    def test_invalid_evidence_file_rejected(self):
        """Executable or non-image files must be rejected."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin["id"]
            sess["role"] = "admin"
            sess["name"] = "System Admin"

        # Try uploading .exe
        fake_exe = (io.BytesIO(b"MZExecutableContent"), "malicious_script.exe")

        resp = self.client.post(
            f"/admin/report/{self.rep1_id}/evidence",
            data={"evidence_image": fake_exe, "caption": "Bad file"},
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Invalid image file type", resp.data)

        # Ensure no evidence record was inserted
        with app.app_context():
            db = database.get_db()
            evidence = database.get_resolution_evidence(db, self.rep1_id)
            self.assertEqual(len(evidence), 0)

    # --------------------------------------------------------------------------
    # 7. Municipal Verification & Resolution Workflow
    # --------------------------------------------------------------------------
    def test_municipal_verification_workflow(self):
        """Admin verifies resolution evidence and resolves report."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin["id"]
            sess["role"] = "admin"
            sess["name"] = "System Admin"

        # 1. Attach evidence
        fake_image = (io.BytesIO(b"FakeJPEGData"), "repaired_pipe.jpg")
        self.client.post(
            f"/admin/report/{self.rep2_id}/evidence",
            data={"evidence_image": fake_image, "caption": "Pipeline repaired"},
            content_type="multipart/form-data",
            follow_redirects=True,
        )

        # 2. Verify and resolve
        resp_verify = self.client.post(
            f"/admin/report/{self.rep2_id}/verify",
            follow_redirects=True,
        )
        self.assertEqual(resp_verify.status_code, 200)
        self.assertIn(b"Report resolution verified and closed successfully", resp_verify.data)

        # Verify DB states
        with app.app_context():
            db = database.get_db()
            rep = db.execute("SELECT status FROM reports WHERE id = ?", (self.rep2_id,)).fetchone()
            self.assertEqual(rep["status"], "Resolved")

            evidence = database.get_resolution_evidence(db, self.rep2_id)
            self.assertEqual(evidence[0]["verified"], 1)

            # Check citizen Bob received resolution notification
            notifs = database.get_user_notifications(db, self.bob["id"])
            self.assertTrue(any("resolved" in n["title"].lower() or "resolved" in n["message"].lower() for n in notifs))

    # --------------------------------------------------------------------------
    # 8. Citizen Data Isolation & Privacy Guardrails
    # --------------------------------------------------------------------------
    def test_citizen_privacy_and_data_isolation(self):
        """Citizen cannot view private admin info or other citizens' reports."""
        with app.app_context():
            db = database.get_db()
            roads_dept = database.get_department_by_code(db, "ROADS")
            database.assign_report_department(
                db, self.rep1_id, roads_dept["id"], notes="Confidential contact: 9999999999"
            )

        with self.client.session_transaction() as sess:
            sess["user_id"] = self.alice["id"]
            sess["role"] = "user"
            sess["name"] = "Alice Citizen"

        # Alice views her report
        resp = self.client.get(f"/report/{self.rep1_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Roads &amp; Infrastructure", resp.data)

        # Must NOT expose admin password or private notes
        self.assertNotIn(b"admin@cityos.com", resp.data)
        self.assertNotIn(b"Confidential contact", resp.data)

        # Alice tries viewing Bob's report (Report 2) -> 403 Forbidden
        resp_bob = self.client.get(f"/report/{self.rep2_id}")
        self.assertEqual(resp_bob.status_code, 403)

    # --------------------------------------------------------------------------
    # 9. Admin Operations Dashboard & Department Filtering
    # --------------------------------------------------------------------------
    def test_admin_dashboard_department_filtering(self):
        """Admin dashboard properly filters reports by department."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin["id"]
            sess["role"] = "admin"
            sess["name"] = "System Admin"

        with app.app_context():
            db = database.get_db()
            roads = database.get_department_by_code(db, "ROADS")
            water = database.get_department_by_code(db, "WATER")
            database.assign_report_department(db, self.rep1_id, roads["id"])
            database.assign_report_department(db, self.rep2_id, water["id"])

        # Filter by ROADS
        resp_roads = self.client.get("/admin?department=ROADS")
        self.assertEqual(resp_roads.status_code, 200)
        self.assertIn(b"Dangerous Road Pothole", resp_roads.data)
        self.assertNotIn(b"Burst Water Pipe", resp_roads.data)

        # Filter by WATER
        resp_water = self.client.get("/admin?department=WATER")
        self.assertEqual(resp_water.status_code, 200)
        self.assertIn(b"Burst Water Pipe", resp_water.data)
        self.assertNotIn(b"Dangerous Road Pothole", resp_water.data)

    # --------------------------------------------------------------------------
    # 10. Non-Existent Report Handling & Teams API
    # --------------------------------------------------------------------------
    def test_non_existent_report_returns_404(self):
        """Operations on non-existent report IDs must return HTTP 404."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin["id"]
            sess["role"] = "admin"
            sess["name"] = "System Admin"

        invalid_id = 99999
        self.assertEqual(self.client.get(f"/admin/report/{invalid_id}").status_code, 404)
        self.assertEqual(self.client.post(f"/admin/report/{invalid_id}/assign", data={"department_id": 1}).status_code, 404)
        self.assertEqual(self.client.post(f"/admin/report/{invalid_id}/update", data={"update_text": "Note"}).status_code, 404)
        self.assertEqual(self.client.post(f"/admin/report/{invalid_id}/evidence").status_code, 404)
        self.assertEqual(self.client.post(f"/admin/report/{invalid_id}/verify").status_code, 404)

    def test_department_teams_api(self):
        """API endpoint /api/departments/<id>/teams returns JSON field teams."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.admin["id"]
            sess["role"] = "admin"
            sess["name"] = "System Admin"

        with app.app_context():
            db = database.get_db()
            roads = database.get_department_by_code(db, "ROADS")
            dept_id = roads["id"]

        resp = self.client.get(f"/api/departments/{dept_id}/teams")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)


if __name__ == "__main__":
    unittest.main()
