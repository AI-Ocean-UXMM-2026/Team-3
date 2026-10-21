# Concurrency verification

Five new bounded competing-operation/availability tests plus one malformed-search test
were added in `test_overnight_concurrency.py`. They passed along with existing concurrency
and optimistic locking tests.

| New scenario | Observed invariant |
| --- | --- |
| Two dispatchers assign one order to different riders | Responses 201/409; one assignment and one assignment event |
| Two successful verifications | Both return 200, only latest session works; other returns 401 |
| Buyer pin races readiness | Responses 200/409; either pending review + NEEDS_REVIEW, or ready with no pending request; no submitted pin silently applied |
| Distinct completion request UUIDs race | Responses 200/404; only one completion event |
| Assigned rider becomes OFFLINE | Queue retains stop, START returns 409, status remains ASSIGNED |

Existing tests additionally cover concurrent failed verification budget, same-UUID buyer
proposal replay, rider queue capacity, same-UUID completion replay and stale ORM versions.
New TestClient competitors use independent clients/sessions and a two-thread bounded pool.
Additionally, `scripts/verify_process_race.py` ran two independent OS HTTP client processes
against one isolated API worker. Both submitted the same expected order version: responses
were 200/409, persisted version was 2 and exactly creation plus one correction event existed
after reopening storage. Evidence: [process_race.json](process_race.json). Credentials were
passed over child stdin and never printed or placed in command-line arguments.

These are not PostgreSQL or distributed stress tests. Multiple API worker processes against
PostgreSQL and sustained contention remain follow-up work. The ordinary HTTP demo uses three
role processes sharing its isolated SQLite database.

No lost update or duplicate completion was observed in these bounded scenarios. Existing
locking/version mechanisms were retained; no distributed infrastructure was introduced.
