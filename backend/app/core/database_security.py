"""The browser must never bypass API authorization through Supabase's Data API."""

from sqlalchemy import text


def check_browser_grants(database):
    if database.engine.dialect.name != "postgresql":
        return
    # Database roles are server-defined. No identifiers or claims come from a request.
    with database.engine.connect() as connection:
        exposed = connection.execute(
            text("""
            SELECT c.relname
            FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            CROSS JOIN pg_roles r
            WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
              AND r.rolname IN ('anon', 'authenticated')
              AND c.relname IN (
                'users', 'orders', 'delivery_events', 'confirmation_links', 'buyer_sessions',
                'buyer_requests', 'buyer_rate_limits', 'location_references', 'rider_profiles',
                'delivery_assignments', 'rider_action_receipts', 'workflow_routes',
                'routing_plans', 'routing_rate_limits', 'alembic_version')
              AND has_table_privilege(r.oid, c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE')
            LIMIT 1
        """)
        ).first()
    if exposed:
        raise ValueError(
            "Browser roles can access application tables directly. "
            "Apply scripts/secure_supabase_tables.sql before starting the secure workspace."
        )
