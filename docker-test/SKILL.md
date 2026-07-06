---
name: docker-test
description: Pre-deploy smoke test that (A) exercises the real background worker/queue path locally and (B) simulates the full Docker build/run topology to catch deploy-only failures before they reach the deploy target (Coolify). Use on /docker-test, or when asked to test the worker/queue locally, dry-run or simulate a Docker / Coolify deploy, or catch deploy errors before pushing. Detects the project's Dockerfile, worker, queue, DB, and migrations; defaults to colima as the local runtime. Fixes blockers only to unblock the test and reports every one, but never commits without approval.
---

# docker-test

Two-pronged pre-deploy check, run before pushing to a containerized deploy (Coolify on Hetzner by default):

- **(A) Worker/queue path** — boot the real background worker against a local DB and watch a job flow through every queue stage. Inline/pilot code paths bypass the worker, so it may have **never actually started**. This is the only thing that proves it does.
- **(B) Docker deploy simulation** — build the real image and run the full deploy topology (DB + migrations + worker + web, from the image) locally. Surfaces failures that only appear inside the container, never on the host.

Generic methodology: detect the project's shape, don't assume this exact stack. The worked examples below come from a Next.js + pg-boss + Postgres + drizzle + Coolify project; pattern-match, don't copy blindly.

## Step 0 — Map the project

