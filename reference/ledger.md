# The ledger and the state file

Two files under `<project>/.build/` are the durable record of a build. Both are written by `scripts/ledger.py`, never by hand, so the format never drifts and a fresh session can resume from them.

- `ledger.md`: the human-readable record. Manifest, roles, one row per cycle, fix, gate pass, or consult, residuals, backlog, notes, final report.
- `state.json`: the machine-readable position. Which item is open, which phase it is in, the snapshot tag, the brief in flight, the pinned plugin copy, and every row, residual, and report entry the final report renders. `/build:build resume` reads it and continues.

## Commands

```
ledger.py init --name <build-name> --spec <abs spec path> --commit <hash> \
  --executor <triple> --frontend <triple> --reviewer <triple> --consult <triple> \
  [--judge <triple>] [--docs <triple>|none]      # reads .build/preflight.txt; pins scripts/ and reference/
ledger.py manifest --items <json file> [--whole-build-unit "<the spec's final verify-the-build unit, verbatim>"]
ledger.py item-add --item N --name "<name>" --unit "<spec unit verbatim>" --reason "<why it was added mid-build>"
ledger.py protected --file <abs path>            # the Must-not-regress list, verbatim, once
ledger.py item-open --item N --name "<name>" --surface backend|frontend|mixed --greenfield yes|no --brief <abs path>
ledger.py row [--item N | --heading "## <section>"] --kind cycle|fix|gate|consult|note --trigger "<text>" \
  --engine "<triple or gate name>" [--findings <abs path>] [--raw N --verified N --blocking "<...>" --tests green|red] --action "<text>"
ledger.py residual [--item N] --text "<what you would see, scores, what a real fix takes>"
ledger.py backlog [--item N] --text "<pre-existing defect, one line>"
ledger.py item-close --item N --cycles N --critique "<score/max or n/a>"
ledger.py subheading --item N --title "REDESIGN -- new build, cycle count restarts"
ledger.py section --title "Backend gate" | "E2E gate" | "Whole-build review" | "Docs"
ledger.py state --set phase=review brief=/abs/path gates.backend=clean      # current.* keys, or gates.<name>
ledger.py live --text "<a step the user must take to make it live, in plain words>"
ledger.py unbuilt --text "<a spec requirement that was not built, and why>"
ledger.py deviation --text "<a spec deviation that changes product behavior, and why>"
ledger.py note --text "<an observation or decision: never a violation>"
ledger.py violation --text "<what happened>"     # a discipline violation, carried into the final report
ledger.py backoff --minutes N --reason "<engine> quota"                    # a sanctioned wait, exempt from gap notes
ledger.py stop --reason "<which permitted stop and why>"                   # the stop guard lets the turn end
ledger.py queue --set <spec> [<spec>...] | --pop                            # remaining specs of a multi-spec invocation
ledger.py status                                # one line: items closed, current item and phase, fix rounds, elapsed
ledger.py show                                  # state plus the open item's rows
ledger.py report                                # renders the final report and closes the build
ledger.py close --abandon                       # marks an unfinished build closed so a new one can start
```

Every command appends or updates in place; nothing is ever rewritten by hand. If a row was wrong, add a corrected row with `--trigger "correction of row N"`.

**Cycle numbers come from the rows.** A cycle row's number is the count of cycle rows under the same heading plus one; a redesign subheading restarts it. `state --set cycle=` is ignored. A cycle row requires `--findings` pointing at an existing findings file, so no cycle is logged without a real review. `row` defaults to the current item, or to the current section after `section`.

**Lifecycle.** `init` refuses while a build is open (resume it, or `close --abandon` it, which records a violation). A closed build is archived to `.build-archive/<name>-<closed-at>/` when the next `init` runs; `init` then recreates `briefs/`, `runs/`, and `gates/`, carries the session's `owner-session` and `queue` across the archive, reads `preflight.txt` into the new state, and copies the installed `scripts/`, `reference/`, and `skills/` into `.build/plugin/`, recording that path as `plugin` so every later command runs the same version. `report` always renders and always closes the build, replacing any earlier final report; a failed discipline check marks its line failed and never refuses to close. Always call `section` before the first row of a gate section or the whole-build review.

## Row format

One line per cycle, fix, gate pass, consult, or note, in a table under the item heading:

```
| # | Trigger | Engine | Raw | Verified | Blocking | Tests | Action |
```

- `#`: cycle number within this item (a redesign restarts at 1 under its own sub-heading); `-` for every other kind.
- `Trigger`: `initial build`, `fix-N`, `confirming (after fix-N)`, `redesign build`, `scope-gate`, `structure-gate`, `frontend-gate`, `backend-gate`, `e2e-gate`, `consult`.
- `Engine`: the locked role triple that ran, or the gate name. The discipline check compares it with the locked roles, so write the triple, never a nickname.
- `Raw`: findings the reviewer returned, after its own withdrawals.
- `Verified`: CONFIRMED plus UNVERIFIABLE after the judge's check. Refuted and fabricated counts go in Action when non-zero.
- `Blocking`: the count of findings scoring 6 or more, then in parentheses each one's `impact x likelihood` and cause class, for example `2 (3x2 omission, 2x3 regression)`. The closing row reads `0`. Gate rows read `n/a`.
- `Tests`: `green` or `red`.
- `Action`: what happens next, in a few words: `fix-2 (3 findings)`, `CONSULT -> REDESIGN (keep schema, rebuild orchestration)`, `REVERT TO SPEC SCOPE (byte-identity verified)`, `EXIT (qualifying)`, `residual x2, backlog x1`. Name any downgrade, refutation, or fabrication here in one clause.

