"""
CityOS Step 10: City Intelligence & Problem Heatmap Unit & Integration Tests
---------------------------------------------------------------------------
Tests:
1. Haversine distance spatial formula
2. City statistics KPI computation (7 dynamic metrics)
3. Category analytics and percentage breakdown
4. Priority distribution analytics
5. Lifecycle status analytics
6. Spatial clustering and hotspot detection (~500m radius)
7. Ranked top problem areas
8. Resolution turnaround time analytics
9. Deterministic smart city insights generation
10. Weighted heatmap points generation
11. Admin Intelligence route access (/admin/intelligence) with RBAC enforcement
12. Analytics JSON API (/api/reports/analytics) with query filtering
13. Heatmap JSON API (/api/reports/heatmap) with query filtering
14. Privacy verification (no sensitive user data in analytics/heatmap responses)
"""

import math
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

import database
import city_analytics
from app import app


class CityIntelligenceTestCase(unittest.TestCase):
    def setUp(self):
        # Create a temporary SQLite database for test isolation
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
        os.unlink(self.db_path)

    def _seed_test_data(self):
        """Populate database with controlled test users and multi-category geo-tagged reports."""
        db = database.get_db()

        now = datetime.now()
        t_now = now.isoformat()

        # Seed users: citizen1, citizen2
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("Jane Citizen", "jane@example.com", generate_password_hash("pass123"), "user", t_now),
        )
        db.execute(
            "INSERT INTO users (name, email, password, role, created_at) VALUES (?, ?, ?, ?, ?)",
            ("John Citizen", "john@example.com", generate_password_hash("pass123"), "user", t_now),
        )
        db.commit()

        # Fetch user IDs
        jane = db.execute("SELECT id FROM users WHERE email = 'jane@example.com'").fetchone()
        john = db.execute("SELECT id FROM users WHERE email = 'john@example.com'").fetchone()

        t_minus_2_days = (now - timedelta(days=2)).isoformat()
        t_minus_1_day = (now - timedelta(days=1)).isoformat()
        t_minus_5_hrs = (now - timedelta(hours=5)).isoformat()

        # Cluster 1: Indiranagar 100ft Road (3 reports near 12.9716, 77.6412)
        # Report 1: Road / Pothole (High priority, Reported)
        db.execute(
            """
            INSERT INTO reports (
                user_id, category, title, description, location, location_description,
                latitude, longitude, status, issue_type, priority, keywords, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                jane["id"], "Road", "Deep pothole near 100ft road", "Dangerous crater on main road",
                "Indiranagar 100ft Rd", "Near Metro Station", 12.9716, 77.6412, "Reported",
                "Pothole", "HIGH", "road, pothole, dangerous", t_minus_2_days, t_minus_2_days
            ),
        )

        # Report 2: Road / Road Damage (High priority, In Progress) - 100 meters away
        db.execute(
            """
            INSERT INTO reports (
                user_id, category, title, description, location, location_description,
                latitude, longitude, status, issue_type, priority, keywords, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                john["id"], "Road", "Broken road surface", "Damaged asphalt causing vehicle skids",
                "Indiranagar 100ft Rd", "Opposite Cafe", 12.9720, 77.6415, "In Progress",
                "Road Damage", "HIGH", "broken, road, damage", t_minus_1_day, t_minus_1_day
            ),
        )

        # Report 3: Traffic / Congestion (Medium priority, Under Review) - 150 meters away
        db.execute(
            """
            INSERT INTO reports (
                user_id, category, title, description, location, location_description,
                latitude, longitude, status, issue_type, priority, keywords, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                jane["id"], "Traffic", "Severe traffic jam", "Signal failure causing gridlock",
                "Indiranagar 100ft Rd", "Junction", 12.9718, 77.6410, "Under Review",
                "Traffic Problem", "MEDIUM", "traffic, signal, jam", t_minus_5_hrs, t_minus_5_hrs
            ),
        )

        # Cluster 2: Koramangala 4th Block (2 reports near 12.9352, 77.6245, ~5km away from Indiranagar)
        # Report 4: Water / Water Leakage (High priority, Resolved in 24 hours)
        db.execute(
            """
            INSERT INTO reports (
                user_id, category, title, description, location, location_description,
                latitude, longitude, status, issue_type, priority, keywords, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                jane["id"], "Water", "Burst water pipe", "Major water leakage flooding street",
                "Koramangala 4th Block", "80ft Road", 12.9352, 77.6245, "Resolved",
                "Water Leakage", "HIGH", "water, pipe, burst, leak", t_minus_2_days, t_minus_1_day
            ),
        )

        # Report 5: Waste / Garbage Dump (Low priority, Rejected) - near Koramangala
        db.execute(
            """
            INSERT INTO reports (
                user_id, category, title, description, location, location_description,
                latitude, longitude, status, issue_type, priority, keywords, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                john["id"], "Waste", "Garbage on corner", "Overflowing bin",
                "Koramangala 4th Block", "Near Park", 12.9355, 77.6248, "Rejected",
                "Garbage Dump", "LOW", "waste, garbage, bin", t_minus_1_day, t_now
            ),
        )

        # Report 6: Non-geolocated Report (Electricity, Medium priority, Reported)
        db.execute(
            """
            INSERT INTO reports (
                user_id, category, title, description, location, location_description,
                latitude, longitude, status, issue_type, priority, keywords, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                jane["id"], "Electricity", "Streetlight blinking", "Flickering lamp post",
                "MG Road", None, None, None, "Reported",
                "Streetlight", "MEDIUM", "electricity, light", t_now, t_now
            ),
        )

        db.commit()

    def _login_as_admin(self):
        return self.client.post(
            "/login",
            data={"email": "admin@cityos.com", "password": "admin123"},
            follow_redirects=True,
        )

    def _login_as_citizen(self):
        return self.client.post(
            "/login",
            data={"email": "jane@example.com", "password": "pass123"},
            follow_redirects=True,
        )

    # -------------------------------------------------------------
    # 1. Haversine Distance Tests
    # -------------------------------------------------------------
    def test_haversine_distance_computation(self):
        # Indiranagar to Indiranagar adjacent (~0.05 km)
        dist = city_analytics.haversine_distance(12.9716, 77.6412, 12.9720, 77.6415)
        self.assertLess(dist, 0.1)
        self.assertGreater(dist, 0.0)

        # Indiranagar to Koramangala (~4.5 - 5.5 km)
        dist_far = city_analytics.haversine_distance(12.9716, 77.6412, 12.9352, 77.6245)
        self.assertGreater(dist_far, 3.5)
        self.assertLess(dist_far, 6.5)

        # Null coordinate safety
        self.assertEqual(city_analytics.haversine_distance(None, 77.0, 12.0, 77.0), float("inf"))
        self.assertEqual(city_analytics.haversine_distance(12.0, None, 12.0, 77.0), float("inf"))

    # -------------------------------------------------------------
    # 2. City Statistics KPIs
    # -------------------------------------------------------------
    def test_compute_city_statistics(self):
        with app.app_context():
            db = database.get_db()
            stats = city_analytics.compute_city_statistics(db)

            self.assertEqual(stats["total"], 6)
            # Open = Reported (2) + Under Review (1) = 3
            self.assertEqual(stats["open"], 3)
            self.assertEqual(stats["reported"], 2)
            self.assertEqual(stats["under_review"], 1)
            self.assertEqual(stats["in_progress"], 1)
            self.assertEqual(stats["resolved"], 1)
            self.assertEqual(stats["rejected"], 1)
            # High priority = 3 (Report 1, 2, 4)
            self.assertEqual(stats["high_priority"], 3)
            # Geolocated = 5 (Reports 1 to 5)
            self.assertEqual(stats["with_location"], 5)
            self.assertAlmostEqual(stats["resolution_rate"], round(1/6 * 100, 1))

    def test_compute_city_statistics_with_filters(self):
        with app.app_context():
            db = database.get_db()
            # Category filter: Road
            road_stats = city_analytics.compute_city_statistics(db, {"category": "Road"})
            self.assertEqual(road_stats["total"], 2)
            self.assertEqual(road_stats["high_priority"], 2)

            # Priority filter: HIGH
            high_stats = city_analytics.compute_city_statistics(db, {"priority": "HIGH"})
            self.assertEqual(high_stats["total"], 3)

    # -------------------------------------------------------------
    # 3. Category, Priority & Status Analytics
    # -------------------------------------------------------------
    def test_compute_category_analytics(self):
        with app.app_context():
            db = database.get_db()
            cat_analytics = city_analytics.compute_category_analytics(db)

            self.assertEqual(cat_analytics["total"], 6)
            breakdown_dict = {b["category"]: b for b in cat_analytics["breakdown"]}

            self.assertEqual(breakdown_dict["Road"]["count"], 2)
            self.assertEqual(breakdown_dict["Water"]["count"], 1)
            self.assertEqual(breakdown_dict["Waste"]["count"], 1)
            self.assertEqual(breakdown_dict["Electricity"]["count"], 1)
            self.assertEqual(breakdown_dict["Traffic"]["count"], 1)
            self.assertIn("Road", cat_analytics["labels"])

    def test_compute_priority_analytics(self):
        with app.app_context():
            db = database.get_db()
            prio = city_analytics.compute_priority_analytics(db)

            self.assertEqual(prio["total"], 6)
            self.assertEqual(prio["high"], 3)
            self.assertEqual(prio["medium"], 2)
            self.assertEqual(prio["low"], 1)
            self.assertEqual(prio["labels"], ["High", "Medium", "Low"])
            self.assertEqual(prio["data"], [3, 2, 1])

    def test_compute_status_analytics(self):
        with app.app_context():
            db = database.get_db()
            st = city_analytics.compute_status_analytics(db)

            self.assertEqual(st["total"], 6)
            self.assertEqual(st["reported"], 2)
            self.assertEqual(st["under_review"], 1)
            self.assertEqual(st["in_progress"], 1)
            self.assertEqual(st["resolved"], 1)
            self.assertEqual(st["rejected"], 1)

    # -------------------------------------------------------------
    # 4. Spatial Hotspots & Top Problem Areas
    # -------------------------------------------------------------
    def test_detect_problem_hotspots_clustering(self):
        with app.app_context():
            db = database.get_db()
            hotspots = city_analytics.detect_problem_hotspots(db, distance_threshold_km=0.5)

            self.assertGreaterEqual(len(hotspots), 2)

            # Top hotspot should be Indiranagar cluster with 3 complaints
            top_hs = hotspots[0]
            self.assertEqual(top_hs["count"], 3)
            self.assertEqual(top_hs["top_category"], "Road")
            self.assertEqual(top_hs["highest_priority"], "HIGH")
            self.assertIn("Indiranagar", top_hs["location_name"])
            self.assertTrue(top_hs["is_multi"])

            # Second hotspot should be Koramangala cluster with 2 complaints
            second_hs = hotspots[1]
            self.assertEqual(second_hs["count"], 2)
            self.assertIn("Koramangala", second_hs["location_name"])

    def test_get_top_problem_areas(self):
        with app.app_context():
            db = database.get_db()
            top_areas = city_analytics.get_top_problem_areas(db, limit=5)

            self.assertGreaterEqual(len(top_areas), 1)
            self.assertEqual(top_areas[0]["rank"], 1)
            self.assertEqual(top_areas[0]["count"], 3)
            self.assertEqual(top_areas[0]["category"], "Road")

    # -------------------------------------------------------------
    # 5. Resolution Turnaround Analytics
    # -------------------------------------------------------------
    def test_compute_resolution_analytics(self):
        with app.app_context():
            db = database.get_db()
            res = city_analytics.compute_resolution_analytics(db)

            self.assertEqual(res["total_reports"], 6)
            self.assertEqual(res["resolved_reports"], 1)
            self.assertEqual(res["unresolved_reports"], 5)
            # Water report created 2 days ago, updated 1 day ago -> 24 hours turnaround
            self.assertAlmostEqual(res["avg_resolution_hours"], 24.0, delta=1.0)
            self.assertAlmostEqual(res["avg_resolution_days"], 1.0, delta=0.1)
            self.assertIn("Water", res["category_performance"])

    # -------------------------------------------------------------
    # 6. Smart City Insights Generation
    # -------------------------------------------------------------
    def test_generate_smart_insights(self):
        with app.app_context():
            db = database.get_db()
            insights = city_analytics.generate_smart_insights(db)

            self.assertIsInstance(insights, list)
            self.assertGreaterEqual(len(insights), 2)

            insight_types = [i["type"] for i in insights]
            # Must detect dominant category (Road)
            self.assertIn("category", insight_types)
            # Must detect priority cluster (Indiranagar hazard)
            self.assertIn("hazard", insight_types)

            for ins in insights:
                self.assertIn("title", ins)
                self.assertIn("message", ins)
                self.assertIn("badge", ins)
                self.assertIn("icon", ins)

    # -------------------------------------------------------------
    # 7. Weighted Heatmap Coordinates
    # -------------------------------------------------------------
    def test_get_heatmap_points(self):
        with app.app_context():
            db = database.get_db()
            points = city_analytics.get_heatmap_points(db)

            # 5 geolocated reports
            self.assertEqual(len(points), 5)
            for pt in points:
                self.assertEqual(len(pt), 3)
                lat, lon, weight = pt
                self.assertIsInstance(lat, float)
                self.assertIsInstance(lon, float)
                # Weights: HIGH=1.0, MEDIUM=0.6, LOW=0.3
                self.assertIn(weight, [1.0, 0.6, 0.3])

    # -------------------------------------------------------------
    # 8. Admin Intelligence Web Route & RBAC
    # -------------------------------------------------------------
    def test_admin_intelligence_access_control(self):
        # 1. Unauthenticated -> Redirect to /login
        res_unauth = self.client.get("/admin/intelligence")
        self.assertEqual(res_unauth.status_code, 302)
        self.assertIn("/login", res_unauth.location)

        # 2. Authenticated Citizen -> 403 Forbidden
        self._login_as_citizen()
        res_citizen = self.client.get("/admin/intelligence")
        self.assertEqual(res_citizen.status_code, 403)
        self.client.get("/logout")

        # 3. Authenticated Admin -> 200 OK
        self._login_as_admin()
        res_admin = self.client.get("/admin/intelligence")
        self.assertEqual(res_admin.status_code, 200)

        # Verify page content elements
        html = res_admin.get_data(as_text=True)
        self.assertIn("City Intelligence & Problem Hotspots", html)
        self.assertIn("Municipal KPIs & Core Statistics", html)
        self.assertIn("Total Reports", html)
        self.assertIn("Open / Pending", html)
        self.assertIn("High Priority", html)
        self.assertIn("Geolocated", html)
        self.assertIn("Category Distribution", html)
        self.assertIn("Problem Hotspots & Ranked Problem Areas", html)
        self.assertIn("Indiranagar 100ft Rd", html)
        self.assertIn("categoryChart", html)
        self.assertIn("priorityChart", html)

    # -------------------------------------------------------------
    # 9. JSON API Endpoints (/api/reports/analytics & /api/reports/heatmap)
    # -------------------------------------------------------------
    def test_api_reports_analytics(self):
        self._login_as_admin()

        # Full analytics
        res = self.client.get("/api/reports/analytics")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()

        self.assertIn("stats", data)
        self.assertIn("category_analytics", data)
        self.assertIn("priority_analytics", data)
        self.assertIn("status_analytics", data)
        self.assertIn("hotspots", data)
        self.assertIn("top_areas", data)
        self.assertIn("resolution_analytics", data)
        self.assertIn("insights", data)

        self.assertEqual(data["stats"]["total"], 6)

        # Filtered analytics
        res_filtered = self.client.get("/api/reports/analytics?category=Road")
        self.assertEqual(res_filtered.status_code, 200)
        data_filtered = res_filtered.get_json()
        self.assertEqual(data_filtered["stats"]["total"], 2)

    def test_api_reports_heatmap(self):
        self._login_as_admin()

        res = self.client.get("/api/reports/heatmap")
        self.assertEqual(res.status_code, 200)
        points = res.get_json()

        self.assertEqual(len(points), 5)
        self.assertIsInstance(points[0], list)
        self.assertEqual(len(points[0]), 3)

        # Filtered heatmap
        res_road = self.client.get("/api/reports/heatmap?category=Road")
        points_road = res_road.get_json()
        self.assertEqual(len(points_road), 2)

    # -------------------------------------------------------------
    # 10. Privacy & PII Verification
    # -------------------------------------------------------------
    def test_analytics_and_heatmap_privacy(self):
        self._login_as_admin()

        # Verify no password hashes or citizen emails in analytics endpoint
        res_analytics = self.client.get("/api/reports/analytics")
        text_analytics = res_analytics.get_data(as_text=True)
        self.assertNotIn("jane@example.com", text_analytics)
        self.assertNotIn("password", text_analytics)
        self.assertNotIn("scrypt:", text_analytics)
        self.assertNotIn("pbkdf2:", text_analytics)

        # Verify no citizen emails or names in heatmap endpoint
        res_heatmap = self.client.get("/api/reports/heatmap")
        text_heatmap = res_heatmap.get_data(as_text=True)
        self.assertNotIn("jane@example.com", text_heatmap)
        self.assertNotIn("Jane Citizen", text_heatmap)


if __name__ == "__main__":
    unittest.main()
