---
name: review
description: The plugin's single adversarial review. One external reviewer (agy, codex, or a Claude subagent, chosen by the caller or defaulting to codex gpt-6.1-sol at high) reads the target under the shared reviewer contract (invariants first, four traversals, self-verification); a mechanical quote check and an interrogation round weed out weak findings; then the judge (a fresh Claude opus subagent by default, tunable) verifies every finding against the real code and scores it on impact and likelihood. Inside /build:build it is report-only and returns the judge's table; standalone it also routes the blocking fixes to the default executor. Use on /build:review, or when asked to hard-review, stress-test, adversarially review, red-team, find the bugs in, check repo fit of, or catch regressions in the latest code, feature, fix, plan, or doc.
argument-hint: "[target paths] [reviewer=agy|codex:m:e|claude:m] [judge=claude:m|codex:m:e|agy] [spec=<path>] [report-only] [stop-after=interrogation]"
---

# Review

One reviewer, one contract, one quote check, one interrogation, one judge, one scored table. The review dimensions live in `reference/reviewer-contract.md`, the judging in `reference/judge-contract.md`, and the scoring in `reference/scoring.md`. Resolve the plugin root once per session with the command in `reference/roles.md` ("Where the plugin root is"); every `$PLUGIN_ROOT` below is that printed path, written literally. Inside an open build it prints the build's pinned copy.

Inside `/build:build` the build passes everything below as arguments and consumes the table; this skill never fixes anything there. Standalone, it reviews and then fixes through the default executor unless `report-only` was given. `stop-after=interrogation` (used by `/build:spec-certify`, which judges once per cycle itself) returns the saved report and the quote-check result without running the judge.

## 1. Target

Pin the exact files as absolute paths (or quote the text). Inside a build: the changed paths the caller gave. Standalone: the most recent substantive output, stated in one line. Snapshot the pre-review state: `snapshot.sh save review-<tag>`.

## 2. Cycle brief

Write `.build/briefs/<tag>-review.md` with only the cycle-specific content:

- the target paths, absolute, and what changed and why (two or three lines);
- the spec or item brief path when the caller gave one (activates the scope lane; with none, omit the lane and never infer a scope);
- the `Must not regress` list verbatim when the caller gave one (activates the roll-call; with none, omit it and never invent surfaces);
- the already-adjudicated findings: fixed, refuted with the quoted reason, accepted residuals, backlog entries. The reviewer must not re-raise them;
- coverage gaps named by the previous cycle, if any, as explicit routes to walk this time.

Everything else the reviewer needs is in `reference/reviewer-contract.md`, which it reads first by pointer.

## 3. Launch the reviewer (read-only, by role)

Per `reference/roles.md`, one background launch, then end the turn and wait for the exit notification:

- **agy:** `run-agy.sh --tag <tag> --plan --model "<resolved>" --read $PLUGIN_ROOT/reference/reviewer-contract.md --read $PLUGIN_ROOT/reference/local-environment.md --brief <cycle brief>`. Plan mode is structurally read-only; the contract says report-only as well; both are required.
- **codex:** `run-codex.sh --tag <tag> --readonly --model <slug> --effort <effort> --read $PLUGIN_ROOT/reference/reviewer-contract.md --read $PLUGIN_ROOT/reference/local-environment.md --brief <cycle brief>`.
- **claude:** the Agent tool with `subagent_type: build:reviewer` and the role's model, in the background; prompt: read the reviewer contract, then the cycle brief, then review, and write the full report to `.build/runs/<tag>.report.md`.

Save the report to `.build/runs/<tag>.report.md` without reading it into your own context: `agy-report.py --text <log> > <file>` for agy, a copy of `<tag>.last.md` for codex; a Claude reviewer writes it itself. Never hand-roll the CLI, never run two reviewers in one cycle. Exit codes follow the retry ladder; a report-bearing run with `status: ERROR` is a good run.

**Stray-edit guard.** After the reviewer returns: `snapshot.sh changed review-<tag>`. Revert only the reviewer's stray edits with `snapshot.sh restore`, never a blanket checkout of a file that already had uncommitted changes.

## 4. After the review, always in this order

