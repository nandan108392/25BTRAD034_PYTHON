import os
import sys
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash
from app import app
import database

# Windows console encoding safeguard
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def setup_test_data():
    """Sets up isolated test users and reports in the database."""
    with app.app_context():
        db = database.get_db()
        # Clean up prior test records
        db.execute("DELETE FROM reports WHERE title LIKE 'TestReport_%'")
        db.execute("DELETE FROM users WHERE email IN ('user_a@cityos.com', 'user_b@cityos.com', 'empty_user@cityos.com')")
        
        now = datetime.now().isoformat()
        pw_hash = generate_password_hash("password123")

        # Create User A
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("User Alpha", "user_a@cityos.com", pw_hash, "user", now),
        )
        user_a_id = db.execute("SELECT id FROM users WHERE email = 'user_a@cityos.com'").fetchone()["id"]

        # Create User B
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("User Beta", "user_b@cityos.com", pw_hash, "user", now),
        )
        user_b_id = db.execute("SELECT id FROM users WHERE email = 'user_b@cityos.com'").fetchone()["id"]

        # Create Empty User (0 reports)
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Empty User", "empty_user@cityos.com", pw_hash, "user", now),
        )
        empty_user_id = db.execute("SELECT id FROM users WHERE email = 'empty_user@cityos.com'").fetchone()["id"]

        # Insert reports for User A:
        # 2 Reported, 1 In Progress, 1 Resolved, 1 Under Review => Total = 5
        reports_user_a = [
            (user_a_id, "Pothole", "TestReport_Pothole_1", "Main St", "Reported", now, now),
            (user_a_id, "Garbage", "TestReport_Garbage_1", "2nd Ave", "Reported", now, now),
            (user_a_id, "Streetlight", "TestReport_Light_1", "Oak Rd", "In Progress", now, now),
            (user_a_id, "Water Leakage", "TestReport_Water_1", "Pine Ln", "Resolved", now, now),
            (user_a_id, "Road Damage", "TestReport_Road_1", "Elm St", "Under Review", now, now),
        ]
        for r in reports_user_a:
            db.execute(
                """
                INSERT INTO reports (user_id, category, title, location, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                r,
            )

        # Insert reports for User B (to test isolation):
        reports_user_b = [
            (user_b_id, "Drainage", "TestReport_UserB_Drain", "Broad St", "In Progress", now, now),
            (user_b_id, "Traffic Problem", "TestReport_UserB_Traffic", "Highway 1", "Reported", now, now),
        ]
        for r in reports_user_b:
            db.execute(
                """
                INSERT INTO reports (user_id, category, title, location, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                r,
            )

        db.commit()
        return user_a_id, user_b_id, empty_user_id


def run_dashboard_tests():
    print("==================================================")
    print("        CityOS Citizen Dashboard Test Suite       ")
    print("==================================================")
    all_passed = True
    user_a_id, user_b_id, empty_user_id = setup_test_data()

    with app.test_client() as client:
        # TEST 1: Unauthenticated access redirects to login
        res_unauth = client.get("/dashboard", follow_redirects=False)
        if res_unauth.status_code == 302 and "/login" in res_unauth.headers.get("Location", ""):
            print("[PASS] [TEST 1] Unauthenticated access to /dashboard redirects to /login.")
        else:
            print(f"[FAIL] [TEST 1] Unauthenticated access not redirected. Status: {res_unauth.status_code}")
            all_passed = False

        # TEST 2: Normal user can access dashboard
        # Login User A
        client.post("/login", data={"email": "user_a@cityos.com", "password": "password123"})
        res_user_a = client.get("/dashboard")
        if res_user_a.status_code == 200 and b"Welcome, User Alpha" in res_user_a.data:
            print("[PASS] [TEST 2] Normal user successfully accessed /dashboard with welcome message.")
        else:
            print(f"[FAIL] [TEST 2] Normal user access failed. Status: {res_user_a.status_code}")
            all_passed = False

        # TEST 3: Admin is redirected to admin dashboard
        client.get("/logout")
        client.post("/login", data={"email": "admin@cityos.com", "password": "admin123"})
        res_admin_dash = client.get("/dashboard", follow_redirects=False)
        if res_admin_dash.status_code == 302 and res_admin_dash.headers.get("Location") == "/admin":
            print("[PASS] [TEST 3] Admin accessing /dashboard was redirected to /admin.")
        else:
            print(f"[FAIL] [TEST 3] Admin redirect failed. Location: {res_admin_dash.headers.get('Location')}")
            all_passed = False

        # Login back as User A for metrics & isolation tests
        client.get("/logout")
        client.post("/login", data={"email": "user_a@cityos.com", "password": "password123"})
        res_metrics = client.get("/dashboard")
        content_a = res_metrics.data.decode("utf-8")

        # TEST 4: Total report count is correct (User A has 5 reports)
        if '<span class="stat-number" id="stat-total">5</span>' in content_a:
            print("[PASS] [TEST 4] Total report count is correct (5).")
        else:
            print("[FAIL] [TEST 4] Total report count mismatch.")
            all_passed = False

        # TEST 5: Reported count is correct (User A has 2 'Reported')
        if '<span class="stat-number stat-blue" id="stat-reported">2</span>' in content_a:
            print("[PASS] [TEST 5] Reported status count is correct (2).")
        else:
            print("[FAIL] [TEST 5] Reported count mismatch.")
            all_passed = False

        # TEST 6: In Progress count is correct (User A has 1 'In Progress')
        if '<span class="stat-number stat-amber" id="stat-progress">1</span>' in content_a:
            print("[PASS] [TEST 6] In Progress status count is correct (1).")
        else:
            print("[FAIL] [TEST 6] In Progress count mismatch.")
            all_passed = False

        # TEST 7: Resolved count is correct (User A has 1 'Resolved')
        if '<span class="stat-number stat-green" id="stat-resolved">1</span>' in content_a:
            print("[PASS] [TEST 7] Resolved status count is correct (1).")
        else:
            print("[FAIL] [TEST 7] Resolved count mismatch.")
            all_passed = False

        # TEST 8: Only logged-in user's reports are displayed (Isolation test)
        # User A should see their reports and NOT see User B's reports
        has_user_a_report = "TestReport_Pothole_1" in content_a
        has_user_b_report = "TestReport_UserB_Drain" in content_a
        if has_user_a_report and not has_user_b_report:
            print("[PASS] [TEST 8] Data isolation verified: User A only sees their own reports, User B's reports are hidden.")
        else:
            print(f"[FAIL] [TEST 8] Isolation failed. has_a={has_user_a_report}, has_b={has_user_b_report}")
            all_passed = False

        # TEST 9: Empty state works correctly
        client.get("/logout")
        client.post("/login", data={"email": "empty_user@cityos.com", "password": "password123"})
        res_empty = client.get("/dashboard")
        content_empty = res_empty.data.decode("utf-8")

        if (
            "You haven't submitted any reports yet." in content_empty
            and ("Report a Problem" in content_empty or "Report Your First Problem" in content_empty)
            and '<span class="stat-number" id="stat-total">0</span>' in content_empty
        ):
            print("[PASS] [TEST 9] Empty state card and 0 counts rendered properly for user with no reports.")
        else:
            print("[FAIL] [TEST 9] Empty state did not render properly.")
            all_passed = False

    print("==================================================")
    if all_passed:
        print("🎉 ALL 9 CITIZEN DASHBOARD TESTS PASSED!")
        return 0
    else:
        print("❌ SOME TESTS FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(run_dashboard_tests())
