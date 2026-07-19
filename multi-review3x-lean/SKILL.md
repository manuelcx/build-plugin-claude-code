---
name: multi-review3x-lean
description: Mid-intensity adversarial review of your latest output by a fixed trio of EXTERNAL codex reviewers with NO Claude subagents. Each codex hits a merged dimension cluster (correctness/data; security/integrity/regression; system-fit/repo-consistency including conventions, shared-primitive reuse, URL/API contracts, consolidation), then a codex reproduction pass verifies survivors. Report, then fix on your go-ahead. Use on /multi-review3x-lean and on requests for a 3x, trio, or mid-intensity adversarial, repo-consistency, or regression review run on the external engine only. For the version that adds a Claude layer, use /multi-review3x; for a maximum external fleet, use /multi-review10x-lean.
---

# Multi-Review 3x Lean

A fixed trio of adversarial codex reviewers with **zero Claude subagents**: the find stage is exactly 3 codex, and the verify stage is a codex reproduction pass. Claude orchestrates only: it pins the target, assigns clusters, drives the harness, dedups, reads the verifiers, reports, and (on approval) routes the fix. Each codex gets a DISTINCT merged cluster so the three do not surface the same shallow bug. Keep only flaws that reproduce, report them, and fix only on your explicit go-ahead.

Default contract: **review and report, then fix on approval.** Run the whole review autonomously (launch the trio, watch it, consolidate, run the verify pass, report). Do NOT mutate anything until the user says go.

Why this drives the CLI by hand: running 3 codex at once is incompatible with the single-instance `/codex` command, which writes to fixed scratch paths and tracks/kills one instance per directory, so N of them in parallel clobber each other's logs and confuse its watchdog. This skill carries the same anti-hang recipe as that command, parameterized per run and per instance (nonce-unique scratch files, nonce-scoped watchdog match). Every protection is preserved; see the harness in step 3 and do not strip a single flag.

**No Claude subagents, at any stage.** Both finding and verification run on codex. Claude itself still consolidates and dedups (step 4), reads verdicts (step 5), writes the report, and does any frontend/non-code fixes directly (step 7), all without subagents.

## 1. Target (state in one line, then fire)

Auto-detect the most recent substantive output: a plan, code/feature, a bug fix, a doc, copy, strategy. State what you're reviewing in ONE line, then go. An explicit arg (`/multi-review3x-lean <thing>`) overrides. Pin the exact files as **absolute paths** (or quote the text) so every reviewer hits the identical target. codex doesn't search for files, so absolute paths are required.

**Fleet size: EXACTLY 3 codex in the find stage, always.** Never fewer, never more. No scale-up: if the target deserves a bigger fleet, that is not this skill's job.

## 2. Assign the three clusters (distinct, no overlap)

**Code target:**
- codex-1 - Correctness & data: correctness and logic (off-by-one, inverted conditions, wrong operator, broken control flow, return-value misuse); edge and failure handling (boundary/empty/null/huge inputs, error paths, partial failure, retries, idempotency, timeout/cancel); types, contracts and data shape (null-safety, serialization/parse correctness, schema mismatches, encoding).
- codex-2 - Security, integrity & regression: security and trust boundaries (injection, authz/authn gaps, secret exposure, SSRF, path traversal, missing input validation); hidden assumptions (undocumented coupling, config/version drift, integration-point mismatches); data integrity and state (bad mutation, persistence/migration correctness, transaction boundaries, cache coherence); REGRESSION: any existing behavior the change breaks or alters at a call site of the code it touched (trace the callers of every changed symbol).
- codex-3 - System & repo fit: API and dependency misuse plus repo-consistency (reinventing existing shared primitives/helpers, breaking repo conventions/idioms, ignoring an existing URL/API contract, duplicating logic that should be consolidated); concurrency, resources and performance (races, leaks, N+1, unbounded growth, blocking); backwards-compatibility, migration and rollout; observability (failure visibility, logging gaps, error-message quality). SECONDARY ask, folded in because no Claude layer covers it: over-engineering / simplification and test-coverage gaps on the changed paths.

