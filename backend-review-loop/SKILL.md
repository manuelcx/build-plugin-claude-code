---
name: backend-review-loop
description: Verify a backend change by actually running the service and exercising it like a real client, then loop fix -> re-review until no Critical or High issues remain. Boots the service and its dependencies, hits the touched entrypoint (route, worker, queue, cron, CLI, RPC) with real requests, verifies side effects in the DB/queue/cache, watches the logs, and checks contract, data integrity, security, performance, and resilience. Use on /backend-review-loop, or as the verification step after building or fixing any backend feature.
---

# Backend Review Loop

Verify a backend change the only honest way: run the service, drive the touched entrypoint with real requests, check what actually happened to the system state, and keep fixing until it holds up.

<HARD-GATE>
You MUST run the service and exercise the touched entrypoint with real requests, then verify the real side effects (DB rows, queue messages, cache, files, logs). Reading the handler and assuming the response or the write "probably works" does NOT count. A passing test suite does NOT count on its own. Set up whatever tooling you need to do this yourself (see Tooling). The only reason to stop is a secret or credential that only the user holds.
</HARD-GATE>

## Tooling

Autonomous workflow: provision whatever you need yourself (a request client, a way to inspect DB/queue/cache state, and log access). The only reason to stop is a secret or credential that only the user holds.

## Scope

Review the entrypoint(s) and flow(s) touched by the work you just did: the route, worker, queue consumer, cron job, CLI command, or RPC/GraphQL method you built or fixed, plus the state they read and write. Not the whole service unless the whole service changed. Normally invoked as the verification step at the end of a build/fix task.

## Run it as a loop

Objective-bound, not time-bound. Run under `/loop` with no interval so it self-paces:

```
/loop /backend-review-loop
```

The Exit Criteria below ARE the loop's objective. Keep iterating until they are met.

## Each cycle

1. **Boot**: start the service AND its real dependencies (DB, cache, broker), run migrations, load env/config, seed data. Infer the start command and deps yourself from package.json / Makefile / docker-compose / README and bring them up. Confirm health/readiness is green before touching anything.
2. **Exercise the entrypoint like a real client**: drive the touched surface for real. Happy path with valid input -> assert status, body shape, body values, headers. Bad input (missing / wrong-type / malformed / oversized / empty) -> must return a clean 4xx with a useful error, never a 500. Boundaries: nulls, empty, unicode, max lengths, pagination limits.
3. **Verify side effects, not just the response**: after every write, go look. DB row created/updated/deleted with the right values; queue/event actually published; cache invalidated; file/email/webhook actually written or enqueued. A 2xx whose state never landed is a Critical bug the response hides.
4. **Watch the logs the whole time**: stack traces, unhandled exceptions, error-level logs, slow-query warnings, each tied to the request that caused it.
5. **Data integrity**: idempotency (replay the same request, no double-write); transactions (force a mid-operation failure, state rolls back clean, not half-written); concurrency (two simultaneous requests, no race or lost update); constraints (unique / FK / not-null actually enforced). When the diff touches schema, run the migration forward AND roll back on realistic data.
6. **Contract correctness**: response matches the documented schema/types; status codes are semantically right (201 create, 204 delete, 404 vs 422); pagination/filtering/sorting actually work; content-type and headers correct.
7. **Security**: authz boundary / IDOR (can one user reach another's resource by changing an id?); no secrets, stack traces, or other users' data leaked in responses or logs; no mass assignment (client can't set fields it shouldn't).
8. **Performance**: latency on a realistic payload; N+1 queries (count SQL per request); pool exhaustion, timeouts, runaway memory.
9. **Resilience**: kill a downstream dependency (DB drops, external API 500s or hangs) -> degrades with a timeout or clean error, does not hang or crash; retries/timeouts behave.
10. **Classify** every issue found: Critical / High / Medium / Low.
11. **Fix all Critical and High**, then re-review from step 1 against the touched surface.

## Severity

- **Critical**: 500/crash, data corruption, a write that doesn't persist, auth bypass, data leak, a migration that destroys or locks data.
- **High**: wrong error code (500 where a 4xx is right), missing validation lets bad data in, a side effect silently skipped, IDOR/authz hole, an N+1 that makes it unusable, secret in logs.
- **Medium**: inconsistent error format, missing pagination, slow-but-works query, noisy error logs.
- **Low**: response field-naming nits, log verbosity, cosmetic polish.

## Exit Criteria

Stop the loop ONLY when both hold:

- All checks ran against the current state of the touched surface, AND
- No Critical or High issues remain.

Medium and Low may remain. Report them, don't block on them.

Then report: what you exercised, what you verified in state, what you fixed, and any Medium/Low left open.

## Stop and ask (only genuine blockers)

This is a long autonomous loop. Provision tooling, infer commands, and seed data yourself; do not stop for setup. Stop ONLY when:

- A secret or credential that only the user holds blocks you from running the service or reaching its state.
- The same Critical/High issue survives 3 fix attempts -> report what you tried, ask.
- A fix needs a product or architecture decision outside this task's scope -> ask.
