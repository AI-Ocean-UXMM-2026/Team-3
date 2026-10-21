# Database integrity evidence

All destructive and failure tests used isolated SQLite databases. Production PostgreSQL was
not connected. No normal developer database was downgraded, reset or deleted.

The existing migration/database tests passed in the full suite: fresh Alembic upgrade,
metadata drift comparison, idempotent upgrade, isolated empty-database downgrade/re-upgrade,
preservation of earlier phase records, foreign keys, coordinate/COD/status constraints,
unique active assignments, transaction rollback and reopen/persistence. Head remains
`0003_rider_copilot`; no migration or table change was needed.

Order correction/status, buyer proposals/review and rider actions use transactions and
optimistic versions/serialized row updates. Tests inject commit/DB failures and assert
neither partial canonical changes nor orphan events/assignments survive. New races confirm
one assignment and one completion event under competing requests.

The HTTP demo stopped its servers and reopened storage: 5 orders, 3 buyer requests,
3 assignments, 4 rider receipts, 32 events and 3 links persisted. Benchmarks created fresh
temporary fixtures of 100/1,000/5,000 orders and disposed/removed only those temp directories.

Known boundaries: order POST has no deduplication/idempotency contract; identical requests
create separate IDs. PostgreSQL offline SQL compilation is covered, but real PostgreSQL
locking, query plans, driver, migrations and deployment remain unverified. SQLite outcomes
must not be treated as proof of production multi-worker database behavior.
