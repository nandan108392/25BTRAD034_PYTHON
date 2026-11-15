import os
import sqlite3
import sys
from werkzeug.security import check_password_hash
from app import app
import database

# Ensure stdout supports unicode/utf-8 safely on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def run_tests():
    print("========================================")
    print("      CityOS Database Layer Tests       ")
    print("========================================")
    all_passed = True

    # Test 1: Verify database file creation
    db_path = app.config.get("DATABASE")
    print(f"Checking DB Path: {db_path}")
    if os.path.exists(db_path):
        print("[PASS] [TEST 1] Database file exists.")
    else:
        print("[FAIL] [TEST 1] Database file does NOT exist.")
        all_passed = False

    # Test 2: Check tables exist
    with app.app_context():
        db = database.get_db()
        cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row["name"] for row in cursor.fetchall()]

        required_tables = ["users", "reports"]
        for tbl in required_tables:
            if tbl in tables:
                print(f"[PASS] [TEST 2] Table '{tbl}' exists.")
            else:
                print(f"[FAIL] [TEST 2] Table '{tbl}' is missing.")
                all_passed = False

        # Verify users columns
        user_cols = [row["name"] for row in db.execute("PRAGMA table_info(users);").fetchall()]
        expected_user_cols = ["id", "name", "email", "password", "role", "created_at"]
        if all(col in user_cols for col in expected_user_cols):
            print(f"[PASS] [TEST 2.1] Users table schema verified: {user_cols}")
        else:
            print(f"[FAIL] [TEST 2.1] Users table missing columns: {user_cols}")
            all_passed = False

        # Verify reports columns
        report_cols = [row["name"] for row in db.execute("PRAGMA table_info(reports);").fetchall()]
        expected_report_cols = [
            "id",
            "user_id",
            "category",
            "title",
            "description",
            "location",
            "image",
            "status",
            "created_at",
            "updated_at",
        ]
        if all(col in report_cols for col in expected_report_cols):
            print(f"[PASS] [TEST 2.2] Reports table schema verified: {report_cols}")
        else:
            print(f"[FAIL] [TEST 2.2] Reports table missing columns: {report_cols}")
            all_passed = False

        # Test 3: Check admin account exists
        admin = db.execute("SELECT * FROM users WHERE email = ?", ("admin@cityos.com",)).fetchone()
        if admin is not None:
            print(
                f"[PASS] [TEST 3] Admin account found: id={admin['id']}, email={admin['email']}, role={admin['role']}"
            )
        else:
            print("[FAIL] [TEST 3] Admin account 'admin@cityos.com' not found.")
            all_passed = False

        # Test 4: Check password is hashed (not plain text)
        if admin is not None:
            raw_stored_pw = admin["password"]
            is_not_plain = raw_stored_pw != "admin123"
            is_valid_hash = check_password_hash(raw_stored_pw, "admin123")

            if is_not_plain and is_valid_hash:
                print(
                    f"[PASS] [TEST 4] Admin password is securely hashed with Werkzeug (Hash: {raw_stored_pw[:25]}...)."
                )
            else:
                print("[FAIL] [TEST 4] Admin password hash verification failed.")
                all_passed = False

    # Test 5: Flask client endpoints
    with app.test_client() as client:
        res_index = client.get("/")
        res_health = client.get("/api/health")

        if res_index.status_code == 200:
            print("[PASS] [TEST 5.1] GET / returned HTTP 200.")
        else:
            print(f"[FAIL] [TEST 5.1] GET / returned {res_index.status_code}")
            all_passed = False

        if res_health.status_code == 200:
            health_data = res_health.get_json()
            if health_data.get("database", {}).get("status") == "connected":
                print(
                    f"[PASS] [TEST 5.2] GET /api/health returned HTTP 200 with DB status: {health_data['database']}"
                )
            else:
                print(f"[FAIL] [TEST 5.2] GET /api/health DB not connected: {health_data}")
                all_passed = False
        else:
            print(f"[FAIL] [TEST 5.2] GET /api/health returned {res_health.status_code}")
            all_passed = False

    print("========================================")
    if all_passed:
        print("ALL DATABASE & FLASK TESTS PASSED!")
        return 0
    else:
        print("SOME TESTS FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(run_tests())
