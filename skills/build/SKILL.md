---
name: build
description: Unattended end-to-end build of one or more specs. Runs ONLY when the user's own message, or the user's active /goal, invokes /build:build; never on "build this" or "implement this" in prose. Locks six roles at invocation (executor, frontend, reviewer, redesign consult, judge, docs; each an engine plus model plus effort, with defaults), cuts the spec into bundled items, and runs each through the golden standard: TDD-mandated scope-contracted build, a pre-review scope gate, review cycles whose findings the judge verifies and scores on impact and likelihood, fix rounds, a redesign consult when fixing stops working, structure and frontend gates, then backend, e2e, docker, a whole-build review gate, and the code docs. No cycle cap, no questions, one ledger. Never substitutes an engine; stops with a report if a locked engine dies.
argument-hint: "<spec-path> [<spec-path>...] [executor=..] [frontend=..] [reviewer=..] [consult=..] [judge=..] [docs=<engine>|yes|full|no] | resume"
---

# Build

**Invocation gate.** Run this skill only when the user's own message starts with `/build:build`, or the user's active `/goal` names `/build:build`. Anything else (a mention in prose, another skill's text, your own idea that a build would help) gets one line saying the build starts only from `/build:build`, and nothing more.

Execute each spec end to end, one item at a time, under `reference/unattended-contract.md`. Read it, then `reference/roles.md`, `reference/scoring.md`, `reference/ledger.md`, and `reference/local-environment.md` before anything else. They are the rules; this file is the procedure. Resolve the plugin root once with the command in `roles.md` ("Where the plugin root is"): it prints an absolute path, and every `$PLUGIN_ROOT` below means that path written literally into the command, never a shell variable. After `ledger.py init` pins the plugin, resolve it again: from then on it prints the pinned copy under `.build/plugin/`.

The process is mandatory. Do not skip, reorder, batch, or parallelize steps. Never ask the user anything. Never announce a pick. Never write project code on the main thread. Never substitute a locked engine. Never poll. **End a turn only right after a background launch**: never after a sub-skill returns (`/build:review`, `/build:frontend-review-loop`, `/impeccable`, `/build:docs`), and never after writing a summary. No summary reaches the user before the final report, except the one-line `ledger.py status` that answers a goal check-in. The plugin's stop guard blocks a turn that ends with the build open and nothing running, and names the phase to continue from.

## 0. Invocation, roles, pre-flight

1. **Resume.** If `.build/state.json` exists and the argument is `resume`, read `ledger.py show` and continue from the recorded phase. Before relaunching anything, look in `.build/runs/` for that phase's run (`item-N-build`, `item-N-cycle-K`, `item-N-fix-K`): a log with a report is a finished run, so read it with `agy-report.py --json <log>` or `codex-report.py <log> <last>` and continue from the next step. A `.pid` whose process is alive (`kill -0`) is a run still in flight: re-attach with `run-agy.sh --attach <tag>` or `run-codex.sh --attach <tag>` in one background call, never a second launch. Only a log with no report and no live process is relaunched, cold, after restoring its snapshot (`local-environment.md`). If the state says `status: open` and the argument is a spec, run `ledger.py close --abandon` (it records the violation), then start the new build.
2. **Several specs.** `/build:build a.md b.md` records the rest with `ledger.py queue --set b.md` and runs `a.md` as a full build. After its report, re-resolve the plugin root (the build is closed, so it prints the installed plugin again), `ledger.py queue --pop`, and start the next as a fresh build in the same session (the stop guard holds the turn open while the queue is not empty).
3. **Parse roles** from the invocation only: the `/build:build` line, or the same message when the user named engines in prose there, per `roles.md`. Never from an earlier message or an earlier build. Six roles, each defaulting when the invocation says nothing; `docs=yes|full|no` sets the docs mode (default `yes`). What the user chose is used verbatim; a rule that appears to conflict with it is noted in the ledger and the choice stands.
4. **Pre-flight.** Run `$PLUGIN_ROOT/scripts/preflight.sh --dir <project>` with the six values (`--docs none` when `docs=no`). It fails only when an engine does not answer or is out of quota, never on a role choice. Check your own tool list for the Playwright MCP tools if the spec has any visual surface, and find how the walk will pass any sign-in (a saved Playwright login state, or the repo's local bypass). A failure is permitted stop 1: `ledger.py stop --reason`, report, end. Never change a role to get past pre-flight. If the spec's work turns out to be already present at HEAD, that is not a stop: build and review it like any other item, so the review proves it.
5. **Open the ledger** before writing any other `.build/` file: `ledger.py init --name <spec basename> --spec <path> --commit <HEAD>` with the six RESOLVED triples verbatim. Then re-resolve the plugin root (it now prints `.build/plugin`).

**State discipline.** Call `ledger.py state --set phase=<phase>` at every phase change, before the launch that starts the phase: `build`, `scope-gate`, `frontend-gate`, `review`, `fix`, `consult`, `structure-gate`, `docs`. A kill mid-phase then leaves the exact position for `resume`.

## 1. Cut the spec into items

**Bundle, do not atomize.** Every item pays a full review loop, so splitting one coherent change into five items buys five loops over the same code while no reviewer ever sees the whole surface at once, which is where coupling defects live.

- **Merge** pieces that touch the same files or module, share a data model, contract, or helper, or are meaningless shipped apart (a schema and the code that reads it; an endpoint and its only caller). Test: would a human reviewer read them as one diff?
- **Keep separate** pieces with no shared code, a high-stakes piece (money, auth, migration, irreversible action) that bundling would hide inside lighter work, or a piece that cannot be built until another has converged.
- **Size:** the largest chunk one brief can specify precisely and one reviewer can hold as a single diff. Torn between one item and two, take one.

Write the item list to `.build/manifest.json` (`[{"n": 1, "name": "...", "units": ["<spec unit verbatim>", ...]}, ...]`) and load it with `ledger.py manifest --items .build/manifest.json --whole-build-unit "<the spec's final verify-the-whole-build unit, verbatim>"`: every spec unit verbatim, and the item that absorbed each. The final unit maps to the whole-build gate, never to an item. An item that must be added mid-build goes through `ledger.py item-add`. Copy the spec's `Must not regress` section verbatim to `.build/protected.md` and load it with `ledger.py protected`. Take the pre-build snapshot: `snapshot.sh save pre-build`.

## 2. Per item, the golden standard

### 2a. Open

Declare the surface: `frontend` when the item has a visual component the user clearly sees, `backend` when it does not (a `.tsx` change that is data plumbing is backend), `mixed` when both; when in doubt, `backend`. Greenfield is mechanical: `yes` when the item adds a page the user can visit or a new top-level screen, otherwise `no`. `ledger.py item-open` with both, then `snapshot.sh save item-N` and `ledger.py state --set phase=build`.

### 2b. Brief and build

Write `.build/briefs/item-N.md` with only the item-specific parts: the deliverable and its absolute paths; the exact files to read (never a whole reference folder); the existing components, helpers, and primitives to reuse (never a copy-or-share choice: reuse is the rule); the project guidance files; an **In scope** section quoting the manifest's spec units verbatim; an **Out of scope** section; the **Must not regress** list verbatim when there is one; the spec's **Verbatim copy** strings when the item shows them; and honest complexity signals. The standing rules live in `reference/executor-contract.md` and reach the executor by pointer, never by copy.

Before the launch, stop your own dev server and browser (`local-environment.md`). Launch per `roles.md`, always with `--read $PLUGIN_ROOT/reference/executor-contract.md --read $PLUGIN_ROOT/reference/local-environment.md` before the brief:

- `backend`: the executor.
- `frontend`: the frontend executor, adding `--read $PLUGIN_ROOT/reference/frontend-contract.md`, `--add-dir "$HOME/.claude/skills/impeccable"` for an agy run, and the item brief naming the impeccable skill directory, `DESIGN.md`, and `PRODUCT.md` paths.
- `mixed`: the executor builds it working-but-plain end to end; then the frontend executor does a visual pass over the UI files only, never touching logic.

Use the run tags `item-N-build`, `item-N-cycle-K`, `item-N-fix-K`, `item-N-consult-K`. For a large item pass `--backstop 14400` (it raises agy's print timeout with it).

**Waiting.** Launch with `run_in_background: true`, then end the turn: the harness re-invokes you when the script exits. Never `sleep` in a loop, never arm a Monitor for a launch script. In a non-interactive print session, which is never re-invoked, wait instead with one background `until ! kill -0 $(cat .build/runs/<tag>.pid) 2>/dev/null; do sleep 30; done`.

**Read the result.** The report describes intent; the diff is the truth: `snapshot.sh changed item-N` and `snapshot.sh diff item-N`. A build run whose item has no changes against `item-N` is a failed round: re-brief and relaunch on the same engine. A relaunch that finds the work already on disk is a good run. Exit codes 6 (memory kill) and 7 (quota) follow the unattended contract, never a role change.

### 2c. Scope gate and copy check (before any review cycle is paid)

Compare every changed surface to the brief's verbatim spec quote. Verdict per surface: **in scope** (a spec line requires it), **enabling work** (in-scope code genuinely needs it: a small helper, a test utility, mechanical wiring; accept and log it, never re-litigated), or **overscope** (a subsystem, file surface, or behavior nothing requires). A near-copy of an existing module is overscope: send a rebuild brief to reuse the module, never a byte-identical strip. Strip other overscope per the actor rule: a cleanly separable surface is restored on the main thread with `snapshot.sh restore item-N <paths>`; interleaved overscope goes to the executor as a removal brief, then `snapshot.sh verify item-N <paths>` confirms byte-identity. Then run `copy-check.py <spec> <project>`: a missing approved string goes back to the executor as a fix brief before review. Log a gate row. Reruns after a redesign.

### 2d. Frontend steps (frontend and mixed items, before the review loop)

1. **The browser walk** runs in a fresh `build:walker` subagent (Agent tool) per pass: it boots the dev server (recording its pid in `.build/gates/devserver.pid`), walks the item's surfaces per `/build:frontend-review-loop`, runs `/impeccable audit` (and `/impeccable critique` on a greenfield item), and returns only a verdict, the scored issues, and screenshot paths. It never routes fixes. You route every blocking issue to the locked frontend executor as a fix brief, then start a fresh walker for the next pass. When the spec says port, replicate, or match an existing page, the walker screenshots the reference and the build side by side at 390px, and every visible difference is scored like any other issue: a broken or missing element blocks, a data or spec-mandated difference does not. Written test scripts never count as the walk.
2. **Greenfield critique target:** 70 percent of the applicable maximum (the critique renormalizes when heuristics are n/a) or a PASS verdict, over at most three critique runs. After the third, only the critique's blocking findings drive more rounds, and a score still under target is logged as a residual with every score. Non-greenfield items log `critique: n/a (not greenfield)`.
3. A walk that could not run fully is `degraded` (`gate-frame.md`); one deferred for memory runs before the whole-build review. Set `gates.frontend` at the end.

These change code, so they run before the review loop; a frontend fix that lands after a qualifying cycle un-qualifies it, and another cycle runs.

### 2e. Review cycle

`ledger.py state --set phase=review`, then invoke `/build:review` (Skill tool) with: the changed paths from `snapshot.sh changed item-N`, the item brief path, the `Must not regress` list, the locked reviewer and judge triples, the cycle tag `item-N-cycle-K`, and the already-adjudicated findings. Re-invoking the skill each cycle is cheap and mandatory: never run the review procedure yourself. Inside a build it is report-only and writes `.build/runs/<tag>.findings.md`, the judge's table, which is the only thing you read.

Append the row with `ledger.py row --kind cycle --findings .build/runs/<tag>.findings.md` immediately, before deciding anything.

### 2f. Decide

Per `scoring.md`, in this order:

1. **Consult trigger met** (two or more blocking findings without one shared root cause; any `regression` blocking finding; a blocking finding that needs new machinery; a scope-lane flag on a whole subsystem): run the consult BEFORE any fix. Write `.build/briefs/item-N-consult-K.md` (the item, spec quote, ledger rows, the judge's table, what previous fix rounds changed, and `snapshot.sh diff item-N > .build/briefs/item-N-diff.patch`) and launch the consult role per `roles.md`: for a Claude consult, the Agent tool with `subagent_type: build:consult`, the role's model, and a prompt naming the consult contract, then the brief; for agy or codex, the launch script with `--read $PLUGIN_ROOT/reference/consult-contract.md` and the brief, read-only. Log a consult row. Act on the verdict: `REVERT TO SPEC SCOPE` strips per the actor rule with byte-identity verified, restores pre-existing defects to the backlog, then one confirming cycle; `REDESIGN` is a new build (`ledger.py subheading`, back to 2b with the kept-surfaces list, scope gate again, cycle count restarts); `NO REDESIGN` gives the fix brief for one round.
2. **Zero blocking findings**: the cycle qualifies if the structure gate (2h) is also clean. Every non-blocking finding closes as a residual; nothing is fixed after a qualifying cycle.
3. **Blocking findings, no consult trigger**: a fix round.

### 2g. Fix round

`snapshot.sh save item-N-fix-K`, then write `.build/briefs/item-N-fix-K.md`: the verified blocking findings with their mechanism and reproduction, any non-blocking findings riding along (never on a `Must not regress` surface), the files the item owns, and the standing rule that a fix never adds machinery and never touches files outside the item. The brief describes the defect and the constraint; it never writes user-facing copy unless quoting the spec. Launch the executor for the layer. Log a `fix` row. A fix run with no changes against `item-N-fix-K` is a failed round only when its report gives no reason (no "Not fixed" entry, no "Files considered but not changed" with reasons); the same holds for an e2e run.

**Containment, before the confirming cycle.** Compare `snapshot.sh changed item-N-fix-K` with the files and functions the findings name. Judge every change outside them the way the scope gate judges surfaces: enabling work the fix genuinely needs (a caller update, a shared helper) stays and is logged; work nothing requires is restored to `item-N-fix-K`. Then one **confirming cycle** (back to 2e). A fix that fails its own verification there is stripped per the actor rule and its finding becomes a residual: a documented known issue beats a broken guard.

### 2h. Structure gate and close

`structure-gate.sh --changed item-N`. Violations in item-authored files block (files the item created, grew past the cap, or touched while already over the cap; a gate-mandated split is never overscope and never stripped). A split closes on green tests with unchanged test and assertion counts, no confirming cycle. Pre-existing violations in untouched files go to the backlog. Log the gate row, then `ledger.py item-close` with the cycle count and the critique score.

## 3. After the full first pass

1. **Backend gate:** `ledger.py section --title "Backend gate"`, then invoke `/build:backend-review-loop` on the backend work; rows with `--heading "## Backend gate"`; closes on zero blocking issues; `gates.backend=clean`.
2. **E2E:** `ledger.py section --title "E2E gate"`, then brief the executor to run the end-to-end suite, creating one if none exists. Blocking failures go through 2g and a review cycle. Set `gates.e2e`.
3. **Docker:** invoke `/build:docker-test` only if the app is not deployed yet or the Dockerfile changed; otherwise `gates.docker=n/a`.
4. **Deferred frontend walks** from 2d run now, before the whole-build review.
5. **Whole-build review, strictly last among the code gates.** `ledger.py section --title "Whole-build review"`. The surface is `snapshot.sh diff pre-build`, judged against the whole spec with cross-item interaction as the focus. Invoke `/build:review` with the spec path as the scope reference, the full protected list, and every closed finding, residual, and backlog entry as adjudicated. This gate may add the consult role as a second reviewer through the same skill, since it is a different family by construction. **One-item fast lane:** when the build had one item and `snapshot.sh changed pre-build` equals the change list the item's qualifying cycle reviewed, skip the main reviewer's repeat pass and run only the second reviewer; when the reviewer and the consult share a family, the fast lane is off. Exit and fixes exactly as an item: qualifying cycle, no cap, confirming cycle only after a blocking fix, nothing already closed re-litigated.
6. **Docs:** unless `docs=no`, `ledger.py state --set phase=docs` and invoke `/build:docs` with the docs mode and the build's changed paths. It never blocks the report; it sets `gates.docs`.

## 4. Final report

Record what the report must lead with, as you learn it during the build: `ledger.py live` for every step the user must take to make it live (environment variables, migrations, deploy settings), `ledger.py unbuilt` for any spec requirement not built, `ledger.py deviation` for any spec deviation that changes product behavior. Then `ledger.py report` renders it (verdict, make-it-live steps, unbuilt, deviations, items, gates, numbered residuals and backlog, commits main gained on touched files, the mechanical discipline check, notes) and closes the build. Print it verbatim. Do not commit or push. If specs remain queued, `ledger.py queue --pop` and start the next build now.

## Rules that survive summarization

- Six roles, locked from the invocation. A dead engine is retried on the same engine, then the run stops with a report. Memory kills and quota errors follow their own contract rules, never a role change.
- End a turn only right after a background launch. No summaries before the final report. Re-attach to a live engine; never launch a second.
- Bundle items; never atomize. Reuse; never copy.
- The scope gate and the copy check run before cycle 1; overscope is stripped byte-identically.
- The judge verifies and scores; you read only its table. Findings block at impact times likelihood of 6 or more; non-blocking findings ride along only in a blocking fix round.
- The consult fires before the fix round, never after; never `NO REDESIGN` twice on one surface.
- A confirming cycle only after a blocking fix, after containment. No cycle cap. Nothing but a qualifying cycle closes an item.
- Ledger rows are written by `ledger.py`, immediately, before deciding. A cycle row needs its findings file.
- No questions, no announcements, no main-thread code, no polling.