Read, don't guess: `Dockerfile`, `docker-compose.yml`, `package.json` scripts, the worker entry (e.g. `worker/index.ts`), the queue module, the migration config (e.g. `drizzle.config.ts`), the health route, `.dockerignore`. Identify:
- the **build command** (the Dockerfile's risky `RUN` step, usually `npm run build`)
- the **worker** process + **queue** tech + the **mock/offline flag** (e.g. `MOCK_INTEGRATIONS=true`)
- the **DB** + **migration** command (e.g. `npm run db:migrate`)
- the **health endpoint** + exposed port
- the **deploy target** (Coolify → env vars live in the dashboard, web + worker run as separate services from the same image)

## Step 1 — Cheap check first, in parallel with Docker boot

The host production build is the #1 deploy-failure point and needs no Docker. Kick it off immediately (background) **while** the Docker runtime starts:

```bash
npm run build            # validates the Dockerfile's RUN npm run build, host-side, instantly
docker info              # is the daemon up?
colima start             # if down and colima is the runtime (background; takes ~1 min)
```

A clean host build ≠ a clean image (see Step 5/6), but a broken host build means the image build will fail too — catch it for free now.

## Step 2 — (A) Exercise the worker/queue locally

1. Ensure a local Postgres is up (`docker compose up -d db` if the compose file defines one) and **migrated** (`npm run db:migrate`).
2. Boot the worker in **mock mode** so it costs nothing and hits no external API — the queue plumbing, scheduler, and job ordering are identical to live:
   ```bash
   MOCK_INTEGRATIONS=true npm run worker     # adapt to the project's mock flag + worker script
   ```
3. Enqueue one representative job (a backfill/scrape) through the **real** producer (the same `send`/enqueue function the app uses), then watch it fan out through every stage.
4. **Assert the queue, don't eyeball logs.** Query the queue's own state tables and require **zero failed, zero dead-lettered**:
   ```sql
   SELECT name, state, count(*) FROM pgboss.job GROUP BY name, state ORDER BY name;
   ```
   Confirm: worker booted, scheduler auto-enqueued due work, each stage ran as a **separate queued job** (not inline), nothing in any `*.dead` queue.
5. Stop the worker.

## Step 3 — (B) Build the real image

```bash
docker build -t deploy-test .
```
Validates the base image, `npm ci`, every `COPY` path, and the in-container build — none of which the host build exercises.

## Step 4 — Boot the runner image and hit health

```bash
docker run --rm -p 3000:3000 --env-file .env.local deploy-test &
curl -fsS localhost:3000/api/health     # expect 200
```

## Step 5 — Simulate the full deploy topology (the faithful check)

This is where deploy-only failures surface. Recreate the Coolify shape: a **fresh** Postgres, run migrations **from the image**, then boot the **worker from the image** (the part that has never run in prod):

```bash
docker network create deploy-test-net
docker run -d --name dt-db --network deploy-test-net \
  -e POSTGRES_DB=app -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres postgres:16
# migrations from the image (NOT the host) — catches configs missing from the runner stage
docker run --rm --network deploy-test-net -e DATABASE_URL=postgres://postgres:postgres@dt-db:5432/app \
  deploy-test npm run db:migrate
# worker from the image
docker run -d --name dt-worker --network deploy-test-net \
  -e DATABASE_URL=postgres://postgres:postgres@dt-db:5432/app deploy-test npm run worker
docker logs dt-worker     # expect the worker's "started" line, no crash
```

## Step 6 — Fix-to-unblock policy

When a stage fails, it has caught a real deploy-blocker. Apply the **minimal** fix needed to let the test continue, re-run that stage, then proceed. **Report every blocker found.** Do **not** commit or push the fixes; ask for explicit approval first (per the main-branch protection rule).

## Step 7 — Full teardown

```bash
docker rm -f dt-db dt-worker 2>/dev/null; docker network rm deploy-test-net 2>/dev/null
docker rmi deploy-test 2>/dev/null
colima stop
```
Then **flag** the dev-DB queue residue (pg-boss tables + completed test jobs) and offer to clean it. Re-verify the host is green: type-check + tests (`tsc`/`npm test`).

## Step 8 — Report

List each blocker with its failure signature, root cause, and the exact fix; state the verified-green results (worker/queue counts, image build, health 200, in-image migrate + worker boot); list uncommitted files; end by asking whether to commit/push.

---

## Common deploy-blockers (worked examples)

The three classes below recur. The unifying principle: **anything that works on the host only because it sits in the cwd, but is never `COPY`'d into the runner stage, fails only inside the container.** That is exactly why Step 5 (run from the image, not the host) is mandatory.

**1. Queue library needs the dead-letter queue created before it's referenced.**
- Signature: `Error: Queue scrape.creator.dead does not exist` at worker boot (pg-boss v12).
- Cause: queues created with `deadLetter: '${name}.dead'` but the `.dead` queue itself was never created.
- Fix: create `await boss.createQueue(\`${name}.dead\`)` **before** the main `createQueue`, in **every** place that creates queues (the worker *and* the app-side producer).

**2. Runner stage missing `tsconfig.json` → `@/*` path alias fails.**
- Signature: `ERR_MODULE_NOT_FOUND` at `resolveTsPaths` when the worker runs under `tsx` in the image.
- Cause: `tsx` needs `tsconfig.json` to resolve the `@/*` alias; it's in cwd locally but never copied to the runner.
- Fix: `COPY --from=builder /app/tsconfig.json ./tsconfig.json`.

**3. Runner stage missing the migration config → `db:migrate` fails in the image.**
- Signature: `/app/drizzle.config.json file does not exist` when running migrations from the image (drizzle-kit looks for a `.json` after the `.ts` is absent).
- Cause: `drizzle.config.ts` is in cwd locally but never copied to the runner.
- Fix: `COPY --from=builder /app/drizzle.config.ts ./drizzle.config.ts`.

After fixing Dockerfile `COPY`s, rebuild (cached layers make it fast) and re-run Step 5 to confirm.

## Notes
- **colima** is the default local Docker runtime; the daemon is often stopped. Step 1 starts it, Step 7 stops it.
- **Mock mode** keeps Prong A free and side-effect-free; the queue/scheduler behavior is identical to live, so it fully validates the path the inline pilots skip.
- macOS has no `timeout`/`gtimeout` by default (`brew install coreutils` adds `gtimeout`) if you need to bound a hanging container.
