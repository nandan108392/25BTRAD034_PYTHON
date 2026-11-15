#!/usr/bin/env python3
"""
CityOS Admin Account Recovery & Credential Reset Utility
=========================================================
Secure one-time administrative credential reset tool.

Features:
- Locates existing SQLite database (instance/cityos.db or DATABASE_PATH).
- Identifies existing administrator accounts.
- Prompts securely for email and password using hidden terminal input (getpass).
- Validates password length and confirmation.
- Hashes password using application's native Werkzeug password hashing algorithm (scrypt).
- Updates existing admin record in-place without creating duplicate accounts.
- Preserves all existing reports, users, notifications, and operational records.
- Formally verifies administrator role and password hash validity before completion.
- Never prints passwords or secret hashes to terminal output.
"""

import os
import sys
import re
import sqlite3
import getpass
import argparse
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# Regular expression pattern for basic email validation (matching auth.py)
EMAIL_REGEX = r"^[\w\.-]+@[\w\.-]+\.\w+$"

# Minimum password length enforced for administrator security
MIN_ADMIN_PASSWORD_LENGTH = 8


def find_database_path():
    """
    Locates the CityOS SQLite database path from environment or default locations.
    """
    load_dotenv()
    
    # 1. Check environment variables
    env_db = os.environ.get("DATABASE_PATH") or os.environ.get("DATABASE")
    if env_db and os.path.exists(env_db):
        return os.path.abspath(env_db)

    # 2. Check standard instance directory
    base_dir = os.path.dirname(os.path.abspath(__file__))
    instance_db = os.path.join(base_dir, "instance", "cityos.db")
    if os.path.exists(instance_db):
        return instance_db

    # 3. Check root directory
    root_db = os.path.join(base_dir, "cityos.db")
    if os.path.exists(root_db):
        return root_db

    # Default to instance/cityos.db even if not yet created
    return instance_db


