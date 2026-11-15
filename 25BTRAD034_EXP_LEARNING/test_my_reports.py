import os
import io
import sys
import sqlite3
import subprocess
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
    """Sets up clean test users and historical reports with various statuses and timestamps."""
    with app.app_context():
        db = database.get_db()
        db.execute("DELETE FROM reports WHERE title LIKE 'Step6Test_%'")
        db.execute("DELETE FROM users WHERE email IN ('citizen_x@cityos.com', 'citizen_y@cityos.com', 'empty_citizen@cityos.com')")

        pw_hash = generate_password_hash("password123")

        # User X
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Citizen X", "citizen_x@cityos.com", pw_hash, "user", "2026-09-01T10:00:00"),
        )
        user_x_id = db.execute("SELECT id FROM users WHERE email = 'citizen_x@cityos.com'").fetchone()["id"]

        # User Y
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Citizen Y", "citizen_y@cityos.com", pw_hash, "user", "2026-09-01T10:00:00"),
        )
        user_y_id = db.execute("SELECT id FROM users WHERE email = 'citizen_y@cityos.com'").fetchone()["id"]

        # Empty User
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Empty Citizen", "empty_citizen@cityos.com", pw_hash, "user", "2026-09-01T10:00:00"),
        )
        empty_id = db.execute("SELECT id FROM users WHERE email = 'empty_citizen@cityos.com'").fetchone()["id"]

        # Reports for User X with specific timestamps to test sorting:
        # Report 1 (Oldest): 2026-09-10 - Status: Resolved, No Image
        db.execute(
            """
            INSERT INTO reports (user_id, category, title, description, location, image, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_x_id, "Pothole", "Step6Test_Old Pothole", "Fix required", "1st Street", None, "Resolved", "2026-09-10T08:00:00", "2026-09-12T14:00:00"),
        )
        rep1_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

        # Report 2 (Middle): 2026-09-14 - Status: In Progress, With Image
        db.execute(
            """
            INSERT INTO reports (user_id, category, title, description, location, image, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_x_id, "Streetlight", "Step6Test_Broken Lamp", "Dark intersection hazard", "Oak Avenue", "/uploads/test_lamp.png", "In Progress", "2026-09-14T11:30:00", "2026-09-15T09:00:00"),
        )
        rep2_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

        # Report 3 (Newest): 2026-09-18 - Status: Reported, No Image
        db.execute(
            """
            INSERT INTO reports (user_id, category, title, description, location, image, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_x_id, "Garbage", "Step6Test_New Garbage", "Overflowing dumpster", "Park Road", None, "Reported", "2026-09-18T16:45:00", "2026-09-18T16:45:00"),
        )
        rep3_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

        # Report 4 (Rejected): 2026-09-16 - Status: Rejected
        db.execute(
            """
            INSERT INTO reports (user_id, category, title, description, location, image, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_x_id, "Other", "Step6Test_Rejected Report", "Private property issue", "Private Way", None, "Rejected", "2026-09-16T12:00:00", "2026-09-17T10:00:00"),
        )
        rep4_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

        # Report for User Y (to test ownership / 403):
        db.execute(
            """
            INSERT INTO reports (user_id, category, title, description, location, image, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_y_id, "Drainage", "Step6Test_UserY Drain", "Blocked storm drain", "East Avenue", None, "Reported", "2026-09-18T09:00:00", "2026-09-18T09:00:00"),
        )
        rep_y_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

        db.commit()
        return user_x_id, user_y_id, empty_id, rep1_id, rep2_id, rep3_id, rep4_id, rep_y_id


def run_tests():
    print("==================================================")
    print("      CityOS Step 6: My Reports & Tracking        ")
    print("==================================================")
    all_passed = True
    user_x_id, user_y_id, empty_id, rep1_id, rep2_id, rep3_id, rep4_id, rep_y_id = setup_test_data()

    with app.test_client() as client:
        # TEST 1: Unauthenticated user cannot access /my-reports
        res_unauth = client.get("/my-reports", follow_redirects=False)
        if res_unauth.status_code == 302 and "/login" in res_unauth.headers.get("Location", ""):
            print("[PASS] [TEST 1] Unauthenticated user blocked from /my-reports and redirected to /login.")
        else:
            print(f"[FAIL] [TEST 1] Unauthenticated access check failed: {res_unauth.status_code}")
            all_passed = False

        # Login as User X
        client.post("/login", data={"email": "citizen_x@cityos.com", "password": "password123"})

        # TEST 2: Authenticated citizen can access /my-reports
        res_my_rep = client.get("/my-reports")
        if res_my_rep.status_code == 200 and b"My Submitted Reports" in res_my_rep.data:
            print("[PASS] [TEST 2] Authenticated citizen successfully accessed /my-reports (HTTP 200).")
        else:
            print(f"[FAIL] [TEST 2] Authenticated access to /my-reports failed: {res_my_rep.status_code}")
            all_passed = False

        # TEST 3: Only logged-in user's reports are displayed
        content_my_rep = res_my_rep.data.decode("utf-8")
        has_x_reports = ("Step6Test_Old Pothole" in content_my_rep and 
                         "Step6Test_Broken Lamp" in content_my_rep and 
                         "Step6Test_New Garbage" in content_my_rep)
        has_y_report = "Step6Test_UserY Drain" in content_my_rep
        if has_x_reports and not has_y_report:
            print("[PASS] [TEST 3] Data isolation verified: Only User X's reports are displayed, User Y's reports are excluded.")
        else:
            print(f"[FAIL] [TEST 3] Data isolation failed in /my-reports. has_x={has_x_reports}, has_y={has_y_report}")
            all_passed = False

        # TEST 4: Reports are sorted newest first
        # Order should be: rep3 (Sep 18), rep4 (Sep 16), rep2 (Sep 14), rep1 (Sep 10)
        pos_rep3 = content_my_rep.find("Step6Test_New Garbage")
        pos_rep4 = content_my_rep.find("Step6Test_Rejected Report")
        pos_rep2 = content_my_rep.find("Step6Test_Broken Lamp")
        pos_rep1 = content_my_rep.find("Step6Test_Old Pothole")
        if pos_rep3 < pos_rep4 < pos_rep2 < pos_rep1 and all(p != -1 for p in [pos_rep1, pos_rep2, pos_rep3, pos_rep4]):
            print("[PASS] [TEST 4] Reports are correctly sorted with newest submissions first.")
        else:
            print(f"[FAIL] [TEST 4] Sorting order incorrect: pos3={pos_rep3}, pos4={pos_rep4}, pos2={pos_rep2}, pos1={pos_rep1}")
            all_passed = False

        # TEST 5: Empty state works
        client.get("/logout")
        client.post("/login", data={"email": "empty_citizen@cityos.com", "password": "password123"})
        res_empty = client.get("/my-reports")
        content_empty = res_empty.data.decode("utf-8")
        if "You haven't submitted any reports yet." in content_empty and "Report a Problem" in content_empty:
            print("[PASS] [TEST 5] Empty state works correctly with descriptive message and 'Report a Problem' button.")
        else:
            print("[FAIL] [TEST 5] Empty state failed to render properly.")
            all_passed = False

        # Login back as User X
        client.get("/logout")
        client.post("/login", data={"email": "citizen_x@cityos.com", "password": "password123"})

        # TEST 6: Citizen can open their own report details
        res_detail = client.get(f"/report/{rep2_id}")
        if res_detail.status_code == 200 and b"Step6Test_Broken Lamp" in res_detail.data:
            print(f"[PASS] [TEST 6] Citizen successfully opened own report details /report/{rep2_id} (HTTP 200).")
        else:
            print(f"[FAIL] [TEST 6] Could not open report details: {res_detail.status_code}")
            all_passed = False

        # TEST 7: Citizen cannot open another user's report (returns HTTP 403)
        res_forbidden = client.get(f"/report/{rep_y_id}")
        if res_forbidden.status_code == 403:
            print(f"[PASS] [TEST 7] Unauthorized access to another user's report returned HTTP 403 Access Denied.")
        else:
            print(f"[FAIL] [TEST 7] Expected HTTP 403 but got {res_forbidden.status_code}")
            all_passed = False

        # TEST 8: Non-existent report returns HTTP 404
        res_404 = client.get("/report/999999")
        if res_404.status_code == 404:
            print("[PASS] [TEST 8] Non-existent report returned HTTP 404 Not Found.")
        else:
            print(f"[FAIL] [TEST 8] Expected HTTP 404 but got {res_404.status_code}")
            all_passed = False

        # TEST 9: Report details display correct information
        content_rep2 = res_detail.data.decode("utf-8")
        formatted_id_2 = database.format_report_id(rep2_id, "2026-09-14T11:30:00")
        has_meta = (formatted_id_2 in content_rep2 and 
                    "Streetlight" in content_rep2 and 
                    "Dark intersection hazard" in content_rep2 and 
                    "Oak Avenue" in content_rep2 and 
                    "2026-09-14" in content_rep2 and 
                    "2026-09-15" in content_rep2)
        if has_meta:
            print("[PASS] [TEST 9] Report details display correct Category, Title, Description, Location, and Timestamps.")
        else:
            print(f"[FAIL] [TEST 9] Report metadata mismatch in details view.")
            all_passed = False

        # TEST 10: Current status is displayed correctly
        if "In Progress" in content_rep2 and "badge-in-progress" in content_rep2:
            print("[PASS] [TEST 10] Current report status ('In Progress') is displayed with proper status badge.")
        else:
            print("[FAIL] [TEST 10] Current status display failed.")
            all_passed = False

        # TEST 11: Status tracker displays correctly (completed vs active vs upcoming & rejected)
        # In rep2 ("In Progress"): Reported=completed, Under Review=completed, In Progress=active, Resolved=upcoming
        has_tracker_classes = ("step-completed" in content_rep2 and 
                               "step-active" in content_rep2 and 
                               "step-upcoming" in content_rep2)
        
        # Test rejected report tracker (rep4)
        res_rejected = client.get(f"/report/{rep4_id}")
        content_rej = res_rejected.data.decode("utf-8")
        has_rejected_box = "Report Rejected" in content_rej and "rejected-state-card" in content_rej

        if has_tracker_classes and has_rejected_box:
            print("[PASS] [TEST 11] Status tracker renders progression stages and dedicated rejected state correctly.")
        else:
            print(f"[FAIL] [TEST 11] Status tracker mismatch. tracker_classes={has_tracker_classes}, rejected_box={has_rejected_box}")
            all_passed = False

        # TEST 12: Uploaded image is displayed when present
        if '<img src="/uploads/test_lamp.png"' in content_rep2:
            print("[PASS] [TEST 12] Uploaded image is displayed in report details.")
        else:
            print("[FAIL] [TEST 12] Uploaded image not displayed.")
            all_passed = False

        # TEST 13: No-image state works
        res_rep1 = client.get(f"/report/{rep1_id}")
        content_rep1 = res_rep1.data.decode("utf-8")
        if "No image uploaded." in content_rep1:
            print("[PASS] [TEST 13] Reports without an image display 'No image uploaded.' placeholder.")
        else:
            print("[FAIL] [TEST 13] No-image state failed.")
            all_passed = False

        # TEST 14: Dashboard report links work
        res_dash = client.get("/dashboard")
        dash_content = res_dash.data.decode("utf-8")
        if f"/report/{rep3_id}" in dash_content or f"/reports/{rep3_id}" in dash_content:
            print("[PASS] [TEST 14] Dashboard recent reports link directly to report details.")
        else:
            print("[FAIL] [TEST 14] Dashboard links to report details missing.")
            all_passed = False

    # TEST 15: Existing authentication tests still pass
    auth_proc = subprocess.run(
        [sys.executable, "test_auth.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if auth_proc.returncode == 0:
        print("[PASS] [TEST 15] Existing authentication test suite passes completely.")
    else:
        print(f"[FAIL] [TEST 15] test_auth.py failed:\n{auth_proc.stdout}\n{auth_proc.stderr}")
        all_passed = False

    # TEST 16: Existing report submission tests still pass
    reports_proc = subprocess.run(
        [sys.executable, "test_reports.py"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if reports_proc.returncode == 0:
        print("[PASS] [TEST 16] Existing report submission test suite passes completely.")
    else:
        print(f"[FAIL] [TEST 16] test_reports.py failed:\n{reports_proc.stdout}\n{reports_proc.stderr}")
        all_passed = False

    print("==================================================")
    if all_passed:
        print("🎉 ALL 16 MY REPORTS & STATUS TRACKING TESTS PASSED!")
        return 0
    else:
        print("❌ SOME TESTS FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
