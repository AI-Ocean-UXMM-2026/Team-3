"""Operator-only account provisioning; Supabase user UUID must be supplied explicitly."""

import argparse
from uuid import UUID

from sqlalchemy import select

from app.core.config import Settings
from app.db.models import User
from app.db.rider_models import RiderProfile
from app.db.session import Database
from app.domain.lifecycle import UserRole


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auth-user-id", type=UUID, required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--role", choices=["Dispatcher", "Rider"], required=True)
    args = parser.parse_args()
    if not 1 <= len(args.name) <= 200 or "@" not in args.email or len(args.email) > 254:
        parser.error("Provide a name and valid account email")
    settings = Settings()
    database = Database(settings.database_url.get_secret_value())
    try:
        with database.sessions.begin() as session:
            if session.get(User, args.auth_user_id) or session.scalar(
                select(User).where(User.email == args.email)
            ):
                parser.error("Account already exists; refusing to overwrite its identity or role")
            session.add(
                User(
                    id=args.auth_user_id, name=args.name, email=args.email, role=UserRole(args.role)
                )
            )
            session.flush()
            if args.role == "Rider":
                session.add(RiderProfile(id=args.auth_user_id, operational_status="OFFLINE"))
        print("Account provisioned. No password or Supabase secret was stored.")
    finally:
        database.dispose()


if __name__ == "__main__":
    main()
