# Failure and recovery verification

| Fault | Evidence/result |
| --- | --- |
| AI disabled/missing unsupported provider config | Existing config/adapter tests: disabled assistance retains rules; unknown config fails startup clearly |
| AI timeout/rate limit/malformed/ungrounded JSON | Hybrid tests retain validated deterministic fields and explicit availability; external adapters remain blocked |
| Encoding detector unavailable | New injected exception test: 200 parse, original input and phone retained, encoding uncertain/RED, private exception absent from logs |
| Local encoding conversion failure | Existing test retains original, warning and review; no pretending conversion succeeded |
| DB unavailable/unmigrated/commit failure | Existing DB/rollback tests: sanitized 503 or conflict, no partial event/order/assignment |
| Expired/revoked/locked buyer credential | Existing buyer tests deny change, maintain state and lockout semantics |
| Invalid environment/origin/timeout values | Existing settings validation; production APIs closed |
| Missing pin / optional customer fields | Existing queue/card tests use null and navigation not ready; no fabricated coordinates/branding |
| NUL or oversized/blank input | 422 rejection before persistent operation; original valid whitespace remains preserved |

No real AI API or external map service was activated. Errors do not silently switch to fake
success. The frontend must distinguish connection error from explicit demo simulation.
