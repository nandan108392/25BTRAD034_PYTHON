import os
import sys
import subprocess
import time

# Windows console encoding safeguard
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

TEST_SCRIPTS = [
    ("test_database.py", "Database & Schema Layer"),
    ("test_auth.py", "Authentication & RBAC"),
    ("test_citizen_dashboard.py", "Citizen Dashboard & Stats"),
    ("test_reports.py", "Report Submission & Media"),
    ("test_my_reports.py", "My Reports & Tracking"),
    ("test_admin.py", "Admin Management & Status"),
    ("test_smart_classifier.py", "Smart Complaint Intelligence"),
    ("test_location_map.py", "Location & City Map"),
    ("test_city_intelligence.py", "City Intelligence & Heatmap"),
    ("test_citizen_tracking.py", "Live Citizen Tracking & Notifications"),
    ("test_municipal_operations.py", "Municipal Operations & Problem Resolution"),
    ("test_e2e_audit.py", "Comprehensive End-to-End Audit"),
    ("test_live_server.py", "Live Server Integration Audit"),
    ("test_production_hardening.py", "Production Hardening & Security Headers"),
]


def run_all():
    print("=" * 70)
    print("           CityOS V1 Complete Quality & Regression Suite          ")
    print("=" * 70)

    total_suites = len(TEST_SCRIPTS)
    passed_suites = 0
    failed_suites = 0
    start_time = time.time()

    results = []

    for script, description in TEST_SCRIPTS:
        print(f"\n[RUNNING] {script} ({description})...")
        proc = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if proc.returncode == 0:
            print(f"  --> [PASS] {script}")
            passed_suites += 1
            results.append((script, description, "PASS", proc.stdout.strip()))
        else:
            print(f"  --> [FAIL] {script}")
            failed_suites += 1
            results.append((script, description, "FAIL", proc.stdout + "\n" + proc.stderr))

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"AUDIT SUMMARY: {passed_suites}/{total_suites} Suites Passed in {elapsed:.2f}s")
    print("=" * 70)

    if failed_suites == 0:
        print("🎉 ALL TEST SUITES PASSED WITH ZERO FAILURES AND ZERO REGRESSIONS!")
    else:
        print(f"❌ {failed_suites} SUITE(S) FAILED.")

    return failed_suites == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