**Non-code target (plan / copy / strategy / docs), remap:**
- codex-1 logical holes and internal contradictions; missing cases, risks and failure scenarios; definitional precision (load-bearing-but-undefined terms, ambiguous specs).
- codex-2 unsupported claims and evidence gaps; hidden assumptions and dependencies; weakest link / single points of failure.
- codex-3 feasibility and second-order consequences; measurability; compatibility with existing commitments and migration from the status quo. SECONDARY ask: scope/altitude problems and completeness (what angle was never argued).

## 2.5 Assign each codex a model and effort (mixed, silent)

The global codex default in `~/.codex/config.toml` (currently `gpt-5.6-sol` at `xhigh`) must NEVER be inherited. Every instance's command (find stage AND verify stage) carries an explicit `-m "<model>" -c model_reasoning_effort="<effort>"`, assigned per cluster, **silently** (never ask the user, never announce in prose; the launch commands necessarily carry the flags, and the report's fleet accounting is where the mix is summarized).

Default mix, tuned to the target's difficulty:
- codex-2 (security/integrity/regression, the heavyweight cluster): `gpt-5.6-sol` at `high` (`medium` for a small or simple target).
- codex-1 (correctness/data): `gpt-5.6-terra` at `high`, or `gpt-5.6-sol` at `medium` for gnarly logic.
- codex-3 (system/repo fit, knowledge-heavy): `gpt-5.6-terra` at `medium`, or `gpt-5.6-sol` at `low` when the target leans on API breadth and idiom judgment.

Three hard bounds: never all 3 on sol; sol `xhigh` on at most 1 instance and only when the target truly warrants it; never `ultra` (it enables autonomous task delegation inside codex, wrong for unattended runs).

## 3. Launch the trio in parallel (the faithful per-instance harness)

Fire EVERYTHING in the same turn so it all runs concurrently: each codex as its own background Bash job, then arm one consolidated watchdog. Read-only is enforced two ways: codex runs in `-s read-only` sandbox, and every brief says report-only. Do not edit any target file yourself while the trio runs.

Mint a run ID once, before launching: run `openssl rand -hex 4` and note the printed value (e.g. `4fa21c9e`). Substitute that literal value everywhere `<run>` appears below, exactly as you substitute `<model>`. Never submit a command still containing `<run>` (the shell parses the angle brackets as redirections) and never rely on a `$RUN` shell variable (it does not survive across Bash calls, and the quoted heredocs do not expand variables). The `.mr3xl-<run>-` prefix makes every scratch file unique to this run, so concurrent runs, including this same skill in another session, cannot read, clobber, or kill each other's fleets. Three background jobs launch safely in one turn; never exceed 4 in a single turn.

### 3a. Pre-flight (do once, before launching)

**codex trust.** codex hangs on a trust prompt in an untrusted dir. Check the working dir once:

```bash
# Exact-match test: a substring grep for 'trusted' would also match "untrusted".
awk -v h='[projects."<project-dir>"]' \
  '$0==h{b=1;next} b&&/^\[/{b=0} b&&/trust_level[[:space:]]*=[[:space:]]*"trusted"/{f=1;exit} END{exit !f}' \
  ~/.codex/config.toml && echo "trusted" || echo "NOT trusted"
```

If NOT trusted, codex cannot run and the trio can't launch. Do not silently drop it: tell the user plainly, and offer to either (a) pause so they trust the dir (run codex once interactively there, or add a trusted entry), or (b) abandon this lean run and switch to the `/multi-review3x` skill entirely (its Claude skeptic needs no trusted dir), stating plainly that the lean contract was dropped for this run. Never bolt Claude subagents onto a lean run; the no-Claude rule holds as long as this skill is the one running. Your home directory (`$HOME`) is untrusted by default, so any project not explicitly listed is untrusted.

### 3b. Codex trio (per-instance, read-only)

For each codex instance `i` (1, 2, 3), launch a **separate background Bash job** with this template. The things that change per instance are the number `i`, the **cluster brief** in the heredoc, and the instance's **model/effort pair** from step 2.5:

