# Local security review

Reviewed API dependencies, tokens, role/merchant/rider scoping, buyer capabilities, CORS,
errors and logging. Existing security tests and the new adversarial/cross-request checks
passed in the 749-test run. No external systems were probed.

- Management/rider routes require actual loopback peer, enabled local/test config, private
  development token and server-bound actor. Production remains closed. Arbitrary client
  identity headers cannot change actor. Buyer credentials cannot access dispatcher APIs.
- Link and session secrets use cryptographic random tokens; only digests are stored.
  Generation rotation/revocation/expiry prevents old session reuse. Concurrent successful
  verification yielded two responses but only the latest credential authorized details.
- Three failed valid guesses lock the link across sessions/concurrent attempts. Persisted
  rate limits ignore spoofed forwarded-IP headers. Last four plus link is a light check,
  not proof of phone ownership.
- Buyer pre-verification card excludes name, full phone, address, GPS and private notes.
  Error payloads/logs suppress input values and private exception text. New detector-failure
  test verifies no exception message leakage.
- NUL input/search safeguards reject malformed data before persistence/query. Other ordinary
  Unicode/newlines/tabs are preserved; no arbitrary address stripping was introduced.
- CORS uses configured exact origins and no cookie credentials. Private access must not be
  embedded in a Vite bundle or public static JS. Keep local runtime tokens in memory only.

Git tracking/working changes were checked against private runtime values and common key
patterns without printing values. Ignored `.env`, venv, databases, logs and demo credentials
remain excluded. Any future secret discovery needs revocation, not only file deletion.

**Public demo blocker:** production identity/tenant authorization, HTTPS/proxy/log/retention
controls and operational validation are not implemented. Do not expose local tokens through
a public tunnel or unauthenticated BFF. This review is bounded, not a penetration-test
certificate or complete dependency-advisory audit.