**4a. Quote check.** `quote-check.py .build/runs/<tag>.report.md <target paths> > .build/runs/<tag>.quotes.txt`. It marks every quoted passage FOUND, PARTIAL, or NOT FOUND. It settles nothing by itself: it only tells the next two steps which findings rest on text that is not in the target.

**4b. Interrogation (one resume).** A reviewer put in front of its own finished report kills its weak findings and sometimes finds the one it missed. Skip it only for findings whose quoted text the check marked NOT FOUND, since the judge treats those as likely fabrications anyway; ask about every other finding. Skip the round entirely when no finding remains to ask about.

- **agy:** `run-agy.sh --tag <tag>-q --plan --model "<resolved>" --conversation <id from the printed CONVERSATION line> --prompt "<the prompt below>"`.
- **codex:** a second cold `run-codex.sh --readonly --tag <tag>-q --model <slug> --effort <effort>` run whose brief `.build/briefs/<tag>-q.md` is the first report path, the target paths, and the prompt below.
- **claude:** `SendMessage` to the same reviewer agent with the prompt below, asking it to rewrite `.build/runs/<tag>.report.md`.

If it reported findings: *"For each finding you reported, state the strongest reason it might be WRONG, then go and check that specific thing in the code now. Withdraw any finding your check kills and say which. For each survivor, add what you checked and what you saw. Add a new finding only if the check itself uncovered one."* If it came back clean or with only low-impact findings: *"Your clean verdict is under audit. Name the three places you are LEAST certain about, argue as persuasively as the code allows that each IS broken, then say plainly whether you believe it."* Save the answer next to the report as `<tag>-q.report.md`. If the resume fails, carry on with the original report; this round never blocks.

**4c. Judge.** Stop here when the caller passed `stop-after=interrogation`. Otherwise write `.build/briefs/<tag>-judge.md`: the target paths, the cycle brief path, the report paths (first report and interrogation answer), the quote-check file, the adjudicated list, and the protected list. Launch the locked judge (default `claude:opus:medium`):

- **claude:** the Agent tool with `subagent_type: build:judge` and the role's model, in the background; prompt: read the judge contract and scoring, then the judge brief, and write the findings table to `.build/runs/<tag>.findings.md`.
- **codex:** `run-codex.sh --tag <tag>-judge --readonly --model <slug> --effort <effort> --read $PLUGIN_ROOT/reference/judge-contract.md --read $PLUGIN_ROOT/reference/scoring.md --read $PLUGIN_ROOT/reference/local-environment.md --brief <judge brief>`; copy `<tag>-judge.last.md` to the findings file.
- **agy:** the same with `run-agy.sh --plan`; `agy-report.py --text <log> > <findings file>`.

The judge verifies every finding against the code, scores it, and returns the table defined in `judge-contract.md`. You read only that table.

## 5. Output

The findings file `.build/runs/<tag>.findings.md` is the judge's table plus its roll-call, advisories, gaps, and one-line accounting. Inside a build, print its blocking rows and the accounting line, and return. A clean cycle must come with named gaps or an explicit statement that there are none.

## 6. Standalone only: fix, verify, report

Skip this inside `/build:build`, or when `report-only` was given.

Route blocking findings to the default executor per `roles.md` (a Claude subagent for frontend fixes, via `build:frontend`), briefed with the findings' mechanisms and reproductions and pointed at `reference/executor-contract.md` and `reference/local-environment.md`. Never fix on the main thread. Then re-read the changed files, run tests, show `git --no-pager diff --stat` and a one-line revert pointer, and report: found, fixed by whom, verified, anything left. Non-blocking findings are reported as optional.

## Rules

- Exactly one reviewer per cycle. No fleets, no Claude skeptic subagents alongside, no second engine (the whole-build gate in `/build:build` is the one place a second reviewer runs, and the build invokes this skill twice for it).
- The reviewer reports; the judge verifies and scores; the executor fixes. Three actors, never merged, and the orchestrator is none of them.
- Quote check, then interrogation, then judge: one order, everywhere.
- Reproduce before you confirm; never fix a phantom.
- Depth over breadth. Never treat finding volume as review quality.
- Sweep nothing mid-build; the build owns `.build/`. Standalone, remove `.build/runs/<tag>.*` after reporting.
- No em dashes.
