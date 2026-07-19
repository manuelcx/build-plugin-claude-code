---
name: multi-review10x-lean
description: Maximum-intensity adversarial review of your latest output by a parallel fleet of EXTERNAL reviewers, at least 10 codex, each hitting a distinct dimension (including repo-consistency: conventions, shared-primitive reuse, existing URL/API contract, consolidation; and regression risk), with NO Claude skeptic subagents. Find flaws, then verify survivors with a second codex reproduction pass, report, and fix on your go-ahead. Use on /multi-review10x-lean and on requests for a 10x / deep / maximum / fleet / red-team adversarial or repo-consistency / regression review of the latest plan, code, feature, fix, or output run on the external engine only (no Claude subagent workflow). For the version that adds a Claude skeptic fleet, use /multi-review10x; for a single-reviewer pass, use /multi-review-lean.
---

# Multi-Review 10x Lean

A parallel fleet of EXTERNAL adversarial reviewers with **zero Claude subagents**: the review fleet is exactly codex (at least 10), and the verify stage is a second codex reproduction pass. Claude orchestrates only: it pins the target, assigns dimensions, drives the harness, dedups, reads the verifiers, reports, and (on approval) routes the fix. Claude spawns **zero review or verify subagents**. Each reviewer gets a DISTINCT dimension so they don't all surface the same shallow bug. Keep only flaws that reproduce, report them, and fix only on your explicit go-ahead.

Default contract: **review and report, then fix on approval.** Run the whole review autonomously (launch the fleet, watch it, consolidate, run the verify pass, report). Do NOT mutate anything until the user says go.

Why this drives the CLI by hand: running 10+ codex at once is fundamentally incompatible with the single-instance `/codex` command. It writes to fixed scratch paths and tracks/kills one instance per directory, so N of them in parallel clobber each other's logs and confuse its watchdog. This skill is a sanctioned place to drive the CLI directly, because it carries the **exact same anti-hang recipe** as that command, only parameterized per run and per instance (nonce-unique scratch files, nonce-scoped watchdog match). Every protection is preserved. See the harness in step 3 and do not strip a single flag.

**No Claude subagents (the whole point of "lean").** Do not spin up a review Workflow, a skeptic fleet, or per-finding verifier subagents at any stage. Both finding and verification run on the external engine (codex). Claude itself still does the consolidation/dedup (step 4), reads the verifier verdicts (step 5), writes the report, and does any frontend/non-code fixes directly (step 7), all without subagents.

## 1. Target (state in one line, then fire)

Auto-detect the most recent substantive output: a plan, code/feature, a bug fix, a doc, copy, strategy. State what you're reviewing in ONE line, then go. An explicit arg (`/multi-review10x-lean <thing>`) overrides. Pin the exact files as **absolute paths** (or quote the text) so every reviewer hits the identical target. codex doesn't search for files, so absolute paths are required.

Decide the fleet size from the target:
- **Floor (always): 10 codex.** Never go below this.
- **Scale up to 12-16 codex** for a very large target (many files / a whole feature / a migration) or a high-stakes one (security-sensitive, money, data integrity, irreversible). Use the scale-up dimension pool below so every extra reviewer still gets its own lens.

## 2. Assign dimensions (distinct lenses, no overlap)

The point of a fleet is coverage, not redundancy. Give each reviewer ONE dimension. codex (GPT-5) covers the full breadth below.

**Code target (default matrix, 10 codex):**
- codex-1 - Correctness & logic: does it do what it claims; off-by-one, inverted conditions, wrong operator, broken control flow, return-value misuse.
- codex-2 - Security & trust boundaries: injection, authz/authn gaps, secret exposure, unsafe deserialization, SSRF, path traversal, missing input validation, trust-boundary crossings.
- codex-3 - Edge & failure handling: boundary/empty/null/huge inputs, error paths, partial failure, retries, idempotency, timeout/cancel behavior.
- codex-4 - API, dependency & repo-consistency misuse: wrong library/API usage, broken contracts, footguns, version/supply-chain risk; PLUS does it reinvent the repo's existing shared primitives/helpers instead of reusing them, break repo conventions/idioms, ignore an existing URL/API contract (route, params, response shape), or duplicate logic that should be consolidated.
- codex-5 - Types, contracts & data shape: type/null-safety assumptions, serialization/parse correctness, schema/shape mismatches, encoding.
- codex-6 - Hidden assumptions & contracts: API/shape/type assumptions, undocumented coupling, config/version drift, integration-point mismatches.
- codex-7 - Concurrency, resources & performance: races, deadlocks, leaks (connections, timers, listeners), N+1, unbounded growth, blocking the event loop.
- codex-8 - Data integrity, state & regression: bad mutation, persistence/migration correctness, transaction boundaries, cache coherence; REGRESSION: any existing behavior the change breaks or alters at a call site of the code it touched (trace the callers of every changed symbol).
- codex-9 - Observability & operability: failure visibility, logging/metrics/alerting gaps, debuggability, error-message quality, dead-letter/retry visibility.
- codex-10 - Backwards-compatibility, migration & rollout: breaking changes, migration correctness, deploy/rollback safety, feature-flag and cutover gaps.

