import datetime
import json
import uuid
from sqlalchemy import text
from app.core.config import Settings
from app.db.session import Database

def provision_rider():
    s = Settings()
    db = Database(s.database_url.get_secret_value())
    rider_id = uuid.UUID("cbf94be5-6e94-4346-bc74-6b2d36012ead")
    email = "rider.aung@lannpya.dev"

    with db.sessions.begin() as session:
        user_row = session.execute(
            text("SELECT instance_id, encrypted_password FROM auth.users ORDER BY created_at ASC LIMIT 1")
        ).mappings().one()
        instance_id = user_row["instance_id"]
        pwd_hash = user_row["encrypted_password"]
        now = datetime.datetime.now(datetime.timezone.utc)

        existing = session.execute(
            text("SELECT id FROM auth.users WHERE id=:id"), {"id": rider_id}
        ).scalar()

        if not existing:
            raw_meta = json.dumps({
                "sub": str(rider_id),
                "email": email,
                "name": "Ko Aung",
                "email_verified": True,
                "phone_verified": False
            })
            raw_app_meta = json.dumps({"provider": "email", "providers": ["email"]})

            session.execute(
                text("""
                    INSERT INTO auth.users (
                        id, instance_id, aud, role, email, encrypted_password, email_confirmed_at,
                        raw_app_meta_data, raw_user_meta_data, created_at, updated_at, is_sso_user, is_anonymous,
                        confirmation_token, recovery_token, email_change_token_new, email_change, phone_change, phone_change_token,
                        reauthentication_token, email_change_token_current
                    ) VALUES (
                        :id, :instance_id, 'authenticated', 'authenticated', :email, :pwd, :now,
                        CAST(:raw_app_meta AS jsonb), CAST(:raw_meta AS jsonb), :now, :now, false, false,
                        '', '', '', '', '', '', '', ''
                    )
                """),
                {
                    "id": rider_id,
                    "instance_id": instance_id,
                    "email": email,
                    "pwd": pwd_hash,
                    "now": now,
                    "raw_app_meta": raw_app_meta,
                    "raw_meta": raw_meta,
                }
            )

            identity_id = uuid.uuid4()
            session.execute(
                text("""
                    INSERT INTO auth.identities (
                        id, provider_id, user_id, identity_data, provider, last_sign_in_at, created_at, updated_at
                    ) VALUES (
                        :id, :provider_id, :user_id, CAST(:raw_meta AS jsonb), 'email', :now, :now, :now
                    )
                """),
                {
                    "id": identity_id,
                    "provider_id": str(rider_id),
                    "user_id": rider_id,
                    "raw_meta": raw_meta,
                    "now": now,
                }
            )
            print("Successfully inserted into auth.users and auth.identities")
        else:
            print("Rider already exists in auth.users - fixing any null string columns")
            session.execute(
                text("""
                    UPDATE auth.users SET
                        confirmation_token = COALESCE(confirmation_token, ''),
                        recovery_token = COALESCE(recovery_token, ''),
                        email_change_token_new = COALESCE(email_change_token_new, ''),
                        email_change = COALESCE(email_change, ''),
                        phone_change = COALESCE(phone_change, ''),
                        phone_change_token = COALESCE(phone_change_token, ''),
                        reauthentication_token = COALESCE(reauthentication_token, ''),
                        email_change_token_current = COALESCE(email_change_token_current, '')
                    WHERE id = :id
                """),
                {"id": rider_id}
            )

        session.execute(
            text("UPDATE public.users SET email=:email, name='Ko Aung' WHERE id=:id"),
            {"email": email, "id": rider_id}
        )
        print("Updated public.users for Ko Aung")

if __name__ == "__main__":
    provision_rider()
