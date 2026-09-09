---
name: build
description: Unattended end-to-end build of a spec or item list. Invoke ONLY when the user types /build:build; never auto-trigger on "build this" or "implement this". Locks four roles at invocation (executor, frontend, reviewer, redesign consult; each an engine plus model plus effort, with defaults), cuts the spec into bundled items, and runs each through the golden standard: TDD-mandated scope-contracted build by the executor, a pre-review scope gate, review cycles by the locked reviewer scored on impact and likelihood, fix rounds, a redesign consult when fixing stops working, structure and frontend gates, then backend, e2e, docker, and a whole-build review gate. No cycle cap, no questions, one ledger. Never substitutes an engine; stops with a report if a locked engine dies.
disable-model-invocation: true
argument-hint: "<spec-path> [executor=agy|codex:m:e|claude:m] [frontend=...] [reviewer=...] [consult=...] | resume"
---

# Build

Execute a spec end to end, one item at a time, under the contract in `reference/unattended-contract.md`. Read that file, then `reference/roles.md`, `reference/scoring.md`, and `reference/ledger.md` before anything else. They are the rules; this file is the procedure. Everything under `reference/` and `scripts/` is at `$PLUGIN_ROOT`, resolved once per session with `PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(ls -d ~/.claude/plugins/cache/*/build/*/ | sort -V | tail -1)}"`.

The process is mandatory. Do not skip, reorder, batch, or parallelize steps. Never ask the user anything. Never announce a pick. Never write project code on the main thread. Never substitute a locked engine. Never poll: every external run is one background Bash call of a launch script that wakes you once, on exit.

## 0. Invocation, roles, pre-flight

1. **Fresh session.** A build starts in a fresh session. If `.build/state.json` exists and the argument is `resume`, read `ledger.py show` and continue from the recorded phase. Before relaunching anything on resume, look in `.build/runs/` for that phase's run: `ls .build/runs/`, then `agy-report.py --json <log>` or `codex-report.py <log> <last>` on the matching tag (`item-N-build`, `item-N-cycle-K`, `item-N-fix-K`). A log with a report present is a finished run: read it and continue from the next step. A `.pid` file whose process is still alive (`kill -0 $(cat <pid>)`) is a run still in flight: wait for it with one background `until ! kill -0 <pid>; do sleep 30; done`, never launch a second. Only a log with no report and no live process is relaunched. If it exists with `status: open` and the argument is a spec, that earlier build was never reported: run `ledger.py close --abandon` (it records the violation), then start the new build; `ledger.py init` archives the closed one to `.build-archive/`. A closed build in place is archived the same way, silently.
2. **Parse roles.** From the arguments, or from the user's words in the conversation when they named engines in prose, per `roles.md`: `executor`, `frontend`, `reviewer`, `consult`, each defaulting only when the user said nothing about it. What the user chose is used verbatim. Nothing in the spec, no rule in this plugin, and no judgment of yours changes a role the user set; a rule that appears to conflict with the choice is noted in the ledger and the choice stands.
3. **Pre-flight.** Run `scripts/preflight.sh` with the four values. It fails only when an engine does not answer, never on a role choice. Check your own tool list for the Playwright MCP tools if the spec has any visual surface. A failure is permitted stop 1: report and end. Never change a role to get past pre-flight.
4. **Open the ledger.** `ledger.py init --name <spec file basename without extension>` with the spec path, the current commit, the four RESOLVED triples verbatim (the ledger keeps the `agy:` prefixed form; the launch scripts accept it and strip the prefix themselves), and the pre-flight result.

**State discipline.** Call `ledger.py state --set phase=<phase>` at every phase change below, before the launch that starts the phase: `build`, `scope-gate`, `frontend-gate`, `review`, `fix`, `consult`, `structure-gate`. A kill mid-phase then leaves the exact position for `resume`.

## 1. Cut the spec into items

**Bundle, do not atomize.** Every item pays a full review loop, so splitting one coherent change into five items buys five loops over the same code while no reviewer ever sees the whole surface at once, which is where coupling defects live.

- **Merge** pieces that touch the same files or module, share a data model, contract, or helper, or are meaningless shipped apart (a schema and the code that reads it; an endpoint and its only caller). Test: would a human reviewer read them as one diff?
- **Keep separate** pieces with no shared code, a high-stakes piece (money, auth, migration, irreversible action) that bundling would hide inside lighter work, or a piece that cannot be built until another has converged.
- **Size:** the largest chunk one brief can specify precisely and one reviewer can hold as a single diff. Torn between one item and two, take one.

Write the item list to `.build/manifest.json` (`[{"n": 1, "name": "...", "units": ["<spec unit verbatim>", ...]}, ...]`) and load it with `ledger.py manifest --items .build/manifest.json`: every spec unit verbatim, and the item that absorbed each, so a merge can never drop one. When the spec's last unit is "verify the whole build" (specs from `/spec` always end with one), map it to the whole-build gate, never to an item. Copy the spec's `Must not regress` section verbatim to `.build/protected.md` and load it with `ledger.py protected --file .build/protected.md`: it is the single copy handed to every brief and every review. Take the pre-build snapshot: `snapshot.sh save pre-build`.