**Cover the orphaned lenses too.** Some angles the engine structurally under-covers: over-engineering / simplification, test-coverage gaps & missing cases, maintainability / dead code, and a completeness check (what did the fleet miss). With no Claude layer, fold the highest-value of these into the fleet: assign them to your scale-up instances when you scale up, or append the most relevant one as a SECONDARY ask on a brief whose primary dimension is adjacent (e.g. test-coverage gaps onto codex-3 edge/failure; over-engineering/simplification onto codex-7 concurrency/perf; a completeness "what did we miss" prompt onto codex-6 hidden assumptions). Don't let them silently go uncovered.

**Non-code target (plan / copy / strategy / docs), remap:**
- codex-1 logical holes & internal contradictions; codex-2 unsupported claims & evidence gaps; codex-3 missing cases / risks / failure scenarios; codex-4 dependency/assumption misuse & external-fact accuracy; codex-5 definitional precision (load-bearing-but-undefined terms, ambiguous specs).
- codex-6 hidden assumptions & dependencies; codex-7 feasibility & second-order consequences; codex-8 weakest link / single points of failure; codex-9 measurability (how you'd know it's working); codex-10 compatibility with existing commitments / migration from the status quo.
- Orphaned lenses to fold in: alternative framings, scope/altitude problems, completeness ("what angle was never argued").

**Scale-up dimension pool (when going to 12-16 codex):** codex-11 numerical/temporal correctness (overflow, precision, timezone, locale, encoding); codex-12 resource lifecycle & cleanup (handles, connections, temp files, memory); codex-13 repo-consistency & reuse as a dedicated lens (shared-primitive reuse, conventions/idioms, URL/API-contract adherence, consolidation of duplicated logic), promoted out of codex-4 when you have the budget; codex-14 scalability & load behavior (hotspots, capacity limits, performance under scale); codex-15 failure-mode / blast-radius (cascading failures, SPOFs, graceful degradation); codex-16 test adequacy of the changed paths (missing cases, untested branches, assertion quality). (Remap analogously for non-code: extra angles like ethical/legal exposure, cost, adoption friction, timing/sequencing.)

## 2.5 Compose the fleet's models (mixed by lens, silent)

The global codex default in `~/.codex/config.toml` (currently `gpt-5.6-sol` at `xhigh`) must NEVER be inherited by a fleet: 10+ frontier instances at xhigh is the worst-case token burn, and this lean variant exists to be cheaper. Every instance's command (find stage AND verify stage) carries an explicit `-m "<model>" -c model_reasoning_effort="<effort>"`, and you assign the pair per lens, **silently** (never ask the user, never announce in prose; the launch commands necessarily carry the flags, and the report's fleet accounting is where the mix is summarized).

Assign by lens weight, then tune to the target's difficulty:
- **Heavyweight lenses** (correctness & logic, security, data integrity & regression, hidden assumptions, concurrency): `gpt-5.6-sol` at `high` (`medium` for a small or simple target).
- **Mid lenses** (edge & failure handling, types/contracts, API & dependency misuse, backwards-compat/rollout): `gpt-5.6-terra` at `high` or `medium`, or `gpt-5.6-sol` at `low` when the lens leans on frontier knowledge (API breadth, idioms) more than deep reasoning.
- **Light lenses** (observability, dedicated repo-consistency, scale-up extras, folded-in orphan lenses): `gpt-5.6-luna` at `medium` or `gpt-5.6-terra` at `medium`. (Remap by the same weight logic for non-code lenses.)

