-- Run after Alembic migrations as the database owner, before serving the app.
-- This backend uses SQLAlchemy credentials; browsers use only the authorized HTTP API.
-- Restrict only LannPya tables. Do not change auth.users or unrelated project tables.
DO $$
DECLARE
  table_name text;
  browser_role text;
BEGIN
  FOREACH table_name IN ARRAY ARRAY[
    'users', 'orders', 'delivery_events', 'confirmation_links', 'buyer_sessions',
    'buyer_requests', 'buyer_rate_limits', 'location_references', 'rider_profiles',
    'delivery_assignments', 'rider_action_receipts', 'workflow_routes',
    'routing_plans', 'routing_rate_limits', 'alembic_version'
  ] LOOP
    IF to_regclass(format('public.%I', table_name)) IS NOT NULL THEN
      EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', table_name);
      EXECUTE format('REVOKE ALL ON TABLE public.%I FROM PUBLIC', table_name);
      FOREACH browser_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = browser_role) THEN
          EXECUTE format('REVOKE ALL ON TABLE public.%I FROM %I', table_name, browser_role);
        END IF;
      END LOOP;
    END IF;
  END LOOP;
END $$;
