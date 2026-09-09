---
name: backend-review-loop
description: Verify a backend change by running the service and exercising the touched entrypoint like a real client (route, worker, queue, cron, CLI, RPC), verifying side effects in the DB, queue, cache, and logs, then loop fix and re-check until no blocking issue remains. Checks contract, data integrity, security, performance, and resilience; scores issues on impact and likelihood; routes blocking fixes to the executor. Use on /build:backend-review-loop, or as the verification step after building or fixing any backend feature.
argument-hint: "[entrypoints] [executor=agy|codex:m:e|claude:m]"
---

# Backend Review Loop

The shared loop shape, scoring, and stop policy are in `reference/gate-frame.md`; read it first. This file is the checklist.

<HARD-GATE>
Run the service and exercise the touched entrypoint with real requests, then verify the real side effects (rows, messages, cache entries, files, logs). Reading the handler does not count. A passing suite does not count on its own. Provision whatever tooling you need yourself; a credential only the user holds makes the gate `not runnable`, never a question.
</HARD-GATE>

## Scope

The entrypoints the item touched and the state they read and write. Not the whole service unless the whole service changed.

## Each cycle

1. **Boot** the service and its real dependencies (database, cache, broker), run migrations, load config, seed data. Infer commands from the package manifest, Makefile, compose file, README. Confirm health before touching anything.
2. **Exercise like a real client:** happy path with valid input (status, body shape and values, headers); bad input (missing, wrong type, malformed, oversized, empty) must return a clean 4xx with a useful error, never a 500; boundaries (nulls, empty, unicode, max lengths, pagination limits).
3. **Verify side effects, not just the response:** after every write, look. The row created, updated, or deleted with the right values; the event actually published; the cache invalidated; the file, email, or webhook actually written or enqueued. A 2xx whose state never landed is impact 3.
4. **Logs, the whole time:** stack traces, unhandled exceptions, error-level logs, slow-query warnings, each tied to the request that caused it.
5. **Data integrity:** idempotency (replay the same request, no double write); transactions (force a mid-operation failure, state rolls back clean); concurrency (two simultaneous requests, no race or lost update); constraints actually enforced. When the diff touches schema, run the migration forward and roll it back on realistic data.
6. **Contract:** response matches the documented schema; status codes semantically right; pagination, filtering, sorting work; content-type and headers correct.
7. **Security:** authz boundary and IDOR (another user's resource by changing an id); no secrets, stack traces, or other users' data in responses or logs; no mass assignment.
8. **Performance:** latency on a realistic payload; N+1 queries; pool exhaustion, timeouts, runaway memory.
9. **Resilience:** kill a downstream dependency; it degrades with a timeout or clean error, never hangs or crashes.
10. **Score** every issue: impact (3 crash, corruption, a write that does not persist, auth bypass, data leak, a migration that destroys or locks data; 2 wrong error code, missing validation lets bad data in, a side effect silently skipped, an N+1 that makes it unusable; 1 inconsistent error format, missing pagination, slow but works) times likelihood (3 ordinary traffic; 2 unusual but real; 1 contrived). Blocking at 6 or more.
11. **Route** blocking issues to the executor as a fix brief pointing at `reference/executor-contract.md`; never edit on the main thread. Then re-run from step 1 against the touched surface.

## Exit

All checks ran against the current state, and no blocking issue remains. Non-blocking issues are reported, not chased. Log the row per `gate-frame.md`. Report: what you exercised, what you verified in state, what was routed and fixed, what remains.