The mix is yours to tune per run: a frontier-hard or high-stakes target can push more instances to sol high; a small target can run mostly terra/luna. Three hard bounds: never the whole fleet on sol; sol `xhigh` on at most 1-2 instances and only when the target truly warrants it; never `ultra` anywhere in a fleet (it enables autonomous task delegation inside codex, wrong for unattended runs). The mixed fleet is also a diversity win: different models disagree in useful ways, which is exactly what a review panel wants.

## 3. Launch the fleet in parallel (the faithful per-instance harness)

Launch the codex fleet in WAVES of at most 4 background Bash jobs: fire a wave, confirm each new job's `.jsonl` log exists and is growing (about 30s), then fire the next wave until the whole fleet is up, and arm the consolidated watchdog (3c) right after the final wave (its grace sleep covers the newest jobs; armed earlier it would see wave 1 exit and wrongly conclude the whole fleet is done). Never launch 10+ tracked background jobs in one turn: that has empirically triggered a harness mass-stop of the entire fleet minutes after launch, while waves of 3-4 survive. Read-only is enforced two ways: codex runs in `-s read-only` sandbox, and every brief says report-only. Do not edit any target file yourself while the fleet runs.

Mint a run ID once, before launching: run `openssl rand -hex 4` and note the printed value (e.g. `4fa21c9e`). Substitute that literal value everywhere `<run>` appears below, exactly as you substitute `<model>`. Never submit a command still containing `<run>` (the shell parses the angle brackets as redirections) and never rely on a `$RUN` shell variable (it does not survive across Bash calls, and the quoted heredocs do not expand variables). The `.mr10xl-<run>-` prefix makes every scratch file unique to this run, so concurrent runs, including this same skill in another session, cannot read, clobber, or kill each other's fleets.

### 3a. Pre-flight (do once, before launching)

**codex trust.** codex hangs on a trust prompt in an untrusted dir. Check the working dir once:

```bash
# Exact-match test: a substring grep for 'trusted' would also match "untrusted".
awk -v h='[projects."<project-dir>"]' \
  '$0==h{b=1;next} b&&/^\[/{b=0} b&&/trust_level[[:space:]]*=[[:space:]]*"trusted"/{f=1;exit} END{exit !f}' \
  ~/.codex/config.toml && echo "trusted" || echo "NOT trusted"
```

If NOT trusted, codex cannot run and the 10-codex floor can't be met. Do not silently drop it: tell the user plainly, and offer to either (a) pause so they trust the dir (run codex once interactively there, or add a trusted entry), or (b) abandon this lean run and switch to the `/multi-review10x` skill entirely (its Claude skeptic workflow needs no trusted dir), stating plainly that the lean contract was dropped for this run. Never bolt Claude subagents onto a lean run; the no-Claude rule holds as long as this skill is the one running. Your home directory (`$HOME`) is untrusted by default, so any project not explicitly listed is untrusted.

### 3b. Codex fleet (per-instance, read-only)

For each codex instance `i` (1, 2, 3, ... 10, ...), launch a **separate background Bash job** with this template. The things that change per instance are the number `i`, the **dimension brief** in the heredoc, and the instance's **model/effort pair** from step 2.5:

```bash
cd <project-dir> || exit 1
# Faithful recipe, parameterized. perl alarm = oversized backstop (only fires if the watchdog
#   AND session both died). --json = JSONL heartbeat the watchdog reads. -s read-only = no writes.
#   -o / > use per-run, per-instance filenames so no fleet, this run's or another session's,
#   ever clobbers another. The unique -o filename (.mr10xl-<run>-codex-1.msg.md) is what the
#   watchdog pgrep/pkill matches, NOT the shared "codex exec".
#   -m / model_reasoning_effort = this instance's assigned pair from step 2.5. Never omit them:
#   omitting re-inherits the global sol@xhigh default for the whole fleet.
perl -e 'alarm shift; exec @ARGV' 7200 \
  codex exec --json --color never -s read-only \
  -m "<model>" -c model_reasoning_effort="<effort>" \
  -o .mr10xl-<run>-codex-1.msg.md \
  > .mr10xl-<run>-codex-1.jsonl 2>&1 <<'EOF'
## Hostile review (READ-ONLY, report findings only, edit NOTHING)
Dimension for THIS pass: Correctness & logic.
Target: <pinned absolute path(s)>.

BREAK it along your dimension. Find the worst flaws. Be concrete: exact location
(file:line), what's wrong, why it matters, severity (Critical/High/Med/Low), and a
failing input / counterexample / traced code path if you can produce one. Stay on
your dimension; the rest of the fleet covers the others.

## Operational constraints (verbatim, prevent deadlocks)
- Never invoke a pager. Use `git --no-pager <cmd>` and append `| cat` to anything that could page.
- No network or credential-prompting commands.
- DO NOT edit, write, or create any file. This is read-only review.

## Required output
A findings list: for each flaw -> severity, file:line, what's wrong, why it matters,
and reproduction (failing input / counterexample / code path) if available.
EOF
```

