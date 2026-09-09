---
name: review
description: The plugin's single adversarial review. One external reviewer (agy, codex, or a Claude subagent, chosen by the caller or defaulting to codex gpt-6-astra at medium) reads the target under the shared reviewer contract (invariants first, four traversals, self-verification), then Claude verifies every finding against the real code and scores it on impact and likelihood. Inside /build:build it is report-only and returns the scored table; standalone it also routes the blocking fixes to the default executor. Use on /build:review, or when asked to hard-review, stress-test, adversarially review, red-team, find the bugs in, check repo fit of, or catch regressions in the latest code, feature, fix, plan, or doc.
argument-hint: "[target paths] [reviewer=agy|codex:m:e|claude:m] [spec=<path>] [report-only]"
---

# Review

One reviewer, one contract, one verification pass by Claude, one scored table. The review dimensions live in `reference/reviewer-contract.md` and the scoring in `reference/scoring.md`; read both before the first run in a session. Everything under `reference/` and `scripts/` is at `$PLUGIN_ROOT`, resolved once per session with `PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(ls -d ~/.claude/plugins/cache/*/build/*/ | sort -V | tail -1)}"`.

Inside `/build:build` the build passes everything below as arguments and consumes the table; this skill never fixes anything there. Standalone, it reviews and then fixes through the default executor unless `report-only` was given.

## 1. Target

Pin the exact files as absolute paths (or quote the text). Inside a build: the changed paths the caller gave. Standalone: the most recent substantive output, stated in one line. Snapshot the pre-review state if the tree is dirty: `snapshot.sh save review-<tag>`.

## 2. Cycle brief

Write `.build/briefs/<tag>-review.md` with only the cycle-specific content:

- the target paths, absolute, and what changed and why (two or three lines);
- the spec or item brief path when the caller gave one (activates the scope lane; with none, omit the lane and never infer a scope);
- the `Must not regress` list verbatim when the caller gave one (activates the roll-call; with none, omit it and never invent surfaces);
- the already-adjudicated findings: fixed, refuted with the quoted reason, accepted residuals, backlog entries. The reviewer must not re-raise them;
- coverage gaps named by the previous cycle, if any, as explicit routes to walk this time.

Everything else the reviewer needs is in `reference/reviewer-contract.md`, which it reads first by pointer.

## 3. Launch the reviewer (read-only, by role)

Per `reference/roles.md`, one background Bash call, then end the turn and wait for the exit notification:

- **agy:** `run-agy.sh --tag <tag> --plan --model "<resolved>" --read $PLUGIN_ROOT/reference/reviewer-contract.md --brief <cycle brief>`. Plan mode is structurally read-only; the contract says report-only as well; both are required.
- **codex:** `run-codex.sh --tag <tag> --readonly --model <slug> --effort <effort> --read $PLUGIN_ROOT/reference/reviewer-contract.md --brief <cycle brief>`.
- **claude:** no launch script; the Agent tool with `subagent_type: build:reviewer` and the role's model, prompt: read `$PLUGIN_ROOT/reference/reviewer-contract.md`, then the cycle brief, then review.

The `--model` value for agy is the part after `agy:` in the ledger's triple (the script strips the prefix if you pass the whole triple).

Never hand-roll the CLI, never pick your own flags, never run two reviewers in one cycle. If the run exits with code 2 (no report), relaunch once per the retry ladder; a report-bearing run with `status: ERROR` is a good run.

**Stray-edit guard.** After the reviewer returns: `snapshot.sh changed review-<tag>` (or `git status --short`). Revert only the reviewer's stray edits with `snapshot.sh restore`, never a blanket checkout of a file that already had uncommitted changes. If a stray edit cannot be isolated, surface it.

## 3b. The interrogation round (one resume, before you verify)

A reviewer put in front of its own finished report kills its weak findings and sometimes finds the one it missed; the same instruction given during generation only makes it timid. So resume the reviewer once, with its report in front of it, before spending your own verification effort:

- **agy:** `run-agy.sh --tag <tag>-q --plan --model "<resolved>" --conversation <id from the printed CONVERSATION line> --prompt "<the prompt below>"` (no `--brief` is needed on a resume; the conversation already holds the target).
- **codex:** codex has no conversation resume, so this is a second cold `run-codex.sh --readonly --tag <tag>-q` run whose brief `.build/briefs/<tag>-q.md` is the first report verbatim, the target paths, and the prompt below. Because that doubles the reviewer cost per cycle, run it for codex only on cycles that returned findings; skip it on a clean confirming cycle.
- **claude:** `SendMessage` to the same reviewer agent with the prompt below.

