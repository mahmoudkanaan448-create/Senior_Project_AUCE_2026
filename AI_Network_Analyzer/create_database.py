"""
Initialize the database and seed default data.

Creates all tables, seeds the admin user and default settings.
Run once before starting the server: python create_database.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from database.database import init_db, SessionLocal
from database.queries import get_user_by_username, create_user, set_setting
from api.authentication import hash_password


def main():
    """Create tables and seed admin user plus default settings."""
    print("Initializing database...")
    init_db()
    print("Database tables created successfully.")

    db = SessionLocal()
    try:
        if not get_user_by_username(db, "admin"):
            create_user(
                db,
                full_name="System Administrator",
                username="admin",
                email="admin@auce.edu.lb",
                password_hash=hash_password("admin123"),
                role="Administrator",
            )
            print("Default admin user created (admin / admin123)")
        else:
            print("Admin user already exists.")

        set_setting(db, "refresh_rate", "5")
        set_setting(db, "confidence_threshold", "50")
        set_setting(db, "threat_block_threshold", "7")
        set_setting(db, "email_alerts", "0")
        set_setting(db, "response_mode", "automatic")
        set_setting(db, "retention_days", "30")
        print("Default settings configured (Telegram only, no email).")
    finally:
        db.close()

    try:
        from ops.bootstrap import bootstrap
        bootstrap()
        print("SOC defaults bootstrapped (sensor, localhost allowlist, temp-block expiry).")
    except Exception as exc:
        print(f"Bootstrap skipped: {exc}")

    print("\nDatabase initialization complete!")
    print("You can now run the system:")
    print("  Backend:   python main.py")
    print("  Dashboard: streamlit run dashboard/home.py")


if __name__ == "__main__":
    main()