```bash
cd <project-dir> || exit 1
# Faithful recipe, parameterized. perl alarm = oversized backstop (only fires if the watchdog
#   AND session both died). --json = JSONL heartbeat the watchdog reads. -s read-only = no writes.
#   -o / > use per-run, per-instance filenames so no fleet, this run's or another session's,
#   ever clobbers another. The unique -o filename (.mr3xl-<run>-codex-1.msg.md) is what the
#   watchdog pgrep/pkill matches.
#   -m / model_reasoning_effort = this instance's assigned pair from step 2.5. Never omit them:
#   omitting re-inherits the global sol@xhigh default.
perl -e 'alarm shift; exec @ARGV' 7200 \
  codex exec --json --color never -s read-only \
  -m "<model>" -c model_reasoning_effort="<effort>" \
  -o .mr3xl-<run>-codex-1.msg.md \
  > .mr3xl-<run>-codex-1.jsonl 2>&1 <<'EOF'
## Hostile review (READ-ONLY, report findings only, edit NOTHING)
Cluster for THIS pass: Correctness & data (correctness/logic, edge & failure handling, types/contracts/data shape).
Target: <pinned absolute path(s)>.

BREAK it along your cluster. Find the worst flaws. Be concrete: exact location
(file:line), what's wrong, why it matters, severity (Critical/High/Med/Low), and a
failing input / counterexample / traced code path if you can produce one. Stay on
your cluster; the rest of the trio covers the others.

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
- Repeat for codex-2 (Security, integrity & regression) and codex-3 (System & repo fit), each with its own number, cluster brief, and model/effort pair. Leave `7200` oversized; never tune it down to the task.

### 3c. Arm one consolidated watchdog (primary hang defense)

Right after launching the trio, start a single **Monitor** that watches every instance at once. Monitor is a deferred tool: load it FIRST with ToolSearch (`select:Monitor`). An InputValidationError means the schema isn't loaded, never that you may skip the watchdog. Set `persistent: true`.

```bash
cd <project-dir>
sleep 15   # grace: let the background jobs create their logs before the first liveness check
while :; do
  alive=0
  alerted=0
  for f in .mr3xl-<run>-codex-*.jsonl; do
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
- **No events** -> the trio is working. Do nothing; each background job re-invokes you when it exits.
- **CODEX FROZEN `<file>`** -> suspected wedge for THAT instance; investigate before killing. A long step legitimately goes quiet: a full test suite or build inside one tool call emits nothing until it returns. Read the printed Child line together with the tail: a test/build child (`vitest`, `npm`, `tsc`, ...) = healthy long step, stay quiet, but not forever: the SAME child persisting past ~20 min is a process that finished or deadlocked without exiting, which is a hang, so kill it; a pager or credential-prompt child (`less`, `git log`, `ssh`, `security`) = the classic wedge, kill now; no child = stalled stream or silent reasoning, give it the 10-minute bar. Informed kill of only that one: `pkill -f "<file-without-.jsonl>.msg.md"`. The others keep running.
- **all CLI reviewers exited** -> cross-check against the background jobs' own completion notifications before treating the trio as done (a pgrep enumeration failure can fake this signal), then TaskStop the monitor.

A dead or killed reviewer never blocks the run. Note it plainly in the report and proceed with what returned.

## 4. Collect & consolidate

Wait until **every** find-stage job has exited. Do not consolidate early. Gather findings:
- codex-i -> `.mr3xl-<run>-codex-i.msg.md` (clean finish) or the tail of `.mr3xl-<run>-codex-i.jsonl` (if killed late, salvage the report from the log; label it salvaged).

Merge everything, then **dedup** (same file:line + same root cause = one finding; record every reviewer that flagged it, agreement raises triage priority).

Write the deduped candidate list to `.mr3xl-<run>-candidates.md`, one numbered finding per entry: `#N | severity | file:line | claim (what's wrong + why) | flagged-by`. This file is the input the verify pass reads.

If dedup leaves nothing, report "trio reviewed, no findings," sweep scratch, and stop.

## 5. Adversarial verify (a codex reproduction pass)

**A finding is confirmed ONLY if reproduced**: a failing test, a concrete counterexample, or a traced code path. For consistency findings (reused-primitive, convention, URL/API-contract, consolidation), "reproduced" means citing the exact existing primitive/convention/contract the change diverges from; for regressions, a traced call site that now breaks. Reviewer agreement prioritizes; it never substitutes for reproduction. Reproduction is delegated to a fresh codex verify pass on the SAME per-instance harness as step 3 (read-only, perl alarm, per-instance scratch, watchdog).

