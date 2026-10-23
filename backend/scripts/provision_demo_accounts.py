import json
import uuid
from app.core.config import Settings
from app.db.session import Database
from sqlalchemy import text

DEMO_ACCOUNTS = [
    {
        "email": "judge.dispatch@lannpya.dev",
        "password": "JudgeDemo2026!",
        "name": "Judge Dispatch Hub",
        "shop_name": "Judge Dispatch Hub",
        "role": "Dispatcher",
    },
    {
        "email": "judge.rider@lannpya.dev",
        "password": "JudgeDemo2026!",
        "name": "Judge Demo Rider",
        "shop_name": "LannPya Express",
        "role": "Rider",
    },
]

def provision_demo_accounts():
    s = Settings()
    db = Database(s.database_url.get_secret_value())
    with db.sessions.begin() as session:
        for acc in DEMO_ACCOUNTS:
            email = acc["email"]
            pwd = acc["password"]
            name = acc["name"]
            role = acc["role"]
            shop_name = acc["shop_name"]

            existing_auth = session.execute(
                text("SELECT id FROM auth.users WHERE email = :email"),
                {"email": email}
            ).scalar()

            if existing_auth:
                uid = existing_auth
                session.execute(
                    text("""
                        UPDATE auth.users
                        SET encrypted_password = crypt(:pwd, gen_salt('bf', 10)),
                            email_confirmed_at = COALESCE(email_confirmed_at, NOW()),
                            confirmation_token = COALESCE(confirmation_token, ''),
                            recovery_token = COALESCE(recovery_token, ''),
                            email_change_token_new = COALESCE(email_change_token_new, ''),
                            email_change = COALESCE(email_change, ''),
                            phone_change = COALESCE(phone_change, ''),
                            phone_change_token = COALESCE(phone_change_token, ''),
                            email_change_token_current = COALESCE(email_change_token_current, ''),
                            reauthentication_token = COALESCE(reauthentication_token, ''),
                            updated_at = NOW()
                        WHERE id = :id
                    """),
                    {"pwd": pwd, "id": uid}
                )
                print(f"Updated auth password for {email} ({uid})")
            else:
                uid = uuid.uuid4()
                user_meta = json.dumps({
                    "sub": str(uid),
                    "name": name,
                    "shop_name": shop_name,
                    "role": role,
                    "email": email,
                    "email_verified": True,
                    "phone_verified": False,
                })
                app_meta = json.dumps({
                    "provider": "email",
                    "providers": ["email"]
                })

                session.execute(
                    text("""
                        INSERT INTO auth.users (
                            id, instance_id, aud, role, email, encrypted_password,
                            email_confirmed_at, confirmation_token, recovery_token,
                            email_change_token_new, email_change, phone_change, phone_change_token,
                            email_change_token_current, reauthentication_token,
                            raw_app_meta_data, raw_user_meta_data,
                            created_at, updated_at
                        )
                        VALUES (
                            :id, CAST('00000000-0000-0000-0000-000000000000' AS uuid), 'authenticated', 'authenticated',
                            :email, crypt(:pwd, gen_salt('bf', 10)),
                            NOW(), '', '', '', '', '', '', '', '',
                            CAST(:app_meta AS jsonb), CAST(:user_meta AS jsonb),
                            NOW(), NOW()
                        )
                    """),
                    {
                        "id": uid,
                        "email": email,
                        "pwd": pwd,
                        "app_meta": app_meta,
                        "user_meta": user_meta,
                    }
                )

                identity_id = uuid.uuid4()
                session.execute(
                    text("""
                        INSERT INTO auth.identities (
                            id, user_id, identity_data, provider, provider_id,
                            last_sign_in_at, created_at, updated_at
                        )
                        VALUES (
                            :id, :user_id, CAST(:user_meta AS jsonb), 'email', :user_id_str,
                            NOW(), NOW(), NOW()
                        )
                    """),
                    {
                        "id": identity_id,
                        "user_id": uid,
                        "user_id_str": str(uid),
                        "user_meta": user_meta,
                    }
                )
                print(f"Created auth user and identity for {email} ({uid})")

            # Ensure public.users entry
            existing_pub = session.execute(
                text("SELECT id FROM public.users WHERE id = :id"),
                {"id": uid}
            ).scalar()

            if existing_pub:
                session.execute(
                    text("""
                        UPDATE public.users
                        SET name = :name, email = :email, role = :role, updated_at = NOW()
                        WHERE id = :id
                    """),
                    {"id": uid, "name": name, "email": email, "role": role}
                )
                print(f"Updated public.users for {email} ({role})")
            else:
                session.execute(
                    text("""
                        INSERT INTO public.users (id, name, email, role, created_at, updated_at)
                        VALUES (:id, :name, :email, :role, NOW(), NOW())
                    """),
                    {"id": uid, "name": name, "email": email, "role": role}
                )
                print(f"Inserted public.users for {email} ({role})")

        print("\nAll public.users:")
        users = session.execute(
            text("SELECT id, name, email, role FROM public.users ORDER BY created_at ASC")
        ).mappings().all()
        for u in users:
            print(dict(u))

if __name__ == "__main__":
    provision_demo_accounts()