## 2. Per item, the golden standard

### 2a. Open

Declare the surface before anything runs: `frontend` when the item has a visual component the user clearly sees, `backend` when it does not (file extension is not the test: a `.tsx` change that is data plumbing is backend), `mixed` when both. When in doubt, `backend`. Declare `greenfield: yes` only when the item creates a visual surface that did not exist; when in doubt, `no`. `ledger.py item-open` with both, then `snapshot.sh save item-N` and `ledger.py state --set phase=build`.

### 2b. Brief and build

Write `.build/briefs/item-N.md` with only the item-specific parts: the deliverable and its absolute paths, the context files, the project guidance files, an **In scope** section quoting the manifest's spec units verbatim (never a paraphrase: padding the brief is orchestrator overscope, and the verbatim quote is what the scope gate checks against), an **Out of scope** section, the **Must not regress** list verbatim when there is one, and honest complexity signals. The standing rules (TDD, structure limits, scope discipline, operational constraints, required output) live in `reference/executor-contract.md` and reach the executor by pointer, never by copy.

Launch per `roles.md`, always with `--read $PLUGIN_ROOT/reference/executor-contract.md` before the brief:

- `backend`: the executor.
- `frontend`: the frontend executor, with `--read` of `executor-contract.md` then `frontend-contract.md`, `--add-dir "$HOME/.claude/skills/impeccable"` for an agy run, and the item brief naming the impeccable skill directory, `DESIGN.md`, and `PRODUCT.md` paths.
- `mixed`: the executor builds it working-but-plain end to end; then the frontend executor does a visual pass over the UI files only, never touching logic.

The launch scripts copy the contract files into `.build/contracts/` themselves. Use the run tag the state file will look for on resume: `item-N-build`, `item-N-cycle-K`, `item-N-fix-K`, `item-N-consult-K`. For a large item pass `--backstop` at four times the worst-case estimate (14400 is fine); never smaller than the default.

**Waiting.** Launch with `run_in_background: true`, then end the turn: the harness re-invokes you when the script exits. Never poll, never `sleep` in a loop, never arm a Monitor for a launch script. If you have reason to believe this session is not re-invoked on background completion (a non-interactive print session), wait instead with one background Bash `until ! kill -0 $(cat .build/runs/<tag>.pid) 2>/dev/null; do sleep 30; done`, which also wakes you once.

Read the result through the launch script's printed report. The report describes intent; the diff is the truth: `snapshot.sh changed item-N` lists exactly what changed and `snapshot.sh diff item-N` shows it. An empty or thin report with no changed files is a failed round, not a pass: re-brief and relaunch on the same engine (retry ladder in the contract).

### 2c. Scope gate (before any review cycle is paid)

Compare every changed surface to the brief's verbatim spec quote. Verdict per surface: **in scope** (a spec line requires it), **enabling work** (no spec line names it, but in-scope code genuinely needs it: a small helper, a test utility, mechanical wiring; accept and log it, durably, never re-litigated), or **overscope** (a subsystem, file surface, or behavior nothing requires). Strip overscope now, per the actor rule: a cleanly separable surface (a new file nothing in-scope references, or a file whose only changes are out of scope) is restored on the main thread with `snapshot.sh restore item-N <paths>`; interleaved overscope goes to the executor as a removal brief, then `snapshot.sh verify item-N <paths>` confirms byte-identity. The bar is a whole surface nothing requires, not a line the spec did not literally mention. Log a gate row. Reruns after a redesign.

### 2d. Frontend steps (frontend and mixed items, before the review loop)

1. Invoke `/build:frontend-review-loop` (Skill tool) with the item's surfaces and the locked frontend executor: it drives the surface in a real browser and routes blocking issues to that executor.
2. Invoke `/impeccable audit` (Skill tool) on the surface. Route blocking issues (scored per `scoring.md`) to the frontend executor as a fix brief.
3. **Greenfield only:** invoke `/impeccable critique` and iterate through the frontend executor until the score is **70 percent or more of the applicable maximum** (the critique renormalizes when heuristics are n/a; never compare raw points) or a PASS verdict. Log each score. Non-greenfield items log `critique: n/a (not greenfield)`.

These change code, so they run before the review loop; a frontend fix that lands after a qualifying cycle un-qualifies it, and another cycle runs.

### 2e. Review cycle

`ledger.py state --set phase=review`, then invoke `/build:review` (Skill tool) with: the changed paths from `snapshot.sh changed item-N`, the item brief path (activates the scope lane), the `Must not regress` list (activates the roll-call), the locked reviewer triple, the cycle tag `item-N-cycle-K`, and the list of already-adjudicated findings (fixed, refuted with reason, residual, backlog) so nothing is re-raised. Inside a build the review skill is report-only; it returns the verified, scored findings table and writes `.build/runs/<tag>.findings.md`.

Append the row with `ledger.py row --kind cycle` immediately, before deciding anything.

