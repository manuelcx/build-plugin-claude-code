---
name: docker-test
description: Pre-deploy smoke test that (A) exercises the real background worker and queue path locally and (B) simulates the full Docker build and run topology to catch deploy-only failures before they reach the deploy target (Coolify). Use on /build:docker-test, or when asked to test the worker or queue locally, dry-run or simulate a Docker or Coolify deploy, or catch deploy errors before pushing. Detects the project's Dockerfile, worker, queue, DB, and migrations; defaults to colima as the local runtime. Fixes blockers only to unblock the test and reports every one; never commits.
---

# docker-test

Two-pronged pre-deploy check, run before pushing to a containerized deploy (Coolify on Hetzner by default). Inside `/build:build` it runs under `reference/unattended-contract.md`: no questions, no commits; a runtime that cannot start makes the gate `not runnable` with the reason, never a stop.

- **(A) Worker and queue path:** boot the real background worker against a local DB and watch a job flow through every queue stage. Inline or pilot code paths bypass the worker, so it may never have actually started. This is the only thing that proves it does.
- **(B) Docker deploy simulation:** build the real image and run the full deploy topology (DB, migrations, worker, web, all from the image) locally. Surfaces failures that only appear inside the container.

Generic methodology: detect the project's shape, do not assume this exact stack. The worked examples come from a Next.js, pg-boss, Postgres, drizzle, Coolify project; pattern-match, do not copy blindly.

## Step 0: map the project

Read, do not guess: `Dockerfile`, `docker-compose.yml`, `package.json` scripts, the worker entry, the queue module, the migration config, the health route, `.dockerignore`. Identify the build command (the Dockerfile's risky `RUN` step), the worker process, the queue tech and the mock or offline flag, the DB and migration command, the health endpoint and port, and the deploy target (Coolify: env vars live in the dashboard, web and worker run as separate services from one image).

## Step 1: cheap check first, in parallel with the Docker boot

The host production build is the first deploy-failure point and needs no Docker. Kick it off in the background while the runtime starts:

```bash
npm run build     # validates the Dockerfile's RUN npm run build, host-side
docker info       # daemon up?
colima start      # if down and colima is the runtime; about a minute
```

A clean host build is not a clean image (steps 5 and 6), but a broken host build means the image build fails too.

## Step 2: (A) exercise the worker and queue locally

1. Local Postgres up (`docker compose up -d db` when the compose file defines one) and migrated.
2. Boot the worker in mock mode so it costs nothing and hits no external API; queue plumbing, scheduler, and job ordering are identical to live: `MOCK_INTEGRATIONS=true npm run worker` (adapt the flag and script).
3. Enqueue one representative job through the real producer, then watch it fan out through every stage.
4. Assert the queue, do not eyeball logs: query the queue's own state tables and require zero failed, zero dead-lettered (`SELECT name, state, count(*) FROM pgboss.job GROUP BY name, state ORDER BY name;`). Confirm the worker booted, the scheduler auto-enqueued due work, each stage ran as a separate queued job, nothing in any `*.dead` queue.
5. Stop the worker.

## Step 3: (B) build the real image

`docker build -t deploy-test .` validates the base image, `npm ci`, every `COPY` path, and the in-container build.

## Step 4: boot the runner image and hit health

`docker run --rm -p 3000:3000 --env-file .env.local deploy-test &` then `curl -fsS localhost:3000/api/health` (expect 200).

## Step 5: simulate the full deploy topology (the faithful check)

Recreate the Coolify shape: a fresh Postgres, migrations from the image, then the worker from the image (the part that has never run in prod):

```bash
docker network create deploy-test-net
docker run -d --name dt-db --network deploy-test-net -e POSTGRES_DB=app -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres postgres:16
docker run --rm --network deploy-test-net -e DATABASE_URL=postgres://postgres:postgres@dt-db:5432/app deploy-test npm run db:migrate
docker run -d --name dt-worker --network deploy-test-net -e DATABASE_URL=postgres://postgres:postgres@dt-db:5432/app deploy-test npm run worker
docker logs dt-worker     # expect the worker's started line, no crash
```

## Step 6: fix-to-unblock policy

When a stage fails, it caught a real deploy blocker. Apply the minimal fix needed to let the test continue, re-run that stage, proceed. Inside a build, the fix is routed to the executor as a fix brief per the actor rule; standalone, apply it directly. Report every blocker. Never commit or push.

## Step 7: full teardown

```bash
docker rm -f dt-db dt-worker 2>/dev/null; docker network rm deploy-test-net 2>/dev/null
docker rmi deploy-test 2>/dev/null
colima stop
```

Flag the dev-DB queue residue (queue tables and completed test jobs) in the report. Re-verify the host is green: type-check and tests.

## Step 8: report

Each blocker with its failure signature, root cause, and the exact fix; the verified-green results (worker and queue counts, image build, health 200, in-image migrate and worker boot); the uncommitted files. Inside a build this becomes the docker gate's ledger row.

## Common deploy blockers (worked examples)

The unifying principle: anything that works on the host only because it sits in the cwd, but is never copied into the runner stage, fails only inside the container. That is why step 5 runs from the image.

1. **Queue library needs the dead-letter queue created before it is referenced.** Signature: `Error: Queue scrape.creator.dead does not exist` at worker boot (pg-boss v12). Fix: create the `.dead` queue before the main `createQueue`, in every place that creates queues (worker and app-side producer).
2. **Runner stage missing `tsconfig.json`, so the `@/*` path alias fails.** Signature: `ERR_MODULE_NOT_FOUND` at `resolveTsPaths` under `tsx` in the image. Fix: `COPY --from=builder /app/tsconfig.json ./tsconfig.json`.
3. **Runner stage missing the migration config.** Signature: `/app/drizzle.config.json file does not exist` when migrating from the image. Fix: `COPY --from=builder /app/drizzle.config.ts ./drizzle.config.ts`.

After fixing Dockerfile `COPY`s, rebuild (cached layers make it fast) and re-run step 5.

## Notes

- colima is the default local runtime and is often stopped; step 1 starts it, step 7 stops it.
- Mock mode keeps prong A free and side-effect-free while validating the exact path the inline pilots skip.
- macOS has no `timeout` by default; `perl -e 'alarm shift; exec @ARGV' <secs> <cmd>` bounds a hanging container.
