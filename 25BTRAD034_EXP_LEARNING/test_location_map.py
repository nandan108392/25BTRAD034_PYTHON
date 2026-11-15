import os
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


def setup_map_test_data():
    """Sets up clean test data for location and city map tests."""
    with app.app_context():
        db = database.get_db()
        db.execute("DELETE FROM reports WHERE title LIKE 'MapTest_%'")
        db.execute("DELETE FROM users WHERE email IN ('citizen_map@cityos.com')")

        pw_hash = generate_password_hash("password123")
        now = datetime.now().isoformat()

        # Create Citizen User
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Map Citizen", "citizen_map@cityos.com", pw_hash, "user", now),
        )
        citizen_id = db.execute("SELECT id FROM users WHERE email = 'citizen_map@cityos.com'").fetchone()["id"]

        # Insert multiple reports with and without coordinates
        reports_data = [
            (citizen_id, "Road", "MapTest_Central Pothole", "Pothole crater on main road", "MG Road Central", "Reported", "Pothole", "HIGH", 12.9716, 77.5946, "Near Metro Station Gate 2", now, now),
            (citizen_id, "Water", "MapTest_Water Leak", "Major pipe leak flooding street", "Indiranagar 100ft Rd", "In Progress", "Water Leakage", "HIGH", 12.9784, 77.6408, "Opposite Coffee Shop", now, now),
            (citizen_id, "Electricity", "MapTest_Broken Light", "Streetlight not working", "Koramangala 4th Block", "Under Review", "Broken Streetlight", "MEDIUM", 12.9352, 77.6245, "Near Park Corner", now, now),
            (citizen_id, "Waste", "MapTest_Garbage Dump", "Uncollected garbage pile", "Whitefield Main Rd", "Resolved", "Garbage Dumping", "LOW", 12.9698, 77.7499, "Behind Bus Stop", now, now),
            (citizen_id, "Traffic", "MapTest_No Location Report", "Traffic jam at junction", "Silk Board Junction", "Reported", "Traffic Congestion", "MEDIUM", None, None, None, now, now),
        ]

        for r in reports_data:
            db.execute(
                """
                INSERT INTO reports (user_id, category, title, description, location, status, issue_type, priority, latitude, longitude, location_description, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                r,
            )

        db.commit()
        return citizen_id


def run_location_map_tests():
    print("==================================================")
    print("       CityOS Step 9: Location & City Map         ")
    print("==================================================")
    all_passed = True
    citizen_id = setup_map_test_data()

    with app.test_client() as client:
        # -------------------------------------------------------------
        # 1. CITIZEN REPORT SUBMISSION WITH/WITHOUT LOCATION
        # -------------------------------------------------------------

        # Login as citizen
        client.post("/login", data={"email": "citizen_map@cityos.com", "password": "password123"})

        # TEST 1: Report submission without location coordinates succeeds
        res_no_geo = client.post(
            "/report",
            data={
                "category": "Road",
                "title": "MapTest_Report Without Coordinates",
                "description": "Pothole without GPS",
                "location": "Residency Road",
                "latitude": "",
                "longitude": "",
                "location_description": "Near school",
            },
            follow_redirects=False,
        )
        if res_no_geo.status_code == 302 and "/report/success/" in res_no_geo.headers.get("Location", ""):
            rep_no_geo_id = int(res_no_geo.headers.get("Location").split("/")[-1])
            print(f"[PASS] [TEST 1] Report submitted without coordinates succeeded (Report #{rep_no_geo_id}).")
        else:
            print(f"[FAIL] [TEST 1] Report submission without coordinates failed: {res_no_geo.status_code}")
            all_passed = False
            rep_no_geo_id = None

        # TEST 2: Report submission with valid location coordinates succeeds
        res_geo = client.post(
            "/report",
            data={
                "category": "Road",
                "title": "MapTest_Report With Coordinates",
                "description": "Pothole with GPS coordinates",
                "location": "Brigade Road",
                "latitude": "12.9740",
                "longitude": "77.6070",
                "location_description": "Near War Memorial",
            },
            follow_redirects=False,
        )
        if res_geo.status_code == 302 and "/report/success/" in res_geo.headers.get("Location", ""):
            rep_geo_id = int(res_geo.headers.get("Location").split("/")[-1])
            print(f"[PASS] [TEST 2] Report submitted with coordinates succeeded (Report #{rep_geo_id}).")
        else:
            print(f"[FAIL] [TEST 2] Report submission with coordinates failed: {res_geo.status_code}")
            all_passed = False
            rep_geo_id = None

        # TEST 3: Latitude validation (rejects lat < -90 or lat > 90)
        res_bad_lat = client.post(
            "/report",
            data={
                "category": "Road",
                "title": "MapTest_Bad Latitude",
                "description": "Invalid latitude",
                "location": "Test Loc",
                "latitude": "95.0",
                "longitude": "77.0",
            },
            follow_redirects=True,
        )
        if b"Latitude must be between -90 and 90" in res_bad_lat.data:
            print("[PASS] [TEST 3] Latitude validation correctly rejected out-of-range value (95.0).")
        else:
            print("[FAIL] [TEST 3] Latitude validation failed to catch out-of-range value.")
            all_passed = False

        # TEST 4: Longitude validation (rejects lon < -180 or lon > 180)
        res_bad_lon = client.post(
            "/report",
            data={
                "category": "Road",
                "title": "MapTest_Bad Longitude",
                "description": "Invalid longitude",
                "location": "Test Loc",
                "latitude": "12.0",
                "longitude": "-195.0",
            },
            follow_redirects=True,
        )
        if b"Longitude must be between -180 and 180" in res_bad_lon.data:
            print("[PASS] [TEST 4] Longitude validation correctly rejected out-of-range value (-195.0).")
        else:
            print("[FAIL] [TEST 4] Longitude validation failed to catch out-of-range value.")
            all_passed = False

        # TEST 5: Non-numeric coordinate validation
        res_non_num = client.post(
            "/report",
            data={
                "category": "Road",
                "title": "MapTest_Non Numeric Coord",
                "description": "Text in coord",
                "location": "Test Loc",
                "latitude": "abc",
                "longitude": "77.0",
            },
            follow_redirects=True,
        )
        if b"Latitude must be a valid numerical value" in res_non_num.data:
            print("[PASS] [TEST 5] Non-numeric coordinate safely handled without crashing.")
        else:
            print("[FAIL] [TEST 5] Non-numeric coordinate handling failed.")
            all_passed = False

        # TEST 6: Location persistence in Database
        with app.app_context():
            db = database.get_db()
            row_geo = db.execute("SELECT * FROM reports WHERE id = ?", (rep_geo_id,)).fetchone()
            if row_geo and abs(row_geo["latitude"] - 12.9740) < 0.001 and abs(row_geo["longitude"] - 77.6070) < 0.001 and row_geo["location_description"] == "Near War Memorial":
                print(f"[PASS] [TEST 6] Location persistence verified in database (lat={row_geo['latitude']}, lon={row_geo['longitude']}, landmark='{row_geo['location_description']}').")
            else:
                print(f"[FAIL] [TEST 6] Location persistence mismatch: {dict(row_geo) if row_geo else None}")
                all_passed = False

        # TEST 7: Citizen report details view with coordinates displays coordinates & mini-map
        res_det_geo = client.get(f"/report/{rep_geo_id}")
        content_det_geo = res_det_geo.data.decode("utf-8")
        if res_det_geo.status_code == 200 and "12.97400" in content_det_geo and "77.60700" in content_det_geo and "report-mini-map" in content_det_geo:
            print(f"[PASS] [TEST 7] Report #{rep_geo_id} details displays LAT/LON coordinates and mini-map container.")
        else:
            print(f"[FAIL] [TEST 7] Report details missing coordinates or mini-map.")
            all_passed = False

        # TEST 8: Citizen report details view without coordinates displays "Location not provided."
        res_det_no_geo = client.get(f"/report/{rep_no_geo_id}")
        content_det_no_geo = res_det_no_geo.data.decode("utf-8")
        if res_det_no_geo.status_code == 200 and "Location not provided." in content_det_no_geo:
            print(f"[PASS] [TEST 8] Report #{rep_no_geo_id} without coordinates displays 'Location not provided.' placeholder.")
        else:
            print(f"[FAIL] [TEST 8] Report details without coordinates missing placeholder.")
            all_passed = False

        # -------------------------------------------------------------
        # 2. ADMIN CITY MAP & PERMISSION ENFORCEMENT
        # -------------------------------------------------------------

        # TEST 9: Normal citizen blocked from /admin/map (HTTP 403)
        res_cit_map = client.get("/admin/map")
        if res_cit_map.status_code == 403:
            print("[PASS] [TEST 9] Normal citizen access to /admin/map blocked (HTTP 403 Forbidden).")
        else:
            print(f"[FAIL] [TEST 9] Normal citizen reached /admin/map: {res_cit_map.status_code}")
            all_passed = False

        # Unauthenticated blocked from /admin/map
        client.get("/logout")
        res_unauth_map = client.get("/admin/map", follow_redirects=False)
        if res_unauth_map.status_code == 302 and "/login" in res_unauth_map.headers.get("Location", ""):
            print("[PASS] [TEST 10] Unauthenticated user blocked from /admin/map and redirected to /login.")
        else:
            print(f"[FAIL] [TEST 10] Unauthenticated access to /admin/map unexpected status: {res_unauth_map.status_code}")
            all_passed = False

        # Login as Admin
        client.post("/login", data={"email": "admin@cityos.com", "password": "admin123"})

        # TEST 11: Admin can access /admin/map (HTTP 200)
        res_admin_map = client.get("/admin/map")
        content_admin_map = res_admin_map.data.decode("utf-8")
        if res_admin_map.status_code == 200 and "admin-city-map" in content_admin_map and "OpenStreetMap" in content_admin_map:
            print("[PASS] [TEST 11] Admin successfully accessed /admin/map with Leaflet OpenStreetMap console.")
        else:
            print(f"[FAIL] [TEST 11] Admin failed to access /admin/map: {res_admin_map.status_code}")
            all_passed = False

        # TEST 12: Admin report details displays coordinates & mini-map
        res_adm_det = client.get(f"/admin/report/{rep_geo_id}")
        content_adm_det = res_adm_det.data.decode("utf-8")
        if res_adm_det.status_code == 200 and "admin-report-mini-map" in content_adm_det and "12.97400" in content_adm_det:
            print(f"[PASS] [TEST 12] Admin report details displays coordinates and admin mini-map.")
        else:
            print(f"[FAIL] [TEST 12] Admin report details missing mini-map.")
            all_passed = False

        # -------------------------------------------------------------
        # 3. /api/reports/map JSON ENDPOINT & FILTERING
        # -------------------------------------------------------------

        # TEST 13: /api/reports/map returns array of geo-referenced reports
        res_api_all = client.get("/api/reports/map")
        if res_api_all.status_code == 200:
            data_all = res_api_all.get_json()
            # Must include geo reports and omit non-geo reports
            geo_titles = [r["title"] for r in data_all]
            if "MapTest_Central Pothole" in geo_titles and "MapTest_No Location Report" not in geo_titles:
                print(f"[PASS] [TEST 13] /api/reports/map returned {len(data_all)} georeferenced reports, excluding non-geo reports.")
            else:
                print(f"[FAIL] [TEST 13] Geo-referencing query failed: {geo_titles}")
                all_passed = False
        else:
            print(f"[FAIL] [TEST 13] /api/reports/map returned status {res_api_all.status_code}")
            all_passed = False

        # TEST 14: Category filter on /api/reports/map
        res_api_cat = client.get("/api/reports/map?category=Water")
        data_cat = res_api_cat.get_json()
        if all(r["category"] == "Water" for r in data_cat) and any(r["title"] == "MapTest_Water Leak" for r in data_cat):
            print(f"[PASS] [TEST 14] Category filter (Water) returned {len(data_cat)} matching reports.")
        else:
            print(f"[FAIL] [TEST 14] Category filter failed: {data_cat}")
            all_passed = False

        # TEST 15: Priority filter on /api/reports/map
        res_api_prio = client.get("/api/reports/map?priority=HIGH")
        data_prio = res_api_prio.get_json()
        if all(r["priority"] == "HIGH" for r in data_prio) and any(r["title"] == "MapTest_Central Pothole" for r in data_prio):
            print(f"[PASS] [TEST 15] Priority filter (HIGH) returned {len(data_prio)} high priority reports.")
        else:
            print(f"[FAIL] [TEST 15] Priority filter failed: {data_prio}")
            all_passed = False

        # TEST 16: Status filter on /api/reports/map (In Progress)
        res_api_st = client.get("/api/reports/map?status=In+Progress")
        data_st = res_api_st.get_json()
        if all(r["status"] == "In Progress" for r in data_st) and any(r["title"] == "MapTest_Water Leak" for r in data_st):
            print(f"[PASS] [TEST 16] Status filter (In Progress) returned {len(data_st)} matching reports.")
        else:
            print(f"[FAIL] [TEST 16] Status filter failed: {data_st}")
            all_passed = False

        # TEST 17: Privacy check - verify no passwords or user emails leaked in map API
        raw_api_str = res_api_all.data.decode("utf-8")
        if "password" not in raw_api_str and "citizen_map@cityos.com" not in raw_api_str:
            print("[PASS] [TEST 17] Privacy verified: No passwords or citizen personal emails exposed in map JSON API.")
        else:
            print("[FAIL] [TEST 17] Sensitive information found in map JSON response!")
            all_passed = False

    # -------------------------------------------------------------
    # 4. REGRESSION TEST SUITES (ALL PREVIOUS 7 SUITES)
    # -------------------------------------------------------------
    suites = [
        ("test_database.py", "[TEST 18] Database regression tests"),
        ("test_auth.py", "[TEST 19] Authentication regression tests"),
        ("test_citizen_dashboard.py", "[TEST 20] Citizen Dashboard regression tests"),
        ("test_reports.py", "[TEST 21] Report submission regression tests"),
        ("test_my_reports.py", "[TEST 22] My Reports & Tracking regression tests"),
        ("test_admin.py", "[TEST 23] Admin Dashboard & Management regression tests"),
        ("test_smart_classifier.py", "[TEST 24] Smart Complaint Intelligence regression tests"),
    ]

    for script, label in suites:
        proc = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0:
            print(f"[PASS] {label} passed.")
        else:
            print(f"[FAIL] {label} failed:\n{proc.stdout}\n{proc.stderr}")
            all_passed = False

    print("==================================================")
    if all_passed:
        print("🎉 ALL 24 LOCATION & CITY MAP TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED.")
    print("==================================================")
    return all_passed


if __name__ == "__main__":
    success = run_location_map_tests()
    sys.exit(0 if success else 1)
