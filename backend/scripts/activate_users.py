import datetime
import json
import uuid
from sqlalchemy import text
from app.core.config import Settings
from app.db.session import Database

def activate_all():
    s = Settings()
    db = Database(s.database_url.get_secret_value())
    with db.sessions.begin() as session:
        auth_users = session.execute(
            text("SELECT id, email, email_confirmed_at, raw_user_meta_data FROM auth.users")
        ).mappings().all()

        for au in auth_users:
            uid = au["id"]
            email = au["email"]
            existing = session.execute(
                text("SELECT id FROM public.users WHERE id = :id"), {"id": uid}
            ).scalar()

            if not existing and au["email_confirmed_at"]:
                meta = au["raw_user_meta_data"] or {}
                name = (
                    meta.get("shop_name")
                    or meta.get("shop")
                    or meta.get("name")
                    or (email.split("@")[0] if email else "User")
                )
                role = "Rider" if (meta.get("role") == "Rider") else "Dispatcher"
                session.execute(
                    text("""
                        INSERT INTO public.users (id, name, email, role, created_at, updated_at)
                        VALUES (:id, :name, :email, :role, NOW(), NOW())
                    """),
                    {"id": uid, "name": name, "email": email, "role": role}
                )
                print(f"Activated {email} ({name}) as {role}")

        print("\nCurrent public.users:")
        users = session.execute(
            text("SELECT id, name, email, role FROM public.users")
        ).mappings().all()
        for u in users:
            print(dict(u))

if __name__ == "__main__":
    activate_all()
