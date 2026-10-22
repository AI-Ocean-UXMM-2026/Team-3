# Supabase PostgreSQL Setup Guide — LannPya AI (လမ်းပြ)

This guide walks through setting up an optional hosted **Supabase PostgreSQL** database from scratch for the LannPya AI logistics platform.

---

## 1. Project Creation (Free Tier)

1. Log in to [Supabase](https://supabase.com/).
2. Click **New Project** and select your Organization.
3. Fill in the project configuration:
   * **Project Name**: `lannpya-ai-dev` (or `lannpya-ai-staging`)
   * **Database Password**: Generate a secure 24+ character password.
     > [!IMPORTANT]
     > Store this password in your password manager. Never paste passwords directly into team chat or commit them to Git.
     > If your password contains special characters such as `@`, `:`, or `/`, they must be URL-encoded (e.g., `@` becomes `%40`) in the database URL.
   * **Region**: Choose **Singapore (`ap-southeast-1`)** for minimal network latency from Myanmar.
   * **Pricing Plan**: **Free Plan** ($0/month). Do not select any paid tiers.
4. Click **Create new project** and wait 1–2 minutes for provisioning.

---

## 2. Choosing the PostgreSQL Connection Method

Supabase provides two distinct connection strings in **Project Settings → Database → Connection string**:

### Method A: Connection Pooler (Transaction Mode, Port 6543) — Recommended for Runtime
Best for FastAPI web serving, multi-worker processes, and high-concurrency requests.
```text
postgresql+psycopg://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require
```

### Method B: Direct Connection (Session Mode, Port 5432) — Recommended for Migrations
Direct access to PostgreSQL. Required when running schema migrations or DDL operations that cannot execute inside transaction poolers.
```text
postgresql+psycopg://postgres:[PASSWORD]@db.[PROJECT_REF].supabase.co:5432/postgres?sslmode=require
```

> [!NOTE]
> LannPya AI's `Database` engine automatically normalizes `postgres://` or `postgresql://` URIs to the modern `postgresql+psycopg` dialect driver.

---

## 3. Environment Variable Configuration

Add the connection URL to your uncommitted `backend/.env` file:

```bash
# In backend/.env:
LANNPYA_ORDER_MANAGEMENT_ENABLED=true
LANNPYA_ENVIRONMENT=local

# Connection Pooler (Runtime):
LANNPYA_DATABASE_URL=postgresql+psycopg://postgres.[PROJECT_REF]:[YOUR_PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require

# Standard DATABASE_URL is also supported as a seamless fallback alias:
# DATABASE_URL=postgresql+psycopg://...
```

Verify that `backend/.env` is ignored by Git:
```bash
git status --ignored
```
*(Confirms `.env` is listed under ignored files and never tracked).*

---

## 4. Connectivity Validation

Before running any migrations, execute the built-in database validation tool:

```bash
cd backend
.\.venv\Scripts\python.exe scripts/verify_database.py
```

Expected output for an unmigrated database:
```text
============================================================
LannPya AI - Database Connectivity & Schema Verifier
============================================================
Target URL: postgresql+psycopg://postgres.[REF]:***@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres?sslmode=require
[+] Engine initialized: postgresql (driver: psycopg)
[+] Ping successful (SELECT 1) in 48.20ms
[+] PostgreSQL server version: PostgreSQL 15.x ...
[+] Alembic migration repository head: 0005_routing_plans
[!] Migration status: UNMIGRATED (alembic_version table not found)
    Run 'alembic upgrade head' or call upgrade_database(db).
[+] Transaction begin and rollback test passed cleanly.
============================================================
[+] All database validation checks passed successfully.
============================================================
```

---

## 5. Applying Alembic Migrations

Once connectivity is verified, apply the 5 canonical schema revisions to head:

```bash
cd backend
.\.venv\Scripts\alembic.exe upgrade head
```

This applies:
1. `0001_order_management` — Users, Orders, Delivery Events, and Status Check Constraints.
2. `0002_buyer_confirmation` — Confirmation Links, Sessions, Location References, Buyer Requests.
3. `0003_rider_copilot` — Rider Profiles, Delivery Assignments, Idempotent Action Receipts.
4. `0004_workflow_routes` — Route & Cash aggregates.
5. `0005_routing_plans` — Routing Plans and Rate Limits.

Re-run the verification tool to confirm all 12 canonical tables are active:
```bash
.\.venv\Scripts\python.exe scripts/verify_database.py
```
Status will show: `[+] Migration status: UP TO DATE (matches head)`.

---

## 6. Local Testing Fallback

To switch back to isolated local SQLite at any time, simply remove or comment out `LANNPYA_DATABASE_URL` in `backend/.env`. The application defaults automatically to `sqlite+pysqlite:///./data/lannpya_dev.sqlite3`.
