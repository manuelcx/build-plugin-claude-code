# The ledger and the state file

Two files under `<project>/.build/` are the durable record of a build. Both are written by `scripts/ledger.py`, never by hand, so the format never drifts and a fresh session can resume from them.

- `ledger.md`: the human-readable record. Manifest, roles, one row per cycle or gate pass, residuals, backlog, final report.
- `state.json`: the machine-readable position. Which item is open, which phase it is in, which cycle, the snapshot tag, the brief in flight. `/build:build resume` reads it and continues.

## Commands

```
ledger.py init --name <build-name> --spec <abs spec path> --commit <hash> \
  --executor <triple> --frontend <triple> --reviewer <triple> --consult <triple>
ledger.py manifest --items <json file>          # the item list with verbatim spec units and absorbed units
ledger.py protected --file <abs path>            # the Must-not-regress list, verbatim, once
ledger.py item-open --item N --name "<name>" --surface backend|frontend|mixed --greenfield yes|no --brief <abs path>
ledger.py row --item N --kind cycle|gate|consult --trigger "<text>" --engine "<name>" \
  --raw N --verified N --blocking "<count> (<scores and classes>)" --tests green|red --action "<text>"
ledger.py residual --item N --text "<what, scores, what a real fix takes>"
ledger.py backlog --item N --text "<pre-existing defect, one line>"
ledger.py item-close --item N --cycles N --critique "<score/max or n/a>"
ledger.py subheading --item N --title "REDESIGN -- new build, cycle count restarts"   # a redesign: new table, cycle count restarts
ledger.py section --title "Backend gate" | "E2E gate" | "Whole-build review"          # a standalone section with its own table
ledger.py row --heading "## Whole-build review" --kind cycle ...                          # a row on a section (no --item); cycles count per section
ledger.py state --set phase=review cycle=2 brief=/abs/path gates.backend=clean   # current.* keys, or gates.<name> for a gate
ledger.py show                                                # prints state.json and the open item's rows
ledger.py violation --text "<what happened>"                  # a discipline violation, carried into the final report
ledger.py report                                              # renders the final report section and marks the build closed
ledger.py close --abandon                                     # marks an unfinished build closed so a new one can start
```

Every command appends or updates in place; nothing is ever rewritten by hand. If a row was wrong, add a corrected row with `--trigger "correction of row N"`.

**Lifecycle.** `init` refuses while a build is open (resume it, or `close --abandon` it, which records a violation). A closed build is archived to `.build-archive/<name>-<closed-at>/` when the next `init` runs. `report` is what closes a build. Always call `section` before the first row of a gate section or the whole-build review; rows on a section heading count cycles for that section.

## Row format

One line per cycle, gate pass, or consult, in a table under the item heading:

```
| # | Trigger | Engine | Raw | Verified | Blocking | Tests | Action |
```

- `#`: cycle number within this item (a redesign restarts at 1 under its own sub-heading).
- `Trigger`: `initial build`, `fix-N`, `confirming (after fix-N)`, `redesign build`, `scope-gate`, `structure-gate`, `frontend-gate`, `backend-gate`, `e2e-gate`, `consult`.
- `Engine`: the locked role triple that ran, or the gate name.
- `Raw`: findings the reviewer returned, after its own withdrawals.
- `Verified`: CONFIRMED plus UNVERIFIABLE after the orchestrator's check. Refuted and fabricated counts go in Action when non-zero.
- `Blocking`: the count of findings scoring 6 or more, then in parentheses each one's `impact x likelihood` and cause class, for example `2 (3x2 omission, 2x3 regression)`. The closing row reads `0`. Gate rows read `n/a`.
- `Tests`: `green` or `red`.
- `Action`: what happens next, in a few words: `fix-2 (3 findings)`, `CONSULT -> REDESIGN (keep schema, rebuild orchestration)`, `REVERT TO SPEC SCOPE (byte-identity verified)`, `EXIT (qualifying)`, `residual x2, backlog x1`. Name any downgrade, refutation, or fabrication here in one clause.

## Item heading

```
## Item 3 -- thread-fetch ingestion -- surface: backend -- greenfield: no -- brief: /abs/.build/briefs/item-3.md
```

The surface and greenfield declarations are written when the item opens, never retroactively. They are the forcing function for the frontend obligations: without them there is no artifact proving the frontend question was asked.

## Worked example

```
## Item 3 -- pricing engine -- surface: backend -- greenfield: no -- brief: /repo/.build/briefs/item-3.md

| # | Trigger | Engine | Raw | Verified | Blocking | Tests | Action |
|---|---|---|---|---|---|---|---|
| - | scope-gate | scope-gate | 2 surfaces | 1 accepted (test util), 1 stripped (retry sweep, byte-identity verified) | n/a | green | proceed |
| 1 | initial build | codex:gpt-6-astra:medium | 7 | 5 (1 refuted: spec accepts stale read, line 41) | 2 (3x2 omission, 2x3 conflation) | green | shared root cause: rounding helper; fix-1 |
| 2 | confirming (after fix-1) | codex:gpt-6-astra:medium | 3 | 3 | 1 (3x2 regression) | green | CONSULT -> NO REDESIGN (2 seams); fix-2 |
| 3 | confirming (after fix-2) | codex:gpt-6-astra:medium | 2 | 2 | 0 | green | EXIT (qualifying); residual x2 |
| - | structure-gate | structure-gate | 0 violations | n/a | n/a | green | clean |
```

Cycle 2's blocking finding sits inside fix-1's change, so its cause class is `regression` and the consult ran before fix-2, as the scoring rules require. The two verified findings in cycle 3 scored below 6 (both 1x3), so they closed as residuals with no further cycle.

## Sections the ledger always has

`## Roles` (the four triples verbatim plus the pre-flight result), `## Item manifest` (every spec unit verbatim with the item that absorbed it; the pre-build commit; the `Must not regress` list verbatim), one `## Item N` section per item, `## Whole-build review`, `## Accepted residuals`, `## Triage backlog`, `## Discipline violations`, `## Final report`.

## The state file

```json
{
  "build": "dm-inbox", "spec": "/repo/specs/dm-inbox.md", "started": "2026-09-06T14:02:11",
  "roles": {"executor": "agy:Gemini 3.8 Flash (High)", "frontend": "agy:Gemini 3.8 Flash (High)",
            "reviewer": "codex:gpt-6-astra:medium", "consult": "claude:fable:high"},
  "items": [{"n": 1, "name": "...", "status": "closed", "cycles": 2}, {"n": 2, "name": "...", "status": "open"}],
  "current": {"item": 2, "phase": "review", "cycle": 2, "snapshot": "item-2", "brief": "/repo/.build/briefs/item-2-fix-1.md", "run": "item-2-cycle-2"},
  "gates": {"backend": "pending", "e2e": "pending", "docker": "n/a", "whole_build": "pending"},
  "status": "open"
}
```

Gate values: `pending`, `clean`, `not runnable: <reason>`, `n/a`. `status` becomes `closed` when `report` runs.

Phases: `build`, `scope-gate`, `frontend-gate`, `review`, `fix`, `consult`, `structure-gate`, `closed`. `ledger.py state --set` is called at every phase change, before the launch that starts the phase, so a kill mid-phase leaves the position recorded.
