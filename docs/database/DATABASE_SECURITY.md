# Database Security & Privacy Specification — LannPya AI (လမ်းပြ)

This document details the security posture, network isolation, credential protection, and privacy mechanisms implemented for LannPya AI's database layer.

---

## 1. Network Isolation & Credential Protection

### Zero Client Exposure
The frontend client bundle never receives database credentials, connection strings, or service-role keys. All database queries are executed strictly by the backend FastAPI service over authenticated, validated endpoints.

### Pydantic SecretStr Masking
Database URLs are defined as `pydantic.SecretStr` fields:
```python
database_url: SecretStr = Field(
    default=SecretStr("sqlite+pysqlite:///./data/lannpya_dev.sqlite3"),
    validation_alias=AliasChoices("LANNPYA_DATABASE_URL", "DATABASE_URL"),
)
```
Calling `str(settings.database_url)` or logging `settings` displays `**********`, eliminating accidental credential exposure in application logs, error traces, or monitoring streams.

### Transport Layer Security (TLS/SSL)
All hosted PostgreSQL connections mandate SSL encryption:
```text
.../postgres?sslmode=require
```
Ensures in-transit traffic between the FastAPI middleware and Supabase cloud is encrypted against eavesdropping and man-in-the-middle attacks.

---

## 2. Capability-Based Authorization & Lockout Controls

### Buyer Capability Tokens
Instead of granting direct account logins to buyers, the system issues cryptographically secure, single-purpose capability tokens:
* Tokens are hashed using SHA-256 (`token_hash`) before storage; plaintext tokens never exist in the database.
* Access requires passing phone-number verification (last 4 digits matching a salted phone hash).
* **3-Attempt Lockout**: `failed_attempts` is bounded `BETWEEN 0 AND 3`. After 3 failed verification attempts, the link locks immediately (`locked_at = NOW()`), preventing brute-force guessing.

### Rate Limiting Privacy
Rate limiter keys use salted SHA-256 hashes:
```python
key = hashlib.sha256(f"{salt}:{peer}:{scope}:{bucket}".encode()).hexdigest()
```
No plaintext IP addresses are retained in `buyer_rate_limits`, preserving user privacy while maintaining robust DDoS protection.

---

## 3. Financial & Operational Integrity

### Replay & Double-Spend Protection
Rider delivery completions and COD cash handovers require a client-generated UUID `request_id`. The database records each transaction in `rider_action_receipts` with a composite unique index:
```sql
CREATE UNIQUE INDEX ux_rider_action_actor_request ON rider_action_receipts (actor_id, request_id);
```
Network retries or replayed HTTP requests hit this unique constraint and return the previous receipt idempotently rather than recording duplicate cash collections.

### Concurrency Conflicts
Optimistic locking on `Order` and `RiderProfile` prevents race conditions when multiple actors update records simultaneously. Stale updates fail with `StaleDataError` and return an explicit HTTP 409 Conflict.

---

## 4. Git Repository Cleanliness

The repository's `.gitignore` explicitly excludes all credential stores and local databases:
```gitignore
*.sqlite3
.env
.env.*
!.env.example
```
Before committing any changes, the working tree is verified clean to ensure zero secrets enter version control.
