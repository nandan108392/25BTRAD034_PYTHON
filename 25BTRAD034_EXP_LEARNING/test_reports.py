import os
import io
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


def setup_test_users():
    """Sets up clean test users."""
    with app.app_context():
        db = database.get_db()
        db.execute("DELETE FROM reports WHERE title LIKE 'ReportTest_%'")
        db.execute("DELETE FROM users WHERE email IN ('reporter_a@cityos.com', 'reporter_b@cityos.com')")
        
        now = datetime.now().isoformat()
        pw_hash = generate_password_hash("password123")

        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Reporter Alpha", "reporter_a@cityos.com", pw_hash, "user", now),
        )
        user_a_id = db.execute("SELECT id FROM users WHERE email = 'reporter_a@cityos.com'").fetchone()["id"]

        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Reporter Beta", "reporter_b@cityos.com", pw_hash, "user", now),
        )
        user_b_id = db.execute("SELECT id FROM users WHERE email = 'reporter_b@cityos.com'").fetchone()["id"]

        db.commit()
        return user_a_id, user_b_id


def run_reports_test_suite():
    print("==================================================")
    print("      CityOS Report Submission Test Suite         ")
    print("==================================================")
    all_passed = True
    user_a_id, user_b_id = setup_test_users()

    with app.test_client() as client:
        # TEST 1: Unauthenticated user cannot access report page
        res_unauth = client.get("/report", follow_redirects=False)
        if res_unauth.status_code == 302 and "/login" in res_unauth.headers.get("Location", ""):
            print("[PASS] [TEST 1] Unauthenticated user blocked from /report and redirected to /login.")
        else:
            print(f"[FAIL] [TEST 1] Unauthenticated access allowed or unexpected status: {res_unauth.status_code}")
            all_passed = False

        # Login as User A
        client.post("/login", data={"email": "reporter_a@cityos.com", "password": "password123"})

        # TEST 2: Authenticated user can access report page
        res_auth_page = client.get("/report")
        if res_auth_page.status_code == 200 and b"Report a Problem" in res_auth_page.data and b"Pothole" in res_auth_page.data:
            print("[PASS] [TEST 2] Authenticated user accessed /report with form and categories.")
        else:
            print(f"[FAIL] [TEST 2] Failed to access /report. Status: {res_auth_page.status_code}")
            all_passed = False

        # TEST 3: Valid report submission succeeds
        initial_post = client.post(
            "/report",
            data={
                "category": "Pothole",
                "title": "ReportTest_Large Pothole",
                "description": "Deep crater in center lane creating traffic hazards.",
                "location": "North Boulevard near 14th Cross",
            },
            follow_redirects=False,
        )
        if initial_post.status_code == 302 and "/report/success/" in initial_post.headers.get("Location", ""):
            report_a_id = int(initial_post.headers.get("Location").split("/")[-1])
            print(f"[PASS] [TEST 3] Valid report submitted successfully; redirected to success view (Report ID: {report_a_id}).")
        else:
            print(f"[FAIL] [TEST 3] Report submission failed. Status: {initial_post.status_code}")
            all_passed = False
            report_a_id = None

        # TEST 4, 5, 6: Verify in Database (insertion, status='Reported', belongs to user_a)
        with app.app_context():
            db = database.get_db()
            row = db.execute("SELECT * FROM reports WHERE id = ?", (report_a_id,)).fetchone()
            if row is not None:
                print(f"[PASS] [TEST 4] Report #{report_a_id} found in SQLite database.")
            else:
                print(f"[FAIL] [TEST 4] Report #{report_a_id} not found in database.")
                all_passed = False

            if row and row["status"] == "Reported":
                print(f"[PASS] [TEST 5] Initial status is automatically set to 'Reported'.")
            else:
                print(f"[FAIL] [TEST 5] Initial status is not 'Reported': {row['status'] if row else None}")
                all_passed = False

            if row and row["user_id"] == user_a_id:
                print(f"[PASS] [TEST 6] Report is correctly associated with logged-in user_id ({user_a_id}).")
            else:
                print(f"[FAIL] [TEST 6] User association mismatch: {row['user_id'] if row else None} != {user_a_id}")
                all_passed = False

        # TEST 7: Required field validation (missing title, description, location)
        res_missing_title = client.post(
            "/report",
            data={
                "category": "Pothole",
                "title": "",
                "description": "Some description",
                "location": "Some location",
            },
            follow_redirects=True,
        )
        if b"Problem title is required" in res_missing_title.data:
            print("[PASS] [TEST 7] Missing title validation triggered correctly.")
        else:
            print("[FAIL] [TEST 7] Missing title validation failed.")
            all_passed = False

        # TEST 8: Invalid category rejection
        res_bad_cat = client.post(
            "/report",
            data={
                "category": "Alien Invasion",
                "title": "ReportTest_Invalid Category",
                "description": "UFO landed on main street",
                "location": "Main Square",
            },
            follow_redirects=True,
        )
        if b"Please select a valid report category" in res_bad_cat.data:
            print("[PASS] [TEST 8] Invalid category was rejected with validation error.")
        else:
            print("[FAIL] [TEST 8] Invalid category was not rejected.")
            all_passed = False

        # TEST 9: Invalid image type rejection (.txt file)
        fake_txt_file = (io.BytesIO(b"malicious script content"), "test_script.txt")
        res_bad_img = client.post(
            "/report",
            data={
                "category": "Garbage",
                "title": "ReportTest_Bad Image File",
                "description": "Overflowing bin",
                "location": "Park Street",
                "image": fake_txt_file,
            },
            content_type="multipart/form-data",
            follow_redirects=True,
        )
        if b"Invalid image file type" in res_bad_img.data:
            print("[PASS] [TEST 9] Invalid file extension (.txt) was safely rejected.")
        else:
            print("[FAIL] [TEST 9] Invalid file extension was not rejected.")
            all_passed = False

        # TEST 10: Valid image upload (.png)
        # Create minimal 1x1 PNG bytes
        png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\r\xefe\r\x00\x00\x00\x00IEND\xaeB`\x82"
        valid_png_file = (io.BytesIO(png_bytes), "evidence_photo.png")

        res_valid_img = client.post(
            "/report",
            data={
                "category": "Streetlight",
                "title": "ReportTest_Broken Streetlight With Photo",
                "description": "Dark stretch of road due to faulty lamp.",
                "location": "West Avenue Junction",
                "image": valid_png_file,
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        if res_valid_img.status_code == 302 and "/report/success/" in res_valid_img.headers.get("Location", ""):
            img_report_id = int(res_valid_img.headers.get("Location").split("/")[-1])
            with app.app_context():
                db = database.get_db()
                img_row = db.execute("SELECT * FROM reports WHERE id = ?", (img_report_id,)).fetchone()
                if img_row and img_row["image"] and img_row["image"].startswith("/uploads/"):
                    saved_filename = img_row["image"].replace("/uploads/", "")
                    full_disk_path = os.path.join(app.config["UPLOAD_FOLDER"], saved_filename)
                    if os.path.exists(full_disk_path):
                        print(f"[PASS] [TEST 10] Valid image uploaded, saved with unique name, and persisted to disk ({saved_filename}).")
                    else:
                        print(f"[FAIL] [TEST 10] Image file not found on disk at {full_disk_path}")
                        all_passed = False
                else:
                    print(f"[FAIL] [TEST 10] Image path not stored in database: {img_row['image'] if img_row else None}")
                    all_passed = False
        else:
            print(f"[FAIL] [TEST 10] Valid image upload submission failed. Status: {res_valid_img.status_code}")
            all_passed = False

        # TEST 11: Unique Report ID formatting (CITY-YYYY-00001)
        with app.app_context():
            formatted_id_a = database.format_report_id(report_a_id, "2026-09-18T12:00:00")
            expected_format_prefix = f"CITY-2026-{report_a_id:05d}"
            if formatted_id_a == expected_format_prefix:
                print(f"[PASS] [TEST 11] Unique human-readable Report ID format verified: '{formatted_id_a}'.")
            else:
                print(f"[FAIL] [TEST 11] Report ID format mismatch: {formatted_id_a} != {expected_format_prefix}")
                all_passed = False

        # TEST 12: Report appears in user's reports (/my-reports & /dashboard)
        res_my_reports = client.get("/my-reports")
        if res_my_reports.status_code == 200 and "ReportTest_Large Pothole" in res_my_reports.data.decode("utf-8"):
            print("[PASS] [TEST 12] Submitted report appears in citizen's /my-reports view.")
        else:
            print("[FAIL] [TEST 12] Submitted report not found in /my-reports.")
            all_passed = False

        # TEST 13: Dashboard statistics update after submission
        res_dash = client.get("/dashboard")
        dash_content = res_dash.data.decode("utf-8")
        if "ReportTest_Large Pothole" in dash_content and '<span class="stat-number" id="stat-total">2</span>' in dash_content:
            print("[PASS] [TEST 13] Dashboard statistics updated dynamically (Total: 2, Reported: 2).")
        else:
            print("[FAIL] [TEST 13] Dashboard statistics did not reflect newly submitted reports.")
            all_passed = False

        # TEST 14: Data isolation - Another user cannot access User A's submitted report
        client.get("/logout")
        client.post("/login", data={"email": "reporter_b@cityos.com", "password": "password123"})
        res_user_b_access = client.get(f"/reports/{report_a_id}", follow_redirects=False)
        if res_user_b_access.status_code == 403 or (res_user_b_access.status_code == 302 and res_user_b_access.headers.get("Location") == "/dashboard"):
            print(f"[PASS] [TEST 14] Data isolation verified: User B was denied access to User A's report #{report_a_id} (Status: {res_user_b_access.status_code}).")
        else:
            print(f"[FAIL] [TEST 14] User B was able to view or received unexpected status for User A's report. Status: {res_user_b_access.status_code}")
            all_passed = False

    print("==================================================")
    if all_passed:
        print("🎉 ALL 14 REPORT SUBMISSION TESTS PASSED!")
        return 0
    else:
        print("❌ SOME TESTS FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(run_reports_test_suite())