**Exactly ONE codex verifier, always**, handed the full candidate list and told to REFUTE each finding, defaulting to refuted when it cannot reproduce.

**Verifier model (same explicit-flags rule as step 2.5):** default `gpt-5.6-terra` at `high`; use `gpt-5.6-sol` at `high` when the list holds subtle Critical/High correctness, security, or regression claims. Silent, as always.

Verify scratch uses the `.mr3xl-<run>-vcodex-*` prefix (same run ID). The verifier (read-only, background):

```bash
cd <project-dir> || exit 1
perl -e 'alarm shift; exec @ARGV' 7200 \
  codex exec --json --color never -s read-only \
  -m "<model>" -c model_reasoning_effort="<effort>" \
  -o .mr3xl-<run>-vcodex-1.msg.md \
  > .mr3xl-<run>-vcodex-1.jsonl 2>&1 <<'EOF'
## Adversarial verification (READ-ONLY, edit NOTHING)
A prior review trio produced candidate flaws in: <project-dir>/.mr3xl-<run>-candidates.md
Verify ALL findings in the file.

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

Launch the verify pass, then arm the watchdog from 3c again with the verify glob swapped in (`.mr3xl-<run>-vcodex-*.jsonl`). When the verifier exits, keep a finding ONLY if marked CONFIRMED with a concrete reproduction. Drop anything REFUTED or unreproducible, no matter how many find-stage reviewers raised it.

If nothing survives, that is a valid, expected result: report "trio reviewed, no real flaws," make zero edits, skip steps 6-8. Do not invent nitpicks.

## 6. Report (STOP here, then offer the fix)

Default is report-only. Present the confirmed findings and stop before mutating anything:
- Group by severity (Critical -> Low). Per finding: one line + file:line + which find-stage reviewers flagged it + which verifier confirmed it + how it reproduced.
- State the fleet accounting honestly: the 3 find-stage codex with their model/effort mix (e.g. `1x sol@high, 1x terra@high, 1x terra@medium`), and the verifier with its. (No Claude subagents run at any point; if you ever spawned one, the lean contract was violated.)
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

Re-read changed files; run tests/build/lint if present; for non-code, re-check each finding against the revision. For code edits show `git --no-pager diff --stat` and a one-line revert pointer. Report concisely: found (brief), fixed + by whom, verified, anything left for the user. Offer one more pass.

## Rules

- **The harness in steps 3 and 5 is the only sanctioned hand-driven codex here.** Keep every flag and every per-run, per-instance unique filename: the perl alarm, `--json`, `-o`, `-s read-only`, the `-m`/effort pair, the `<run>` nonce, and the nonce-scoped pgrep/pkill match.
- **Each reviewer is its own tracked background job; never a wrapper script.** Never bundle the fleet into one script that launches and waits on all reviewers: one hung reviewer then blocks the wrapper's exit AND its completion notification, erasing both hang signals at once. Per-job tracking keeps every completion signal independent.
- **Never use a global pattern for liveness or kills.** No `pkill -f "codex exec"`, no kill or pgrep pattern that lacks this run's `<run>` ID, and never read a machine-wide pgrep count as your fleet's liveness. Concurrent sessions run identical skills with identical filenames; a global pattern reads their fleet as yours or murders it (both have actually happened).
- **The FIX pass (step 7) uses the real `/codex` slash command**, not the harness. Review fans out; fixing is one coordinated write.
- **Exactly 3 codex in the find stage, exactly 1 codex verifier.** Fixed, always. Never scale.
- **No Claude subagents, ever.** Finding and verification both run on codex. Claude only orchestrates, dedups, reads verdicts, reports, and does frontend/non-code fixes directly.
- **Explicit model + effort on every codex instance, find and verify.** Never inherit the global sol@xhigh default; never run everything on sol. Selection is silent; the mix is summarized in the report's fleet accounting.
- **Report-only by default.** Nothing mutates before the user's go-ahead. Only steps 7-8 touch files.
- **Reproduce before you fix.** A finding is confirmed only if a verifier reproduced it. Never fix phantom issues or bend good output to satisfy a nitpick.
- **Sweep this run's scratch before reporting**, however each instance ended: `rm -f .mr3xl-<run>-*`. Never sweep without the run ID; another session's live run may share the directory.
- Be concise. No em dashes.