- Add `--skip-git-repo-check` if the target is outside a git repo.
- Launch with the Bash tool's **`run_in_background: true`** (never foreground; the 2-min default would silently background it into an unobservable state).
- Repeat for codex-2 (Security), codex-3 (Edge & failure), codex-4 (API & dependency misuse), codex-5 (Types/contracts), codex-6 (Hidden assumptions), codex-7 (Concurrency/perf), codex-8 (Data integrity & regression), codex-9 (Observability), codex-10 (Backwards-compat/rollout), and any scale-up instances, each with its own number, dimension, and model/effort pair from step 2.5. Leave `7200` oversized; never tune it down to the task.

### 3c. Arm one consolidated watchdog (primary hang defense)

Right after the final wave, start a single **Monitor** that watches every instance at once. Monitor is a deferred tool: load it FIRST with ToolSearch (`select:Monitor`). An InputValidationError means the schema isn't loaded, never that you may skip the watchdog. Set `persistent: true`. It stays silent while the fleet works and only speaks on a per-instance hang or final exit:

```bash
cd <project-dir>
sleep 15   # grace: let the background jobs create their logs before the first liveness check
while :; do
  alive=0
  alerted=0
  for f in .mr10xl-<run>-codex-*.jsonl; do
    [ -e "$f" ] || continue
    # tail -1: the newest match is the codex binary itself; older matches are its wrapper shells,
    # whose child would just read "codex" and hide the real running command.
    p=$(pgrep -f "${f%.jsonl}.msg.md" | tail -1)
    if [ -n "$p" ]; then
      alive=1; now=$(date +%s); mt=$(stat -f %m "$f" 2>/dev/null || echo "$now")
      if [ $((now-mt)) -gt 420 ]; then
        echo "CODEX FROZEN $f $(((now-mt)/60))min. Child: $(pgrep -flP "$p" 2>/dev/null || echo none)"
        tail -n 3 "$f"; alerted=1
      fi
    fi
  done
  [ "$alive" -eq 0 ] && { echo "all CLI reviewers exited"; break; }
  [ "$alerted" -eq 1 ] && sleep 150 || sleep 30
done
```

Reacting:
- **No events** -> the fleet is working. Do nothing; each background job re-invokes you when it exits.
- **CODEX FROZEN `<file>`** -> suspected wedge for THAT instance; investigate before killing. A long step legitimately goes quiet: a full test suite or build inside one tool call emits nothing until it returns. Read the printed Child line together with the tail: a test/build child (`vitest`, `npm`, `tsc`, ...) = healthy long step, stay quiet, but not forever: the SAME child persisting past ~20 min is a process that finished or deadlocked without exiting, which is a hang, so kill it; a pager or credential-prompt child (`less`, `git log`, `ssh`, `security`) = the classic wedge, kill now; no child = stalled stream or silent reasoning, give it the 10-minute bar. Informed kill of only that one: `pkill -f "<file-without-.jsonl>.msg.md"`. The others keep running.
- **all CLI reviewers exited** -> cross-check against the background jobs' own completion notifications before treating the fleet as done (a pgrep enumeration failure can fake this signal), then TaskStop the monitor.

A dead or killed reviewer never blocks the run. Note it and proceed with what returned, as long as the floor intent is honored or its shortfall is surfaced.

## 4. Collect & consolidate

Wait until **every** find-stage CLI job has exited. Do not consolidate early. Then gather every reviewer's findings:
- codex-i -> `.mr10xl-<run>-codex-i.msg.md` (clean finish) or the tail of `.mr10xl-<run>-codex-i.jsonl` (if killed late, salvage the report from the log; label it salvaged).

