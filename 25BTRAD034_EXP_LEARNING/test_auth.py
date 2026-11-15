import os
import sys
import json
import sqlite3
import subprocess
import time
import urllib.request
from werkzeug.security import check_password_hash
from app import app
import database

# Windows console encoding safeguard
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def run_auth_tests():
    print("==================================================")
    print("      CityOS Authentication & RBAC Test Suite     ")
    print("==================================================")
    all_passed = True

    test_user_email = "citizen_test@cityos.com"
    test_user_name = "Jane Citizen"
    test_user_pass = "securepass123"

    with app.app_context():
        db = database.get_db()
        # Clean up test user if previously exists
        db.execute("DELETE FROM users WHERE email = ?", (test_user_email,))
        db.commit()

    with app.test_client() as client:
        # TEST 1: Register a new user
        reg_response = client.post(
            "/register",
            data={
                "name": test_user_name,
                "email": test_user_email,
                "password": test_user_pass,
                "confirm_password": test_user_pass,
            },
            follow_redirects=True,
        )
        if reg_response.status_code == 200 and b"Registration successful" in reg_response.data:
            print("[PASS] [TEST 1] Registered new user successfully.")
        else:
            print(f"[FAIL] [TEST 1] Failed to register user. Status: {reg_response.status_code}")
            all_passed = False

        # TEST 2: Verify the user appears in the users table
        with app.app_context():
            db = database.get_db()
            user_row = db.execute("SELECT * FROM users WHERE email = ?", (test_user_email,)).fetchone()
            if user_row is not None and user_row["name"] == test_user_name and user_row["role"] == "user":
                print(f"[PASS] [TEST 2] User found in SQLite 'users' table (id={user_row['id']}, role={user_row['role']}).")
            else:
                print("[FAIL] [TEST 2] User not found in 'users' table or invalid role.")
                all_passed = False

            # TEST 3: Verify the password is securely hashed
            if user_row is not None:
                stored_hash = user_row["password"]
                is_not_plain = stored_hash != test_user_pass
                is_valid_hash = check_password_hash(stored_hash, test_user_pass)
                if is_not_plain and is_valid_hash:
                    print(f"[PASS] [TEST 3] Password confirmed securely hashed (Prefix: {stored_hash[:20]}...).")
                else:
                    print("[FAIL] [TEST 3] Password is not securely hashed.")
                    all_passed = False

        # TEST 4: Login using the new user's credentials
        login_response = client.post(
            "/login",
            data={
                "email": test_user_email,
                "password": test_user_pass,
            },
            follow_redirects=False,
        )
        if login_response.status_code == 302 and login_response.headers.get("Location") == "/dashboard":
            print("[PASS] [TEST 4] Logged in successfully; redirected to /dashboard.")
        else:
            print(f"[FAIL] [TEST 4] Login failed. Status: {login_response.status_code}, Location: {login_response.headers.get('Location')}")
            all_passed = False

        # TEST 5: Verify the session works
        with client.session_transaction() as sess:
            if sess.get("email") == test_user_email and sess.get("role") == "user" and sess.get("user_id"):
                print(f"[PASS] [TEST 5] Active session verified (user_id={sess['user_id']}, name='{sess['name']}', role='{sess['role']}').")
            else:
                print(f"[FAIL] [TEST 5] Session state invalid: {dict(sess)}")
                all_passed = False

        # TEST 6: Verify the user reaches /dashboard and receives confirmation
        dash_response = client.get("/dashboard")
        if dash_response.status_code == 200 and b"Welcome, Jane Citizen" in dash_response.data:
            print("[PASS] [TEST 6] Citizen reached /dashboard with active welcome banner.")
        else:
            print(f"[FAIL] [TEST 6] Citizen cannot reach /dashboard. Status: {dash_response.status_code}")
            all_passed = False

        # TEST 7: Logout successfully
        logout_response = client.get("/logout", follow_redirects=True)
        if logout_response.status_code == 200 and b"logged out successfully" in logout_response.data:
            with client.session_transaction() as sess:
                if "user_id" not in sess:
                    print("[PASS] [TEST 7] Logged out successfully; session cleared.")
                else:
                    print("[FAIL] [TEST 7] Session was not cleared after logout.")
                    all_passed = False
        else:
            print(f"[FAIL] [TEST 7] Logout request failed. Status: {logout_response.status_code}")
            all_passed = False

        # TEST 8: Login using admin credentials
        admin_login = client.post(
            "/login",
            data={
                "email": "admin@cityos.com",
                "password": "admin123",
            },
            follow_redirects=False,
        )
        if admin_login.status_code == 302 and admin_login.headers.get("Location") == "/admin":
            print("[PASS] [TEST 8] Admin logged in; redirected to /admin.")
        else:
            print(f"[FAIL] [TEST 8] Admin login redirect failed. Status: {admin_login.status_code}, Location: {admin_login.headers.get('Location')}")
            all_passed = False

        # TEST 9: Verify admin reaches /admin and receives confirmation
        admin_dash = client.get("/admin")
        if admin_dash.status_code == 200 and (b"Admin Dashboard" in admin_dash.data or b"CityOS Administration" in admin_dash.data):
            print("[PASS] [TEST 9] Admin reached /admin with 'CityOS Administration' / 'Admin Dashboard'.")
        else:
            print(f"[FAIL] [TEST 9] Admin cannot reach /admin. Status: {admin_dash.status_code}")
            all_passed = False

        # Clear session for role test
        client.get("/logout")

        # TEST 10: Verify normal user cannot access /admin
        # Log back in as normal user
        client.post(
            "/login",
            data={
                "email": test_user_email,
                "password": test_user_pass,
            },
        )
        forbidden_resp = client.get("/admin", follow_redirects=False)
        # Should return 403 or redirect away
        if forbidden_resp.status_code in (403, 302):
            print(f"[PASS] [TEST 10] Normal user was denied access to /admin (Status: {forbidden_resp.status_code}).")
        else:
            print(f"[FAIL] [TEST 10] Normal user accessed /admin or unexpected response. Status: {forbidden_resp.status_code}")
            all_passed = False

        # Clear session for unauthenticated test
        client.get("/logout")

        # TEST 11: Verify unauthenticated user cannot access /dashboard
        unauth_resp = client.get("/dashboard", follow_redirects=False)
        if unauth_resp.status_code == 302 and "/login" in unauth_resp.headers.get("Location", ""):
            print("[PASS] [TEST 11] Unauthenticated user blocked from /dashboard and redirected to /login.")
        else:
            print(f"[FAIL] [TEST 11] Unauthenticated user was not redirected to /login. Status: {unauth_resp.status_code}")
            all_passed = False

    # TEST 12: Verify Flask live startup
    try:
        proc = subprocess.Popen(
            [sys.executable, "app.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(1.5)
        res = urllib.request.urlopen("http://127.0.0.1:5000/api/health")
        data = json.loads(res.read().decode("utf-8"))
        proc.terminate()
        if data.get("status") == "online" and data.get("database", {}).get("status") == "connected":
            print("[PASS] [TEST 12] Flask live server starts successfully and /api/health responds OK.")
        else:
            print(f"[FAIL] [TEST 12] Live server returned unexpected payload: {data}")
            all_passed = False
    except Exception as e:
        print(f"[FAIL] [TEST 12] Live server check failed: {e}")
        all_passed = False

    print("==================================================")
    if all_passed:
        print("🎉 ALL 12 AUTHENTICATION & RBAC TESTS PASSED!")
        return 0
    else:
        print("❌ SOME TESTS FAILED.")
        return 1


if __name__ == "__main__":
    sys.exit(run_auth_tests())
