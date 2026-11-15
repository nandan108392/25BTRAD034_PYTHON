import os
import sys
import sqlite3
import subprocess
from datetime import datetime
from werkzeug.security import generate_password_hash
from app import app
import database
import smart_classifier

# Windows console encoding safeguard
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def setup_smart_test_data():
    """Sets up clean test data for smart complaint intelligence tests."""
    with app.app_context():
        db = database.get_db()
        db.execute("DELETE FROM reports WHERE title LIKE 'SmartTest_%'")
        db.execute("DELETE FROM users WHERE email IN ('citizen_smart@cityos.com')")

        pw_hash = generate_password_hash("password123")
        now = datetime.now().isoformat()

        # Create Citizen User
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Smart Tester", "citizen_smart@cityos.com", pw_hash, "user", now),
        )
        citizen_id = db.execute("SELECT id FROM users WHERE email = 'citizen_smart@cityos.com'").fetchone()["id"]

        db.commit()
        return citizen_id


def run_smart_classifier_tests():
    print("==================================================")
    print("   CityOS Step 8: Smart Complaint Intelligence    ")
    print("==================================================")
    all_passed = True
    citizen_id = setup_smart_test_data()

    # -------------------------------------------------------------
    # 1. UNIT TESTS FOR smart_classifier.classify_complaint
    # -------------------------------------------------------------

    # TEST 1: Road / Pothole Detection
    res1 = smart_classifier.classify_complaint(
        "There is a huge pothole near the school and bikes are almost falling.",
        "Dangerous Crater on Road"
    )
    if res1["category"] == "Road" and res1["issue_type"] == "Pothole" and res1["priority"] == "HIGH":
        print("[PASS] [TEST 1] Road/Pothole correctly detected with HIGH priority (school danger/falling).")
    else:
        print(f"[FAIL] [TEST 1] Road/Pothole classification failed: {res1}")
        all_passed = False

    # TEST 2: Water Leakage Detection
    res2 = smart_classifier.classify_complaint(
        "There is a major water pipe leak and water is flooding the road.",
        "Burst Pipe in Lane 4"
    )
    if res2["category"] == "Water" and res2["issue_type"] == "Water Leakage" and res2["priority"] == "HIGH":
        print("[PASS] [TEST 2] Water Leakage correctly detected with HIGH priority (flooding/major leak).")
    else:
        print(f"[FAIL] [TEST 2] Water Leakage classification failed: {res2}")
        all_passed = False

    # TEST 3: Garbage / Waste Detection
    res3 = smart_classifier.classify_complaint(
        "Illegal garbage dumping in the corner plot creating uncollected trash.",
        "Overflowing Trash"
    )
    if res3["category"] == "Waste" and res3["issue_type"] in ["Garbage Dumping", "Uncollected Waste"] and res3["priority"] == "MEDIUM":
        print(f"[PASS] [TEST 3] Garbage/Waste correctly detected (Category: {res3['category']}, Issue: {res3['issue_type']}, Priority: {res3['priority']}).")
    else:
        print(f"[FAIL] [TEST 3] Garbage/Waste classification failed: {res3}")
        all_passed = False

    # TEST 4: Streetlight / Electricity Detection
    res4 = smart_classifier.classify_complaint(
        "The street light has stopped working.",
        "Dark street pole"
    )
    if res4["category"] == "Electricity" and res4["issue_type"] == "Broken Streetlight" and res4["priority"] == "MEDIUM":
        print("[PASS] [TEST 4] Streetlight/Electricity correctly detected (Electricity / Broken Streetlight / MEDIUM).")
    else:
        print(f"[FAIL] [TEST 4] Streetlight classification failed: {res4}")
        all_passed = False

    # TEST 5: Traffic Signal Detection
    res5 = smart_classifier.classify_complaint(
        "Traffic light is blinking red causing massive congestion at junction.",
        "Signal Failure"
    )
    if res5["category"] == "Traffic" and res5["issue_type"] in ["Signal Problem", "Traffic Congestion"] and res5["priority"] == "MEDIUM":
        print(f"[PASS] [TEST 5] Traffic signal issue detected (Category: {res5['category']}, Issue: {res5['issue_type']}, Priority: {res5['priority']}).")
    else:
        print(f"[FAIL] [TEST 5] Traffic signal classification failed: {res5}")
        all_passed = False

    # TEST 6: Public Safety / Emergency Hazard Detection
    res6 = smart_classifier.classify_complaint(
        "Fire hazard and live wire sparked an accident near market.",
        "Emergency Safety Hazard"
    )
    if res6["category"] == "Public Safety" and res6["priority"] == "HIGH":
        print(f"[PASS] [TEST 6] Public Safety Emergency/Hazard correctly detected with HIGH priority (Keywords: {res6['keywords']}).")
    else:
        print(f"[FAIL] [TEST 6] Public Safety classification failed: {res6}")
        all_passed = False

    # TEST 7: Priority Detection Levels (HIGH, MEDIUM, LOW, and Default)
    res_high = smart_classifier.classify_complaint("Severe life threatening fire and building collapse")
    res_low = smart_classifier.classify_complaint("Cosmetic paint suggestion and minor aesthetic request")
    res_med = smart_classifier.classify_complaint("Pavement has broken stones")
    
    if res_high["priority"] == "HIGH" and res_low["priority"] == "LOW" and res_med["priority"] == "MEDIUM":
        print("[PASS] [TEST 7] Priority evaluation levels verified (HIGH, LOW, MEDIUM).")
    else:
        print(f"[FAIL] [TEST 7] Priority evaluation mismatch: High={res_high['priority']}, Low={res_low['priority']}, Med={res_med['priority']}")
        all_passed = False

    # TEST 8: Unknown / Unclassified Complaint Handling
    res8 = smart_classifier.classify_complaint("I would like to inquire about library opening hours on weekends.")
    if res8["category"] == "Other" and res8["issue_type"] == "General Issue" and res8["priority"] == "MEDIUM":
        print("[PASS] [TEST 8] Unknown complaint safely defaulted to (Other / General Issue / MEDIUM).")
    else:
        print(f"[FAIL] [TEST 8] Unknown complaint fallback failed: {res8}")
        all_passed = False

    # TEST 9: Multiple Keyword Handling and Scoring Weighting
    res9 = smart_classifier.classify_complaint(
        "Water pipe leakage flooded the road pavement near the streetlight.",
        "Leakage"
    )
    # Multiple keywords from Water, Road, Electricity present -> Water should win due to 'water pipe leakage', 'flooded'
    if res9["category"] == "Water" and len(res9["keywords"]) >= 3:
        print(f"[PASS] [TEST 9] Multi-keyword conflict resolution chose strongest category ({res9['category']}) with extracted keywords: {res9['keywords']}.")
    else:
        print(f"[FAIL] [TEST 9] Multi-keyword scoring failed: {res9}")
        all_passed = False

    # -------------------------------------------------------------
    # 2. INTEGRATION TESTS (REPORT SUBMISSION & VIEWS)
    # -------------------------------------------------------------

    with app.test_client() as client:
        # Login as citizen
        client.post("/login", data={"email": "citizen_smart@cityos.com", "password": "password123"})

        # TEST 10: Auto-classified report submission (Auto-Detect category)
        res_sub = client.post(
            "/report",
            data={
                "category": "Auto-Detect",
                "title": "SmartTest_Deep Pothole",
                "description": "Severe deep pothole and broken road pavement near school causing danger with bikes almost falling.",
                "location": "Avenue 7, Block B",
            },
            follow_redirects=False,
        )
        if res_sub.status_code == 302 and "/report/success/" in res_sub.headers.get("Location", ""):
            report_id = int(res_sub.headers.get("Location").split("/")[-1])
            print(f"[PASS] [TEST 10] Citizen submitted report with Auto-Detect; saved as Report #{report_id}.")
        else:
            print(f"[FAIL] [TEST 10] Report submission failed: {res_sub.status_code}")
            all_passed = False
            report_id = None

        # TEST 11: Verify database persistence of issue_type, priority, keywords
        with app.app_context():
            db = database.get_db()
            row = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
            if row and row["category"] == "Road" and row["issue_type"] == "Pothole" and row["priority"] == "HIGH":
                print(f"[PASS] [TEST 11] Database persistence verified: Category={row['category']}, Issue={row['issue_type']}, Priority={row['priority']}, Keywords='{row['keywords']}'.")
            else:
                print(f"[FAIL] [TEST 11] Database values mismatch: {dict(row) if row else None}")
                all_passed = False

        # TEST 12: Citizen report details view displays Smart Analysis section
        res_det = client.get(f"/report/{report_id}")
        content_det = res_det.data.decode("utf-8")
        if res_det.status_code == 200 and "Smart Analysis" in content_det and "Pothole" in content_det and "HIGH" in content_det:
            print("[PASS] [TEST 12] Citizen report details displays 'Smart Analysis' card with Issue, Category, and Priority.")
        else:
            print(f"[FAIL] [TEST 12] Citizen report details missing Smart Analysis: status={res_det.status_code}")
            all_passed = False

        # Login as Admin
        client.post("/login", data={"email": "admin@cityos.com", "password": "admin123"})

        # TEST 13: Admin table displays Issue Type and Priority columns & badges
        res_admin = client.get("/admin")
        content_admin = res_admin.data.decode("utf-8")
        if res_admin.status_code == 200 and "Issue Type" in content_admin and "Priority" in content_admin and "badge-priority-high" in content_admin:
            print("[PASS] [TEST 13] Admin management table displays 'Issue Type' and 'Priority' columns with visual badges.")
        else:
            print(f"[FAIL] [TEST 13] Admin table missing Issue Type or Priority columns: {res_admin.status_code}")
            all_passed = False

        # TEST 14: Admin report details displays Smart Complaint Intelligence panel
        res_admin_det = client.get(f"/admin/report/{report_id}")
        content_admin_det = res_admin_det.data.decode("utf-8")
        if res_admin_det.status_code == 200 and "Smart Complaint Intelligence" in content_admin_det and "Pothole" in content_admin_det and "HIGH" in content_admin_det:
            print("[PASS] [TEST 14] Admin report details displays 'Smart Complaint Intelligence' panel.")
        else:
            print(f"[FAIL] [TEST 14] Admin report details missing Smart Intelligence: {res_admin_det.status_code}")
            all_passed = False

    # -------------------------------------------------------------
    # 3. REGRESSION TEST SUITES
    # -------------------------------------------------------------
    suites = [
        ("test_database.py", "[TEST 15] Database regression tests"),
        ("test_auth.py", "[TEST 16] Authentication regression tests"),
        ("test_citizen_dashboard.py", "[TEST 17] Citizen Dashboard regression tests"),
        ("test_reports.py", "[TEST 18] Report submission regression tests"),
        ("test_my_reports.py", "[TEST 19] My Reports & Tracking regression tests"),
        ("test_admin.py", "[TEST 20] Admin Dashboard & Management regression tests"),
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
        print("🎉 ALL 20 SMART COMPLAINT INTELLIGENCE & REGRESSION TESTS PASSED!")
    else:
        print("❌ SOME TESTS FAILED.")
    print("==================================================")
    return all_passed


if __name__ == "__main__":
    success = run_smart_classifier_tests()
    sys.exit(0 if success else 1)