def get_db_connection(db_path):
    """
    Establishes a connection to the SQLite database with row factory and foreign keys.
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file not found at: {db_path}")

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def list_admin_accounts(conn):
    """
    Retrieves all accounts with administrator privileges.
    """
    cursor = conn.execute(
        "SELECT id, name, email, role, created_at FROM users WHERE role = 'admin' ORDER BY id ASC"
    )
    return cursor.fetchall()


def prompt_email(current_email):
    """
    Prompts the user for a new or confirmed admin email address.
    """
    while True:
        prompt_text = f"Admin Email [{current_email}]: " if current_email else "Admin Email: "
        try:
            entered = input(prompt_text).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled by user.")
            sys.exit(1)

        if not entered and current_email:
            return current_email
        elif not entered:
            print("  [!] Email address cannot be empty.")
            continue

        if not re.match(EMAIL_REGEX, entered):
            print("  [!] Please enter a valid email address (e.g. admin@cityos.com).")
            continue

        return entered


def prompt_password():
    """
    Securely prompts for a new password and confirmation without echoing characters.
    """
    while True:
        try:
            pwd1 = getpass.getpass("New Admin Password (min 8 chars): ")
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled by user.")
            sys.exit(1)

        if len(pwd1) < MIN_ADMIN_PASSWORD_LENGTH:
            print(f"  [!] Password must be at least {MIN_ADMIN_PASSWORD_LENGTH} characters long.")
            continue

        try:
            pwd2 = getpass.getpass("Confirm New Admin Password: ")
        except (KeyboardInterrupt, EOFError):
            print("\nOperation cancelled by user.")
            sys.exit(1)

        if pwd1 != pwd2:
            print("  [!] Passwords do not match. Please try again.\n")
            continue

        return pwd1


def reset_admin_account(db_path, target_id, new_email, new_password, new_name=None):
    """
    Updates the specified admin account in-place with a secure Werkzeug hash.
    Verifies that the account retains role='admin' and credentials verify properly.
    """
    conn = get_db_connection(db_path)
    try:
        # Check if email is already taken by a different user
        existing = conn.execute(
            "SELECT id FROM users WHERE LOWER(email) = ? AND id != ?",
            (new_email.lower(), target_id),
        ).fetchone()

        if existing:
            raise ValueError(
                f"Email '{new_email}' is already registered to user ID #{existing['id']}."
            )

        # Hash password using Werkzeug's default algorithm (scrypt)
        hashed_password = generate_password_hash(new_password)

        if new_name:
            conn.execute(
                """
                UPDATE users
                SET name = ?, email = ?, password = ?, role = 'admin'
                WHERE id = ?
                """,
                (new_name, new_email.lower(), hashed_password, target_id),
            )
        else:
            conn.execute(
                """
                UPDATE users
                SET email = ?, password = ?, role = 'admin'
                WHERE id = ?
                """,
                (new_email.lower(), hashed_password, target_id),
            )

        conn.commit()

        # Formal Verification Step
        verified_user = conn.execute(
            "SELECT id, name, email, password, role FROM users WHERE id = ?",
            (target_id,),
        ).fetchone()

        if verified_user is None:
            raise RuntimeError(f"Verification failed: User #{target_id} not found after update.")

        if verified_user["role"] != "admin":
            raise RuntimeError(f"Verification failed: User #{target_id} role is '{verified_user['role']}', expected 'admin'.")

        if verified_user["email"].lower() != new_email.lower():
            raise RuntimeError("Verification failed: Email does not match updated value.")

        if not check_password_hash(verified_user["password"], new_password):
            raise RuntimeError("Verification failed: Password hash verification test failed.")

        return dict(verified_user)

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="CityOS Secure Administrator Credential Reset Utility"
    )
    parser.add_argument(
        "--db",
        dest="db_path",
        help="Optional path to SQLite database file (defaults to auto-detected cityos.db)",
    )
    parser.add_argument(
        "--email",
        dest="email",
        help="Non-interactive admin email (for automated workflows / CI)",
    )
    parser.add_argument(
        "--password",
        dest="password",
        help="Non-interactive admin password (for automated workflows / CI)",
    )
    parser.add_argument(
        "--id",
        dest="user_id",
        type=int,
        help="Target administrator user ID to update",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("      CityOS Secure Administrator Credential Reset      ")
    print("=" * 60)

    # 1. Locate Database
    db_path = args.db_path or find_database_path()
    print(f"[*] Database location: {db_path}")

    if not os.path.exists(db_path):
        print(f"[!] Error: Database file does not exist at '{db_path}'.")
        print("    Please run the CityOS application once or check the path.")
        sys.exit(1)

    conn = get_db_connection(db_path)

    # 2. List Administrator Accounts
    admin_users = list_admin_accounts(conn)
    conn.close()

    if not admin_users:
        print("[!] No administrator accounts currently found in the database.")
        print("    Looking for existing accounts to promote or seed...")
        conn = get_db_connection(db_path)
        all_users = conn.execute("SELECT id, name, email, role FROM users LIMIT 5").fetchall()
        conn.close()
        if all_users:
            print("    Existing accounts found:")
            for u in all_users:
                print(f"      - ID #{u['id']}: {u['name']} ({u['email']}, role: {u['role']})")
            target_id = int(input("    Enter User ID to promote to administrator: ").strip())
            current_email = ""
            current_name = "System Admin"
        else:
            print("    Database contains no users. Please run the application to seed default tables.")
            sys.exit(1)
    else:
        print(f"[*] Found {len(admin_users)} existing administrator account(s):")
        for idx, u in enumerate(admin_users, start=1):
            print(f"    [{idx}] ID #{u['id']}: {u['name']} <{u['email']}> (Role: {u['role']})")

        # Select target admin account
        if args.user_id:
            matching = [u for u in admin_users if u["id"] == args.user_id]
            if not matching:
                print(f"[!] Specified User ID #{args.user_id} is not an administrator.")
                sys.exit(1)
            target_user = matching[0]
        elif len(admin_users) == 1:
            target_user = admin_users[0]
            print(f"\n[*] Selected administrator account #{target_user['id']} ({target_user['email']}).")
        else:
            try:
                choice = input(f"\nSelect administrator account to update (1-{len(admin_users)}) [1]: ").strip()
                if not choice:
                    selected_idx = 0
                else:
                    selected_idx = int(choice) - 1
                target_user = admin_users[selected_idx]
            except (ValueError, IndexError):
                print("[!] Invalid selection.")
                sys.exit(1)
            except (KeyboardInterrupt, EOFError):
                print("\nOperation cancelled.")
                sys.exit(1)

        target_id = target_user["id"]
        current_email = target_user["email"]
        current_name = target_user["name"]

    # 3. Collect credentials
    if args.email:
        new_email = args.email.strip().lower()
    else:
        print("\n--- Credential Configuration ---")
        new_email = prompt_email(current_email)

    if args.password:
        new_password = args.password
    else:
        new_password = prompt_password()

    # 4. Perform update & verification
    print("\n[*] Updating administrator credentials in database...")
    try:
        verified_user = reset_admin_account(
            db_path=db_path,
            target_id=target_id,
            new_email=new_email,
            new_password=new_password,
            new_name=current_name,
        )

        print("\n" + "=" * 60)
        print("🎉 SUCCESS: Administrator credentials successfully updated!")
        print("=" * 60)
        print(f"  Account ID:    #{verified_user['id']}")
        print(f"  Admin Name:    {verified_user['name']}")
        print(f"  Admin Email:   {verified_user['email']}")
        print(f"  Account Role:  {verified_user['role']} (Verified: Admin Privileges Retained)")
        print(f"  Password Hash: [Werkzeug scrypt - Securely Stored & Verified]")
        print("=" * 60)
        print("\nAll civic reports, database tables, and system records have been preserved.")
        print(f"You can now log in at: http://127.0.0.1:5000/login\n")

    except Exception as e:
        print(f"\n[!] Failed to reset admin credentials: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
