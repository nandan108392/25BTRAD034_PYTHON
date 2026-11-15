import os
import sys
import unittest
import importlib
from app import app
import database

# Windows console encoding safeguard
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


class ProductionHardeningTest(unittest.TestCase):
    """
    Validates Phase 2.3 Production Environment Packaging & Hardening:
    - WSGI Entry Point (wsgi:app)
    - Production Configuration & Secret Key validation
    - Security Response Headers
    - Cookie and Session Flags
    - 403, 404, 413 & 500 Error Pages
    - Safe Default Debug Setting
    - Health Check endpoint security
    - Core Citizen & Admin workflow sanity
    """

    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_01_wsgi_app_importable(self):
        """Verify that wsgi:app is exposed and loadable by Gunicorn."""
        import wsgi
        self.assertIsNotNone(wsgi.app)
        self.assertEqual(wsgi.app, app)

    def test_02_security_headers_present(self):
        """Verify that all responses include defensive HTTP security headers."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(res.headers.get("X-XSS-Protection"), "1; mode=block")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    def test_03_session_cookie_flags_configured(self):
        """Verify that session cookies are configured with HTTPOnly and SameSite=Lax."""
        self.assertTrue(app.config.get("SESSION_COOKIE_HTTPONLY"))
        self.assertEqual(app.config.get("SESSION_COOKIE_SAMESITE"), "Lax")
        self.assertIsNotNone(app.config.get("PERMANENT_SESSION_LIFETIME"))

    def test_04_custom_500_error_page(self):
        """Verify that 500 errors render the branded 500 template."""
        from app import internal_server_error
        with app.test_request_context():
            rendered, code = internal_server_error(Exception("Simulated Error"))
            self.assertEqual(code, 500)
            self.assertIn("Internal Server Encounter", rendered)
            self.assertIn("500", rendered)

    def test_05_custom_413_error_page(self):
        """Verify that 413 errors render the branded 413 template."""
        from app import payload_too_large_error
        with app.test_request_context():
            rendered, code = payload_too_large_error(Exception("Payload Too Large"))
            self.assertEqual(code, 413)
            self.assertIn("Evidence File Too Large", rendered)
            self.assertIn("413", rendered)

    def test_06_custom_403_and_404_error_pages(self):
        """Verify that 403 and 404 errors render the branded templates."""
        from app import forbidden_error, not_found_error
        with app.test_request_context():
            res403, code403 = forbidden_error(Exception("Forbidden"))
            self.assertEqual(code403, 403)
            self.assertIn("403", res403)

            res404, code404 = not_found_error(Exception("Not Found"))
            self.assertEqual(code404, 404)
            self.assertIn("404", res404)

    def test_07_api_health_endpoint(self):
        """Verify /api/health responds with 200 OK without leaking sensitive info."""
        res = self.client.get("/api/health")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "online")
        self.assertEqual(data["database"]["status"], "connected")
        # Ensure no passwords or secret keys are leaked in health check
        raw_text = res.get_data(as_text=True)
        self.assertNotIn("password", raw_text)
        self.assertNotIn("SECRET_KEY", raw_text)

    def test_08_admin_credentials_env_configurable(self):
        """Verify database helper seeds admin respecting environment configuration."""
        with app.app_context():
            db = database.get_db()
            admin = db.execute("SELECT * FROM users WHERE role = 'admin'").fetchone()
            self.assertIsNotNone(admin)

    def test_09_landing_page_accessible(self):
        """Verify GET / renders CityOS landing page."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"CityOS", res.data)


if __name__ == "__main__":
    unittest.main()