Merge all findings, then **dedup aggressively** across the whole fleet (same file:line + same root cause = one finding; record every reviewer that flagged it, agreement raises triage priority). Many reviewers across overlapping symptoms will produce heavy duplication and false positives. That is expected.

Write the deduped candidate list to `.mr10xl-<run>-candidates.md`, one numbered finding per entry: `#N | severity | file:line | claim (what's wrong + why) | flagged-by`. This file is the input the verify pass reads.

If dedup leaves nothing, report "fleet reviewed, no findings," sweep scratch, and stop.

## 5. Adversarial verify (a second codex reproduction pass)

With this many reviewers the false-positive rate is high. The bar is hard: **a finding is confirmed ONLY if reproduced** by a failing test, a concrete counterexample, or a traced code path. For consistency findings (reused-primitive, convention, URL/API-contract, consolidation), "reproduced" means citing the exact existing primitive/convention/contract the change diverges from; for regressions, a traced call site that now breaks. Reviewer agreement prioritizes; it never substitutes for reproduction. With no Claude skeptic layer, reproduction is delegated to a fresh codex verify fleet, run on the SAME per-instance harness as step 3 (read-only, perl alarm, per-instance scratch, watchdog).

**Size the verify fleet to the candidate count.** Split `.mr10xl-<run>-candidates.md` into batches of ~8 findings and assign one codex verifier per batch. Bound it: at most 4 codex verifiers. If there are very few candidates, 1 codex verifier over the whole list is enough. Each verifier is given the candidate file and its assigned finding IDs and told to REFUTE each one, defaulting to refuted when it cannot reproduce.

**Verifier models (same explicit-flags rule as step 2.5).** Verifiers default to `gpt-5.6-terra` at `high`; route a batch to `gpt-5.6-sol` at `high` when it contains subtle Critical/High correctness, regression, or security claims whose reproduction genuinely needs frontier reasoning. Silent, as always.

Verify scratch uses a distinct `.mr10xl-<run>-vcodex-*` prefix (same run ID).

Codex verifier `k` (read-only, background):

```bash
cd <project-dir> || exit 1
perl -e 'alarm shift; exec @ARGV' 7200 \
  codex exec --json --color never -s read-only \
  -m "<model>" -c model_reasoning_effort="<effort>" \
  -o .mr10xl-<run>-vcodex-1.msg.md \
  > .mr10xl-<run>-vcodex-1.jsonl 2>&1 <<'EOF'
## Adversarial verification (READ-ONLY, edit NOTHING)
A prior review fleet produced candidate flaws in: <project-dir>/.mr10xl-<run>-candidates.md
Verify ONLY findings #1-#8.

For EACH assigned finding, try to REFUTE it. Confirm it ONLY if you can reproduce it:
a failing test, a concrete counterexample, or a precisely traced code path. For a
consistency finding (reused-primitive, convention, URL/API-contract, consolidation),
reproduction means citing the exact existing primitive/convention/contract in the repo
the change diverges from; for a regression, a traced call site that now breaks. If you
cannot ground it this way, mark it REFUTED. Default to REFUTED when uncertain.

## Operational constraints (verbatim)
- Never invoke a pager. Use `git --no-pager <cmd>` and append `| cat` to anything that could page.
- No network or credential-prompting commands.
- DO NOT edit, write, or create any file.

## Required output
Per finding: id, verdict (CONFIRMED / REFUTED), and either the reproduction
(failing input / counterexample / code path) or the reason the claim does not hold.
EOF
```