## Item heading

```
## Item 3 -- thread-fetch ingestion -- surface: backend -- greenfield: no -- brief: /abs/.build/briefs/item-3.md
```

The surface and greenfield declarations are written when the item opens, never retroactively. Greenfield is mechanical: `yes` when the item adds a page the user can visit or a new top-level screen, otherwise `no`.

## Worked example

```
## Item 3 -- pricing engine -- surface: backend -- greenfield: no -- brief: /repo/.build/briefs/item-3.md

| # | Trigger | Engine | Raw | Verified | Blocking | Tests | Action |
|---|---|---|---|---|---|---|---|
| - | scope-gate | scope-gate | 2 surfaces | 1 accepted (test util), 1 stripped (retry sweep, byte-identity verified) | n/a | green | proceed |
| 1 | initial build | codex:gpt-6.1-sol:high | 7 | 5 (1 refuted: spec accepts stale read, line 41) | 2 (3x2 omission, 2x3 conflation) | green | shared root cause: rounding helper; fix-1 |
| - | fix-1 | agy:Gemini 3.8 Flash (High) | n/a | n/a | n/a | green | 2 blocking + 1 ride-along closed |
| 2 | confirming (after fix-1) | codex:gpt-6.1-sol:high | 3 | 3 | 1 (3x2 regression) | green | CONSULT -> NO REDESIGN (2 seams); fix-2 |
| 3 | confirming (after fix-2) | codex:gpt-6.1-sol:high | 2 | 2 | 0 | green | EXIT (qualifying); residual x2 |
| - | structure-gate | structure-gate | 0 violations | n/a | n/a | green | clean |
```

Cycle 2's blocking finding sits inside fix-1's change, so its cause class is `regression` and the consult ran before fix-2, as the scoring rules require. The two verified findings in cycle 3 scored below 6 (both 1x3), so they closed as residuals with no further cycle.

## Sections the ledger always has

`## Roles` (the six triples verbatim plus the pre-flight result), `## Item manifest` (every spec unit verbatim with the item that absorbed it; the pre-build commit; the `Must not regress` list verbatim), one `## Item N` section per item, `## Whole-build review`, `## Accepted residuals`, `## Triage backlog`, `## Discipline violations`, `## Notes`, `## Final report`.

## The final report

`report` renders, in this order: a one-line verdict (with "NOT BROWSER-VERIFIED" when the frontend gate was degraded or not runnable); "What you must do to make it live" (from `live`); requirements not built (from `unbuilt`); spec deviations that change product behavior (from `deviation`); the items table and gates; the numbered residuals and backlog, in plain words; the commits main gained since the pre-build commit on files the build touched; the discipline check; the numbered notes, including any gap over 15 minutes between one run ending and the next starting (backoffs exempt). It deletes `.build/gates/`.

The discipline check is mechanical: every recorded violation, every item without a closing row, every gate left `pending` (docs excepted), and every row whose engine is not the role its kind belongs to (cycle rows: the reviewer, plus the consult and the judge on the whole-build review; consult rows: the consult; fix rows: the executor or the frontend executor). Engines match by family and model, so `agy` and `agy:Gemini 3.8 Flash (High)` agree.

## The state file

```json
{
  "build": "dm-inbox", "spec": "/repo/specs/dm-inbox.md", "started": "2026-09-06T14:02:11", "status": "open",
  "plugin": "/repo/.build/plugin",
  "roles": {"executor": "agy:Gemini 3.8 Flash (High)", "frontend": "agy:Gemini 3.8 Flash (High)",
            "reviewer": "codex:gpt-6.1-sol:high", "consult": "claude:fable:high",
            "judge": "claude:opus:medium", "docs": "agy:Gemini 3.8 Flash (High)"},
  "items": [{"n": 1, "name": "...", "status": "closed", "cycles": 2}, {"n": 2, "name": "...", "status": "open"}],
  "current": {"item": 2, "phase": "review", "cycle": 2, "snapshot": "item-2", "brief": "/repo/.build/briefs/item-2-fix-1.md", "run": "item-2-cycle-2"},
  "gates": {"frontend": "pending", "backend": "pending", "e2e": "pending", "docker": "n/a", "whole_build": "pending", "docs": "pending"}
}
```

Gate values: `pending`, `clean`, `degraded: <what was not exercised>`, `not runnable: <reason>`, `n/a`; the docs gate also takes `written`, `converged after N rounds`, or `not produced: <reason>`. `status` becomes `closed` when `report` runs.

Phases: `build`, `scope-gate`, `frontend-gate`, `review`, `fix`, `consult`, `structure-gate`, `docs`, `stopped`, `closed`. `ledger.py state --set` is called at every phase change, before the launch that starts the phase, so a kill mid-phase leaves the position recorded.