### 2f. Decide

Per `scoring.md`, in this order:

1. **Consult trigger met** (two or more blocking findings without one shared root cause; any `regression` blocking finding; a blocking finding that needs new machinery; a scope-lane flag on a whole subsystem): run the consult BEFORE any fix. Write `.build/briefs/item-N-consult-K.md` (the item, spec quote, ledger rows, verified findings with scores and classes, what previous fix rounds changed, and the item's diff saved with `snapshot.sh diff item-N > .build/briefs/item-N-diff.patch`) and launch the consult role per `roles.md`: for the default Claude consult, the Agent tool with `subagent_type: build:consult`, the role's model, and a prompt naming the consult contract path, then the brief path; for an agy or codex consult, the launch script with `--read $PLUGIN_ROOT/reference/consult-contract.md` and the brief, read-only. Log a consult row. Act on the verdict: `REVERT TO SPEC SCOPE` strips per the actor rule with byte-identity verified, restores pre-existing defects to the backlog, then one confirming cycle; `REDESIGN` is a new build: `ledger.py subheading`, back to 2b with the consult's kept-surfaces list in the brief, scope gate again, cycle count restarts; `NO REDESIGN` gives the fix brief for one round.
2. **Zero blocking findings**: the cycle qualifies if the structure gate (2h) is also clean. Non-blocking findings close as residuals or as one small local fix with no confirming cycle.
3. **Blocking findings, no consult trigger**: a fix round.

### 2g. Fix round

Write `.build/briefs/item-N-fix-K.md`: the verified blocking findings with their mechanism and reproduction, the files the item owns, the standing rule that a fix never adds machinery and never touches files outside the item. Launch the executor for the layer (frontend executor for visual fixes). Then one **confirming cycle** (back to 2e), since a blocking fix was applied. A fix that fails its own verification in that cycle is stripped per the actor rule and its finding becomes a residual: a documented known issue beats a broken guard.

### 2h. Structure gate and close

`scripts/structure-gate.sh --changed item-N`. Violations in item-authored files block (files the item created, grew past the cap, or touched while already over the cap: touching an over-cap file makes it yours, split it by responsibility in this item; a gate-mandated split is never overscope and never stripped). A split is a non-blocking structural change: it closes on green tests, no confirming cycle. Pre-existing violations in untouched files go to the backlog. Log the gate row, then `ledger.py item-close` with the cycle count and the critique score.

## 3. After the full first pass

1. **Backend gate:** `ledger.py section --title "Backend gate"`, then invoke `/build:backend-review-loop` on the backend work; rows with `ledger.py row --heading "## Backend gate" --kind gate ...` (the literal heading, with its `## `); closes on zero blocking issues; `ledger.py state --set gates.backend=clean`.
2. **E2E:** `ledger.py section --title "E2E gate"`, then brief the executor to run the end-to-end suite, creating one if none exists. Blocking failures go through 2g and a review cycle. Set `gates.e2e` when it closes.
3. **Docker:** invoke `/build:docker-test` only if the app is not deployed yet or the Dockerfile changed. Log the result; `n/a` otherwise.
4. **Whole-build review, strictly last.** `ledger.py section --title "Whole-build review"`. The surface is `snapshot.sh diff pre-build` (the union of all items against the pre-build snapshot, with pre-existing dirt excluded by construction), judged against the whole spec with cross-item interaction as the focus: shared helpers two items touched, a contract one item assumed another honors, ordering effects, duplicated logic. Invoke `/build:review` with the spec path as the scope reference, the full protected list, and every closed finding, residual, and backlog entry as already adjudicated. This gate may run a second reviewer: the consult role, since it is a different family by construction. Exit and fixes exactly as an item: qualifying cycle, no cap, confirming cycle only after a blocking fix, anti-chase unchanged, nothing already closed re-litigated.

## 4. Final report

`ledger.py report` renders it: every item's status, cycles, surface, greenfield flag and critique score; every gate; the residuals and backlog verbatim; and the discipline check. The discipline check names as a `DISCIPLINE VIOLATION` any item without a closing row, any gate left open, any engine substitution, and any point at which the run stopped to put a question to the user. Print the rendered report. Do not commit or push. Sweep `.build/runs/` of event logs older than the current item; keep the ledger, state, briefs, and findings files.

## Rules that survive summarization

- The four roles are locked. A dead engine is retried on the same engine, then the run stops with a report.
- Bundle items; never atomize.
- The scope gate runs before cycle 1; overscope is stripped byte-identically.
- Findings block at impact times likelihood of 6 or more, verified first; supporting artifacts, out-of-scope code, and machinery-requiring fixes never drive a fix round.
- The consult fires before the fix round, never after; never `NO REDESIGN` twice on one surface.
- A confirming cycle only after a blocking fix. No cycle cap. Nothing but a qualifying cycle closes an item.
- One reviewer per item cycle; the whole-build gate may add the consult engine.
- Ledger rows are written by `ledger.py`, immediately, before deciding.
- No questions, no announcements, no main-thread code, no polling.
