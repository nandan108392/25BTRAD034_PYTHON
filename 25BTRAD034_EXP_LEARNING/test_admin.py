import os
import sys
import sqlite3
import subprocess
import time
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


def setup_admin_test_data():
    """Sets up clean test data for admin dashboard tests."""
    with app.app_context():
        db = database.get_db()
        db.execute("DELETE FROM reports WHERE title LIKE 'AdminTest_%'")
        db.execute("DELETE FROM users WHERE email IN ('citizen_admin_test@cityos.com')")

        pw_hash = generate_password_hash("password123")
        now = datetime.now().isoformat()

        # Create Citizen User
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Citizen Tester", "citizen_admin_test@cityos.com", pw_hash, "user", now),
        )
        citizen_id = db.execute("SELECT id FROM users WHERE email = 'citizen_admin_test@cityos.com'").fetchone()["id"]

        # Insert multiple reports with various categories and statuses:
        # 1. Pothole, Reported, Location: "Market Square", No image
        db.execute(
            """
            INSERT INTO reports (user_id, category, title, description, location, image, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (citizen_id, "Pothole", "AdminTest_Dangerous Road Pothole", "Deep cavity on asphalt", "Market Square", None, "Reported", "2026-09-10T10:00:00", "2026-09-10T10:00:00"),
        )
        rep_pothole_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

        # 2. Streetlight, In Progress, Location: "North Highway", With image
        db.execute(
            """
            INSERT INTO reports (user_id, category, title, description, location, image, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (citizen_id, "Streetlight", "AdminTest_Dark Highway Stretch", "Hazardous night lamp failure", "North Highway", "/uploads/lamp_test.png", "In Progress", "2026-09-12T12:00:00", "2026-09-12T12:00:00"),
        )
        rep_lamp_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

        # 3. Garbage, Under Review, Location: "Central Park", No image
        db.execute(
            """
            INSERT INTO reports (user_id, category, title, description, location, image, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (citizen_id, "Garbage", "AdminTest_Overflowing Waste Bin", "Litter on grass", "Central Park", None, "Under Review", "2026-09-14T14:00:00", "2026-09-14T14:00:00"),
        )
        rep_garbage_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

        # 4. Water Leakage, Resolved, Location: "South Street", No image
        db.execute(
            """
            INSERT INTO reports (user_id, category, title, description, location, image, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (citizen_id, "Water Leakage", "AdminTest_Pipe Burst", "Clean water flooding lane", "South Street", None, "Resolved", "2026-09-16T16:00:00", "2026-09-16T16:00:00"),
        )
        rep_water_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

        # 5. Other, Rejected, Location: "Private Lane", No image
        db.execute(
            """
            INSERT INTO reports (user_id, category, title, description, location, image, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (citizen_id, "Other", "AdminTest_Private Lawn Tree", "Tree branch over fence", "Private Lane", None, "Rejected", "2026-09-18T08:00:00", "2026-09-18T08:00:00"),
        )
        rep_rejected_id = db.execute("SELECT last_insert_rowid() as id").fetchone()["id"]

        db.commit()
        return citizen_id, rep_pothole_id, rep_lamp_id, rep_garbage_id, rep_water_id, rep_rejected_id


def run_admin_tests():
    print("==================================================")
    print("      CityOS Step 7: Admin Dashboard Tests        ")
    print("==================================================")
    all_passed = True
    citizen_id, rep_pothole_id, rep_lamp_id, rep_garbage_id, rep_water_id, rep_rejected_id = setup_admin_test_data()

    with app.test_client() as client:
        # TEST 1: Unauthenticated user cannot access /admin
        res_unauth = client.get("/admin", follow_redirects=False)
        if res_unauth.status_code == 302 and "/login" in res_unauth.headers.get("Location", ""):
            print("[PASS] [TEST 1] Unauthenticated user blocked from /admin and redirected to /login.")
        else:
            print(f"[FAIL] [TEST 1] Unauthenticated access allowed or unexpected status: {res_unauth.status_code}")
            all_passed = False

        # TEST 2: Normal citizen cannot access /admin
        client.post("/login", data={"email": "citizen_admin_test@cityos.com", "password": "password123"})
        res_citizen_admin = client.get("/admin", follow_redirects=False)
        if res_citizen_admin.status_code in (403, 302):
            print(f"[PASS] [TEST 2] Normal citizen blocked from /admin (Status: {res_citizen_admin.status_code}).")
        else:
            print(f"[FAIL] [TEST 2] Normal citizen accessed /admin: {res_citizen_admin.status_code}")
            all_passed = False

        # Logout citizen and login as Admin
        client.get("/logout")
        client.post("/login", data={"email": "admin@cityos.com", "password": "admin123"})

        # TEST 3: Admin can access /admin
        res_admin = client.get("/admin")
        if res_admin.status_code == 200 and b"CityOS Administration" in res_admin.data:
            print("[PASS] [TEST 3] Admin successfully accessed /admin (HTTP 200).")
        else:
            print(f"[FAIL] [TEST 3] Admin failed to access /admin: {res_admin.status_code}")
            all_passed = False

        # TEST 4: Admin statistics match database
        content_admin = res_admin.data.decode("utf-8")
        with app.app_context():
            db = database.get_db()
            total_db = db.execute("SELECT COUNT(*) as count FROM reports").fetchone()["count"]
            reported_db = db.execute("SELECT COUNT(*) as count FROM reports WHERE status = 'Reported'").fetchone()["count"]
            under_review_db = db.execute("SELECT COUNT(*) as count FROM reports WHERE status = 'Under Review'").fetchone()["count"]
            progress_db = db.execute("SELECT COUNT(*) as count FROM reports WHERE status = 'In Progress'").fetchone()["count"]
            resolved_db = db.execute("SELECT COUNT(*) as count FROM reports WHERE status = 'Resolved'").fetchone()["count"]
            rejected_db = db.execute("SELECT COUNT(*) as count FROM reports WHERE status = 'Rejected'").fetchone()["count"]

        has_stats = (
            f'id="stat-total">{total_db}</span>' in content_admin and
            f'id="stat-reported">{reported_db}</span>' in content_admin and
            f'id="stat-under-review">{under_review_db}</span>' in content_admin and
            f'id="stat-in-progress">{progress_db}</span>' in content_admin and
            f'id="stat-resolved">{resolved_db}</span>' in content_admin and
            f'id="stat-rejected">{rejected_db}</span>' in content_admin
        )
        if has_stats:
            print(f"[PASS] [TEST 4] Admin system statistics match database (Total={total_db}, Reported={reported_db}, Review={under_review_db}, Progress={progress_db}, Resolved={resolved_db}, Rejected={rejected_db}).")
        else:
            print("[FAIL] [TEST 4] Admin statistics do not match database.")
            all_passed = False

        # TEST 5: Admin can view all reports
        has_all_reports = (
            "AdminTest_Dangerous Road Pothole" in content_admin and
            "AdminTest_Dark Highway Stretch" in content_admin and
            "AdminTest_Overflowing Waste Bin" in content_admin and
            "AdminTest_Pipe Burst" in content_admin and
            "AdminTest_Private Lawn Tree" in content_admin
        )
        if has_all_reports:
            print("[PASS] [TEST 5] Admin can view all reports from all citizens in management registry.")
        else:
            print("[FAIL] [TEST 5] Some citizen reports were missing from admin view.")
            all_passed = False

        # TEST 6: Search by Report ID
        res_search_id = client.get(f"/admin?q={rep_pothole_id}")
        content_s_id = res_search_id.data.decode("utf-8")
        if "AdminTest_Dangerous Road Pothole" in content_s_id and "AdminTest_Dark Highway Stretch" not in content_s_id:
            print(f"[PASS] [TEST 6] Search by Report ID ({rep_pothole_id}) works accurately.")
        else:
            print("[FAIL] [TEST 6] Search by Report ID failed.")
            all_passed = False

        # TEST 7: Search by Title
        res_search_title = client.get("/admin?q=Pipe+Burst")
        content_s_title = res_search_title.data.decode("utf-8")
        if "AdminTest_Pipe Burst" in content_s_title and "AdminTest_Dangerous Road Pothole" not in content_s_title:
            print("[PASS] [TEST 7] Search by Title ('Pipe Burst') works accurately.")
        else:
            print("[FAIL] [TEST 7] Search by Title failed.")
            all_passed = False

        # TEST 8: Search by Location
        res_search_loc = client.get("/admin?q=Central+Park")
        content_s_loc = res_search_loc.data.decode("utf-8")
        if "AdminTest_Overflowing Waste Bin" in content_s_loc and "AdminTest_Pipe Burst" not in content_s_loc:
            print("[PASS] [TEST 8] Search by Location ('Central Park') works accurately.")
        else:
            print("[FAIL] [TEST 8] Search by Location failed.")
            all_passed = False

        # TEST 9: Category Filter
        res_filter_cat = client.get("/admin?category=Streetlight")
        content_f_cat = res_filter_cat.data.decode("utf-8")
        if "AdminTest_Dark Highway Stretch" in content_f_cat and "AdminTest_Dangerous Road Pothole" not in content_f_cat:
            print("[PASS] [TEST 9] Category Filter ('Streetlight') filtered reports accurately.")
        else:
            print("[FAIL] [TEST 9] Category Filter failed.")
            all_passed = False

        # TEST 10: Status Filter
        res_filter_st = client.get("/admin?status=Under+Review")
        content_f_st = res_filter_st.data.decode("utf-8")
        if "AdminTest_Overflowing Waste Bin" in content_f_st and "AdminTest_Pipe Burst" not in content_f_st:
            print("[PASS] [TEST 10] Status Filter ('Under Review') filtered reports accurately.")
        else:
            print("[FAIL] [TEST 10] Status Filter failed.")
            all_passed = False

        # TEST 11: Combined search + filters
        res_combo = client.get("/admin?q=Highway&category=Streetlight&status=In+Progress")
        content_combo = res_combo.data.decode("utf-8")
        if "AdminTest_Dark Highway Stretch" in content_combo and "AdminTest_Dangerous Road Pothole" not in content_combo:
            print("[PASS] [TEST 11] Combined search + category + status filters work in tandem.")
        else:
            print("[FAIL] [TEST 11] Combined search and filter failed.")
            all_passed = False

        # TEST 12: Admin can open report details
        res_admin_det = client.get(f"/admin/report/{rep_lamp_id}")
        if res_admin_det.status_code == 200 and b"AdminTest_Dark Highway Stretch" in res_admin_det.data:
            print(f"[PASS] [TEST 12] Admin successfully opened /admin/report/{rep_lamp_id} (HTTP 200).")
        else:
            print(f"[FAIL] [TEST 12] Admin failed to open report details: {res_admin_det.status_code}")
            all_passed = False

        # TEST 13: Admin can see citizen name and email
        content_admin_det = res_admin_det.data.decode("utf-8")
        if "Citizen Tester" in content_admin_det and "citizen_admin_test@cityos.com" in content_admin_det:
            print("[PASS] [TEST 13] Admin can see submitter Citizen Name ('Citizen Tester') and Email ('citizen_admin_test@cityos.com').")
        else:
            print("[FAIL] [TEST 13] Citizen information missing on admin report details.")
            all_passed = False

        # TEST 14: Admin can see uploaded image
        if '<img src="/uploads/lamp_test.png"' in content_admin_det:
            print("[PASS] [TEST 14] Admin can see uploaded evidence photo in report inspection view.")
        else:
            print("[FAIL] [TEST 14] Uploaded photo missing on admin report details.")
            all_passed = False

        # TEST 15 & 16: Admin can change report status & updated_at changes
        with app.app_context():
            db = database.get_db()
            old_row = db.execute("SELECT status, updated_at FROM reports WHERE id = ?", (rep_pothole_id,)).fetchone()
            old_status = old_row["status"]
            old_updated_at = old_row["updated_at"]

        # Sleep briefly to ensure updated_at timestamp changes
        time.sleep(0.05)

        res_update_status = client.post(
            f"/admin/report/{rep_pothole_id}/status",
            data={"status": "In Progress"},
            follow_redirects=True,
        )
        if res_update_status.status_code == 200 and b"Report status updated to" in res_update_status.data and b"In Progress" in res_update_status.data:
            print(f"[PASS] [TEST 15] Admin updated report #{rep_pothole_id} status from '{old_status}' to 'In Progress'.")
        else:
            print(f"[FAIL] [TEST 15] Failed to update report status: {res_update_status.status_code}")
            all_passed = False

        with app.app_context():
            db = database.get_db()
            new_row = db.execute("SELECT status, updated_at FROM reports WHERE id = ?", (rep_pothole_id,)).fetchone()
            if new_row["status"] == "In Progress" and new_row["updated_at"] > old_updated_at:
                print(f"[PASS] [TEST 16] Database verified: status='In Progress' and updated_at refreshed ({new_row['updated_at']}).")
            else:
                print(f"[FAIL] [TEST 16] Status or updated_at was not properly updated in DB: {dict(new_row)}")
                all_passed = False

        # TEST 17: Citizen sees updated status in their views
        client.get("/logout")
        client.post("/login", data={"email": "citizen_admin_test@cityos.com", "password": "password123"})
        res_cit_view = client.get(f"/report/{rep_pothole_id}")
        if "In Progress" in res_cit_view.data.decode("utf-8") and "badge-in-progress" in res_cit_view.data.decode("utf-8"):
            print(f"[PASS] [TEST 17] Citizen immediately sees updated status ('In Progress') on their report details.")
        else:
            print("[FAIL] [TEST 17] Citizen did not see updated status.")
            all_passed = False

        # TEST 18: Normal citizen cannot change report status
        res_cit_post_status = client.post(
            f"/admin/report/{rep_pothole_id}/status",
            data={"status": "Resolved"},
            follow_redirects=False,
        )
        if res_cit_post_status.status_code == 403:
            print("[PASS] [TEST 18] Normal citizen was blocked from updating report status (HTTP 403).")
        else:
            print(f"[FAIL] [TEST 18] Normal citizen was able to POST status update: {res_cit_post_status.status_code}")
            all_passed = False

        # TEST 19: Normal citizen cannot access admin report details
        res_cit_admin_det = client.get(f"/admin/report/{rep_pothole_id}", follow_redirects=False)
        if res_cit_admin_det.status_code == 403:
            print("[PASS] [TEST 19] Normal citizen was blocked from accessing /admin/report/<id> (HTTP 403).")
        else:
            print(f"[FAIL] [TEST 19] Normal citizen accessed /admin/report/<id>: {res_cit_admin_det.status_code}")
            all_passed = False

        # Login back as Admin for 404 test
        client.get("/logout")
        client.post("/login", data={"email": "admin@cityos.com", "password": "admin123"})

        # TEST 20: Non-existent admin report returns 404
        res_admin_404 = client.get("/admin/report/999999")
        if res_admin_404.status_code == 404:
            print("[PASS] [TEST 20] Non-existent report returned HTTP 404 Not Found.")
        else:
            print(f"[FAIL] [TEST 20] Expected 404 but got {res_admin_404.status_code}")
            all_passed = False

    # TEST 21: Existing auth tests pass
    auth_proc = subprocess.run([sys.executable, "test_auth.py"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if auth_proc.returncode == 0:
        print("[PASS] [TEST 21] test_auth.py regression tests passed.")
    else:
        print(f"[FAIL] [TEST 21] test_auth.py failed:\n{auth_proc.stdout}\n{auth_proc.stderr}")
        all_passed = False

    # TEST 22: Existing report submission tests pass
    reports_proc = subprocess.run([sys.executable, "test_reports.py"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if reports_proc.returncode == 0:
        print("[PASS] [TEST 22] test_reports.py regression tests passed.")
    else:
        print(f"[FAIL] [TEST 22] test_reports.py failed:\n{reports_proc.stdout}\n{reports_proc.stderr}")
        all_passed = False

    # TEST 23: Existing citizen dashboard tests pass
    dash_proc = subprocess.run([sys.executable, "test_citizen_dashboard.py"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if dash_proc.returncode == 0:
        print("[PASS] [TEST 23] test_citizen_dashboard.py regression tests passed.")
    else:
        print(f"[FAIL] [TEST 23] test_citizen_dashboard.py failed:\n{dash_proc.stdout}\n{dash_proc.stderr}")
        all_passed = False

    # TEST 24: Existing My Reports tests pass
    my_rep_proc = subprocess.run([sys.executable, "test_my_reports.py"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    if my_rep_proc.returncode == 0:
        print("[PASS] [TEST 24] test_my_reports.py regression tests passed.")
    else:
        print(f"[FAIL] [TEST 24] test_my_reports.py failed:\n{my_rep_proc.stdout}\n{my_rep_proc.stderr}")
        all_passed = False

    print("==================================================")
    if all_passed:
        print("🎉 ALL 24 ADMIN DASHBOARD & MANAGEMENT TESTS PASSED!")
        return 0
    else:
        print("❌ SOME TESTS FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(run_admin_tests())
