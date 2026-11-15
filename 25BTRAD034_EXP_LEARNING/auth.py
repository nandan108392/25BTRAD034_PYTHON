import re
from functools import wraps
from datetime import datetime
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    g,
)
from werkzeug.security import generate_password_hash, check_password_hash
import database

auth_bp = Blueprint("auth", __name__)

# Regular expression pattern for basic email validation
EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"


def login_required(view):
    """
    Decorator to ensure that the user is logged in before accessing a route.
    Redirects unauthenticated users to the login page.
    """
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("user_id") is None:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("auth.login"))
        return view(**kwargs)

    return wrapped_view


def admin_required(view):
    """
    Decorator to ensure that the user is logged in AND has the 'admin' role.
    Redirects unauthenticated users to login and returns 403 for unauthorized users.
    """
    @wraps(view)
    def wrapped_view(**kwargs):
        if session.get("user_id") is None:
            flash("Please log in to access the administration panel.", "warning")
            return redirect(url_for("auth.login"))
        if session.get("role") != "admin":
            from flask import abort
            abort(403)
        return view(**kwargs)

    return wrapped_view


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    """User Registration route with input validation and password hashing."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        error = None

        # Validation rules
        if not name:
            error = "Full name is required."
        elif not email or not re.match(EMAIL_REGEX, email):
            error = "A valid email address is required."
        elif not password:
            error = "Password is required."
        elif len(password) < 6:
            error = "Password must be at least 6 characters long."
        elif password != confirm_password:
            error = "Passwords do not match."
        else:
            db = database.get_db()
            # Check for existing email
            existing_user = db.execute(
                "SELECT id FROM users WHERE LOWER(email) = ?", (email,)
            ).fetchone()

            if existing_user is not None:
                error = f"An account with email '{email}' already exists."

        if error is None:
            # Secure password hashing with Werkzeug
            hashed_password = generate_password_hash(password)
            now = datetime.now().isoformat()
            db = database.get_db()
            db.execute(
                """
                INSERT INTO users (name, email, password, role, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, email, hashed_password, "user", now),
            )
            db.commit()

            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for("auth.login"))

        flash(error, "danger")
        return render_template("register.html", name=name, email=email)

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """User Login route with hashed password verification and role-based redirect."""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        error = None
        if not email or not password:
            error = "Please provide both email and password."
        else:
            db = database.get_db()
            user = db.execute(
                "SELECT * FROM users WHERE LOWER(email) = ?", (email,)
            ).fetchone()

            if user is None or not check_password_hash(user["password"], password):
                error = "Invalid email or password. Please try again."

        if error is None:
            # Create session and store user details
            session.clear()
            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["email"] = user["email"]
            session["role"] = user["role"]

            flash(f"Welcome back, {user['name']}!", "success")

            # Role-based redirection
            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("citizen_dashboard"))

        flash(error, "danger")
        return render_template("login.html", email=email)

    return render_template("login.html")


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Logs out user by clearing the session and redirecting to the home page."""
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect(url_for("index"))