If it reported findings: *"For each finding you reported, state the strongest reason it might be WRONG, then go and check that specific thing in the code now. Withdraw any finding your check kills and say which. For each survivor, add what you checked and what you saw. Add a new finding only if the check itself uncovered one."* If it came back clean or with only low-impact findings: *"Your clean verdict is under audit. Name the three places you are LEAST certain about, argue as persuasively as the code allows that each IS broken, then say plainly whether you believe it."*

Drop withdrawn findings (note the count in the accounting), keep the added checks with their findings, add anything new. If the resume fails or returns nothing, carry on with the original report; this round never blocks.

## 4. Verify (Claude, against the real code)

Read the report through the launch script's output. Then, for every finding, open the code it names and decide:

- **FABRICATED**: the code or behavior it describes is not there. Drop it and name it in the table.
- **REFUTED**: the mechanism cannot produce the outcome. Record the reason.
- **CONFIRMED**: the mechanism exists and produces the outcome. Reproduce it in the cheapest honest way: a traced path across the real files, a concrete counterexample, or a failing test you run. For a consistency finding, cite the exact existing primitive, contract, or convention diverged from. For a regression, the traced call site that now breaks.
- **UNVERIFIABLE**: needs a live service, database, or timing control you do not have. Keep it, name the missing capability.

Cross-check the reviewer's claims against its tool trail (printed by the launch script): a chain asserted across files the reviewer never opened is a guess, not a trace; keep it as a candidate with its certainty stripped. A trail with almost no reads did not do the work, whatever the report says.

**Protected surfaces are a required roll-call.** Every listed surface must have a verdict. A surface left out or marked NOT CHECKED is coverage you owe: trace it yourself, or mark it UNVERIFIABLE with the missing capability. Silence is never a pass.

## 5. Score

Per `reference/scoring.md`: impact and likelihood for every CONFIRMED and UNVERIFIABLE finding, quoting the reviewer's proposal when you agree and overriding with one line when you do not; the cause class; then the rules on top (supporting artifacts score by the bug they hide, out-of-scope code goes to the backlog, spec-accepted costs are refuted by spec with the line quoted, machinery-requiring fixes never enter a fix round, protected surfaces are never likelihood 1). Blocking is impact times likelihood of 6 or more.

Structure and scope advisories pass through as their own sections, never scored, never fixed here.

## 6. Output

Write `.build/runs/<tag>.findings.md` and print it:

```
| id | verdict | impact x likelihood | cause | blocking | where | mechanism (one line) | reproduction / reason |
```

followed by: downgrades and refutations with reasons, fabrications by reviewer, UNVERIFIABLE with missing capability, the protected-surfaces roll-call table, the scope advisory, the structure advisory, and the reviewer's coverage gaps (what it could not reach). A clean cycle must come with named gaps or an explicit statement that there are none.

Then a one-line accounting: reviewer triple, raw findings, verified, blocking.

## 7. Standalone only: fix, verify, report

Skip this inside `/build:build`, or when `report-only` was given.

Route blocking findings to the default executor per `roles.md` (a Claude subagent for frontend fixes, via `build:frontend`), briefed with the findings' mechanisms and reproductions and pointed at `reference/executor-contract.md`. Never fix on the main thread. Then re-read the changed files, run tests, show `git --no-pager diff --stat` and a one-line revert pointer, and report: found, fixed by whom, verified, anything left. Non-blocking findings are reported as optional.

## Rules

- Exactly one reviewer per cycle. No fleets, no Claude skeptic subagents alongside, no second engine (the whole-build gate in `/build:build` is the one place a second reviewer runs, and the build invokes this skill twice for it).
- The reviewer reports; Claude verifies and scores; the executor fixes. Three actors, never merged.
- Reproduce before you confirm; never fix a phantom.
- Depth over breadth. Never treat finding volume as review quality.
- Sweep nothing mid-build; the build owns `.build/`. Standalone, remove `.build/runs/<tag>.*` after reporting.
- No em dashes.
