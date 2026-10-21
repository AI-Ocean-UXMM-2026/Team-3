# Database reconciliation

The mature SQLAlchemy schema and migrations 0001?0003 remain authoritative. ZLH adds only
0004_workflow_routes, down_revision 0003_rider_copilot: a workflow_routes table with UUID,
rider FK, JSON/JSONB aggregate data and optimistic version. Existing user/order/buyer/rider/
event tables and exact COD money types are unchanged. Parcel context lives in existing
order parsing_metadata; no destructive record conversion was performed.

Integrated storage is backend/data/integrated-workspaces/local/sandbox.sqlite3 by default,
separate from normal development and temporary dashboard databases. Repeated starts reuse
seeded fictional actor IDs and existing records; no duplicate starter riders are created.
Persistent reset is disabled. --temporary uses a generated, automatically cleaned test DB.
Only simple --state labels are accepted, never arbitrary DB URLs or file deletion targets.

Tests cover fresh migrations, schema/metadata drift, legacy round trip, FK/rollback,
atomic route preparation, independent connection and a complete app restart. Native buyer
capabilities survive restart; verification sessions intentionally need re-establishment.
Real PostgreSQL connection/locking behavior remains unverified. Offline compilation is
only schema compatibility evidence, not production PostgreSQL validation. Downgrades were
limited to existing isolated tests; no developer database was upgraded or deleted.
