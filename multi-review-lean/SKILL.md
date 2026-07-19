---
name: multi-review-lean
description: Leaner stress-test of your own latest output, then fix what's broken. Runs one external adversarial reviewer (/codex) with NO Claude skeptic subagents, keeps only verified-real flaws, and fixes them. Also checks the change fits the repo: conventions, reuse of shared primitives, an existing URL/API contract, consolidation of duplicated logic, and whether a regression was introduced. Use on /multi-review-lean and on requests for a lighter/faster/cheaper hard-review, stress-test, adversarial review, red-team, repo-consistency check, or regression check of the latest plan, code, feature, bug fix, or output when you want only the external engine and not a Claude subagent workflow. Reviews, then fixes.
---

# Multi-Review Lean

One external adversarial reviewer (`/codex`) stress-tests the target; NO Claude skeptic subagents at any stage. Claude orchestrates, consolidates, verifies, and fixes.

The deliverable is fixed output when something real is found, not a report. Run autonomously: find, fix, verify, report. Do not ask permission to fix; the user pre-authorized it.

## 1. Target (state in one line, then fire)
Auto-detect the most recent substantive output: a plan, code/feature, a bug fix, a doc, copy, strategy. State what you're reviewing in ONE line, then go. An explicit arg (`/multi-review-lean <thing>`) overrides. Pin the exact files as absolute paths (or quote the text) so codex hits the identical target.

## 2. Review: codex, READ-ONLY
Read-only is enforced by the brief: codex defaults to write mode, so the brief is the only thing holding it back. Do not edit any target file yourself while it runs.

Adversarial brief, with the pinned absolute path(s) embedded (codex needs them; it doesn't search for files): *"Hostile review of the target at `<paths>`. BREAK it. Find the worst flaws: bugs, logic errors, edge/failure cases, security holes, wrong assumptions, gaps. ALSO check the change FITS THE REPO: flag where it reinvents logic instead of reusing an existing shared primitive/helper/util, breaks the repo's conventions/idioms, ignores an existing URL/API contract (route, params, response shape) when one already exists, or duplicates logic that should be consolidated. And flag REGRESSIONS: any existing behavior the change breaks or alters at a call site of the code it touches. Be concrete: exact location, what's wrong, why it matters, severity (Critical/High/Med/Low). Show a failing input, counterexample, or the existing primitive/contract it should have used. DO NOT edit anything; report findings only."*

Fire codex:
- **`/codex` — you MUST invoke it as the actual slash command (via the Skill tool), passing the adversarial brief as the argument. This is not optional.** Do NOT hand-roll the underlying CLI (`codex exec …`) in a Bash call yourself. The command exists *precisely because* the raw CLI hangs: codex stalls forever with no hard timeout, on a trust prompt, or on a pager (the `/codex` command wraps it in a `perl` wall-clock kill, streams a JSONL heartbeat, and pre-flights the trust check). **If you reconstruct the CLI instead of invoking the command, IT WILL HANG AND THE REVIEW WILL FAIL — every single time, no exceptions. So invoke the command.** Let the command's own hang-handling and hard timeout do their job (the `/codex` command already backgrounds codex; never run it foreground). `/codex` silently picks the codex model and reasoning effort from its rubric: give its brief honest complexity signals (target size, stakes, difficulty) and do not pin a model or effort unless the user did.

If the working tree is dirty when the review starts, snapshot the pre-review state BEFORE firing codex (`git stash create` and note the hash, or `git --no-pager diff > .mr-baseline.patch`); the target under review is often exactly that uncommitted work.

Wait for codex to return before consolidating. If it can't run (e.g. codex needs a trusted git dir), hangs, fails, or edits despite the brief: note it and revert ONLY codex's stray edits, isolated against the pre-review snapshot. Never blanket `git checkout -- <file>` a file that already had uncommitted changes; that destroys the user's work along with the stray edit. If a stray edit can't be isolated, surface it instead of reverting. If codex dies, report that and stop.

## 3. Consolidate
Take codex's findings, dedup, then confirm. A finding is confirmed ONLY if reproduced: a failing test, a concrete counterexample, or a traced code path. For consistency findings (reused-primitive, convention, URL/API-contract, consolidation), "reproduced" means citing the exact existing primitive/convention/contract in the repo that the change diverges from; for regressions, a traced call site that now breaks or changes behavior. Drop anything you can't ground this way. Output a short trace: confirmed issues as severity + one line + how it reproduced.

If nothing survives, that's a valid, expected result: report "reviewed, no real flaws," make zero edits, skip steps 4-5. Do not invent nitpicks to have something to fix.

## 4. Fix (the point): route by domain
- **Backend / heavily technical code → the `/codex` command in write mode**: a fresh, separate invocation of the `/codex` command (again, the actual slash command via the Skill tool, never a raw `codex exec`) briefed with the confirmed findings ("fix these, report what you changed") plus the same honest complexity signals as the review brief, so its rubric picks well for the fix too.
- **Frontend → Claude** fixes directly (pairs with the design skills).
- **Non-code (plan, copy, strategy, docs) → Claude** revises directly.
- If `/codex` is unavailable, Claude does the fix directly.
- Fix all confirmed issues that are genuine improvements. Skip only pure style nitpicks; if you skip anything, note it as an optional suggestion in the report.

## 5. Verify & report
Re-read changed files; run tests/build/lint if present; for non-code, re-check each finding against the revision. For code edits, show `git --no-pager diff --stat` and a one-line revert pointer so the user sees exactly what the unattended run changed. Report concisely: found (brief), fixed + by whom, verified, anything left for the user. Offer one more pass to go again.

## Rules
- **codex ALWAYS runs through its `/codex` command, full stop.** Never reconstruct `codex exec` by hand and never pick your own flags: the raw CLI hangs, the command carries the only working anti-hang recipe. If the command genuinely isn't available, drop the reviewer; do not improvise a substitute CLI.
- **No Claude skeptic subagents.** This is the whole point of the lean variant: do not spin up a review Workflow or fan out reviewer subagents. The review engine is exactly codex. (Claude still does the consolidation/reproduction in step 3 and the frontend/non-code fixes in step 4, directly, not via subagents.)
- Only step 4 mutates. The review `/codex` call and the fix `/codex` call are separate calls.
- Reproduce before you fix: never fix phantom issues or bend good output to satisfy a nitpick.
- Sweep scratch files before reporting, however the reviewer ended (clean, hung, or killed): `rm -f .codex-run.jsonl .codex-last-message.md`. The command body only cleans up on a clean finish.
- Degrade gracefully; scale effort to target size.
- Be concise. No em dashes.