Repeat for each verifier batch (vcodex-2 verifies #9-#16, and so on), each with its own number and assigned finding IDs.

Launch the verify fleet (at most 4 jobs, one wave is fine), then arm the watchdog from 3c again with the verify glob swapped in (`.mr10xl-<run>-vcodex-*.jsonl`). When all verifiers exit, read their verdicts and keep a finding ONLY if a verifier marked it CONFIRMED with a concrete reproduction. Drop anything REFUTED or unreproducible, no matter how many find-stage reviewers raised it.

If nothing survives, that is a valid, expected result: report "fleet reviewed, no real flaws," make zero edits, skip steps 6-8. Do not invent nitpicks.

## 6. Report (STOP here, then offer the fix)

Default is report-only. Present the confirmed findings and stop before mutating anything:
- Group by severity (Critical -> Low). Per finding: one line + file:line + which find-stage reviewers flagged it + which verifier confirmed it + how it reproduced.
- State the fleet accounting honestly: how many codex ran in the find stage and their model/effort mix (e.g. `4x sol@high, 4x terra@medium, 2x luna@medium`), and how many codex verifiers ran in the verify stage with their mix. (No Claude subagents run at any point; if you ever spawned one, the lean contract was violated.)
- Note any reviewer that died/was killed and what it would have covered.
- End with an explicit offer: *"Say go and I'll fix the confirmed flaws (routing heavy backend to a fresh codex write-mode pass, frontend/non-code by me), then verify and show the diff."*

Do not proceed to step 7 without the user's clear go-ahead.

## 7. Fix on approval (route by domain)

Only after the user says go:
- **Backend / heavily technical code -> the `/codex` command in write mode**: a fresh, single invocation of the actual `/codex` slash command (via the Skill tool, never a raw `codex exec`) briefed with the confirmed findings plus honest complexity signals so its rubric picks well for the fix. Use the blessed single-instance command here; fixing is one coordinated pass and parallel writes to shared files corrupt the diff.
- **Frontend -> Claude** fixes directly (pairs with the design skills).
- **Non-code (plan, copy, strategy, docs) -> Claude** revises directly.
- If `/codex` is unavailable, Claude does the fix directly.
- Fix all confirmed issues that are genuine improvements. Skip only pure style nitpicks; note any skip as an optional suggestion.

## 8. Verify & final report

Re-read changed files; run tests/build/lint if present; for non-code, re-check each finding against the revision. For code edits show `git --no-pager diff --stat` and a one-line revert pointer. Report concisely: found (brief), fixed + by whom, verified, anything left for the user. Offer one more fleet pass.

## Rules

- **The fleet harness in steps 3 and 5 is the sanctioned hand-driven codex here**, because N-in-parallel cannot use the single-instance `/codex` command. Keep every flag and every per-run, per-instance unique filename: the perl alarm, `--json`, `-o`, `-s read-only`, the `<run>` nonce, and the nonce-scoped pgrep/pkill match. Do NOT "simplify" back to shared scratch names or the broad `pkill -f "codex exec"`; that reintroduces the collision this skill exists to avoid.
- **Each reviewer is its own tracked background job; never a wrapper script.** Never bundle the fleet into one script that launches and waits on all reviewers: one hung reviewer then blocks the wrapper's exit AND its completion notification, erasing both hang signals at once. Per-job tracking keeps every completion signal independent.
- **Never use a global pattern for liveness or kills.** No `pkill -f "codex exec"`, no kill or pgrep pattern that lacks this run's `<run>` ID, and never read a machine-wide pgrep count as your fleet's liveness. Concurrent sessions run identical skills with identical filenames; a global pattern reads their fleet as yours or murders it (both have actually happened).
- **The FIX pass (step 7) uses the real `/codex` slash command**, not the harness. Review fans out; fixing is one coordinated write.
- **Explicit model + effort on every codex instance, find and verify.** Every `codex exec` carries `-m` and `-c model_reasoning_effort=` per the step 2.5 mix (verifiers per step 5). Never inherit the global sol@xhigh default, never run the whole fleet on sol, and keep sol xhigh to at most 1-2 instances. Selection is silent; the mix is summarized in the report's fleet accounting.
- **No Claude subagents, ever.** Finding (step 3) and verification (step 5) both run on codex. Do not spin up a review Workflow, a skeptic fleet, or per-finding verifier subagents. Claude only orchestrates, dedups, reads verdicts, reports, and does frontend/non-code fixes directly.
- **Report-only by default.** Nothing mutates before the user's go-ahead. Only steps 7-8 touch files.
- **Reproduce before you fix.** A finding is confirmed only if a verifier reproduced it. Never fix phantom issues or bend good output to satisfy a nitpick.
- **Honor the floor or surface the shortfall.** At least 10 codex in the find stage. If codex can't run (untrusted dir) or an instance dies, say so plainly; never silently fall below the floor.
- **Sweep this run's scratch before reporting**, however each instance ended (clean, hung, killed): `rm -f .mr10xl-<run>-*`. Never sweep without the run ID; another session's live run may share the directory.
- Heavy by design: 10+ CLI processes (a mixed-model fleet, not uniform frontier) in the find stage, plus a bounded verify fleet. This is the intended cost. Waves of at most 4 (step 3) are the launch mode; never drop below the floor to lighten load.
- Be concise. No em dashes.
