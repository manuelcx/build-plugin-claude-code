# Scoring: what blocks, what ships, and why

A reviewer surfaces findings. The orchestrator verifies them, scores them, and decides. Severity labels are gone: a finding blocks or not based on two numbers and a short set of rules, all recorded in the ledger.

## Verification first

Nothing is scored until it is verified. The reviewer contract (`reviewer-contract.md`) makes the reviewer confirm each finding by reproduction: a concrete counterexample, a traced code path across real files, a failing input. The orchestrator then checks each confirmed finding against the code before scoring it. Verdicts:

- **CONFIRMED**: the mechanism the finding describes exists in the code and produces the claimed outcome.
- **REFUTED**: shown to be false (the code does not do what the finding says, or the outcome cannot occur). Recorded with the reason.
- **FABRICATED**: the finding describes code or behavior that is not there. Dropped and named in the row as a reliability signal about the reviewer.
- **UNVERIFIABLE**: could not be reproduced for lack of a live service, database, or timing control. Neither confirmed nor refuted. Scored on the reviewer's mechanism with likelihood capped at 2, and recorded with the missing capability.

"Could not reproduce in this environment" is a shortfall, never a refutation.

**How a blocking UNVERIFIABLE finding closes.** Its fix round must include a test that pins the mechanism (the executor contract requires one anyway). The confirming cycle then closes it on that test plus the reviewer's traced path; it does not need the missing live capability. If no test can express the mechanism, the finding is not fixable in this build: it becomes a residual with the missing capability named, and the ledger row says so.

## The two scores

Each CONFIRMED or UNVERIFIABLE finding gets an **impact** and a **likelihood**, each 1 to 3. The orchestrator assigns them from the verified mechanism, quoting the reviewer's numbers when it agrees and overriding with a reason when it does not.

**Impact: what breaks, for whom.**

| Score | Meaning |
|---|---|
| 3 | Money moved wrongly or twice, an irreversible external action done wrongly or twice (a message sent twice, an email to the wrong recipient), silent data loss, corruption of persisted state, an authentication or authorization bypass, or a break on a surface the spec's `Must not regress` list names. |
| 2 | Wrong behavior on a mainline path that a user would notice: a wrong result, a failed action, a request that errors, data shown wrong, a job that does not run. |
| 1 | Degraded but working: slower, noisier logs, a cosmetic defect, a missing nicety, an error message that could be clearer. |

**Likelihood: does it happen in production as the product is used.**

| Score | Meaning |
|---|---|
| 3 | Ordinary use reaches it: a normal request, ordinary data, normal traffic, the scheduled path on its normal run. Concurrency between two ordinary requests counts as ordinary use. Malformed-but-realistic external input (a partner webhook, a user-typed string) counts as ordinary use. |
| 2 | An unusual but real condition reaches it: a retry after a failure, a resume after a crash, a backfill, a large or empty dataset, a partner sending a rare-but-documented shape, a second run after a first run failed. |
| 1 | Only a contrived condition reaches it: corrupt or hand-crafted data, a multi-fault sequence, an abnormal condition such as a multi-minute process stall between two steps, an adversary with access the product does not grant. |

**A finding blocks when impact times likelihood is 6 or more.** That is exactly three combinations: 3 and 2, 2 and 3, 3 and 3. Everything else is non-blocking: logged, fixed when the fix is small and local, otherwise recorded as a residual.

## Rules on top of the numbers

These decide cases the numbers alone get wrong. Each exists because the ledgers showed the loop spending cycles there.

1. **Supporting artifacts do not block on their own.** A finding whose only home is a test, a docs sentence, a runbook, a comment, or a type annotation is scored by the production bug it hides. A test that passes for the wrong reason and hides a real defect scores as that defect. A test that is merely weak, a docs sentence that is merely imprecise: impact 1, non-blocking, fixed in the same round as a blocking fix if cheap, otherwise a residual.
2. **Outside the item's spec scope is not a finding.** A confirmed defect in code the item did not touch, or in behavior the spec did not ask this item for, goes to `## Triage backlog` with one line, never into a fix round. The one exception is a break on a `Must not regress` surface caused by this item: that is impact 3 and belongs to the item.
3. **Spec-accepted costs are refuted by spec.** When the spec explicitly accepts the cost the finding guards against, quote the spec line in the row and do not fix it.
4. **A fix that needs new machinery is not a fix.** If closing a finding requires a new background job, sweep, queue, flag, guard layer, registry, reconciliation path, or cache, the finding is not sent to a fix round. If it blocks, it goes to the consult as a shape question. If it does not block, it is a residual with one line on what a real fix would take. This is the anti-chase rule, and it is absolute: reviewer imagination never gets to add subsystems.
5. **A Must-not-regress surface is never likelihood 1.** The spec declared it live. A narrow trigger does not make breaking it acceptable.
6. **Impact 3 outcomes are never likelihood 1 by timing alone.** A torn write that only happens after a multi-minute stall is still corruption of persisted state: the abnormal timing lowers likelihood to 2 at most, never to 1. The carve-out excuses rare timing, never a bad outcome.
7. **Downgrades are recorded.** Any finding scored below what the reviewer proposed is named in the row with a one-line reason. Any refutation is named with its reason. These two doors are how findings leave the blocking set, so they are always visible.

## Cause classes (the adjudication vocabulary)

Alongside the scores, each CONFIRMED finding on item-authored code gets one cause class. It is about why the defect exists, never how rare the trigger is, and it drives the consult trigger below.

| Class | Meaning |
|---|---|
| `enumeration` | A check, map, or switch covering a proper subset of the states its input can occupy. |
| `conflation` | Two distinct states represented identically, or told apart only by a missing field. |
| `omission` | A path, case, or call site that should have been handled and simply was not. |
| `mainline` | Reachable on a realistic path with ordinary data; none of the above. |
| `regression` | The defect is inside the previous fix round's change. |
| `edge` | The trigger is likelihood 1 and the cause is none of the structural classes above. |

`edge` requires edge in cause AND in trigger. A narrow trigger with a structural cause is the structural class.

## What triggers the redesign consult

The consult runs BEFORE the next fix round, never after, and at most once per cycle, when any of these holds:

- Two or more blocking findings in one cycle whose causes are not clearly one shared root cause. If you can name the single root cause, fix it and name it in the row.
- Any blocking finding with cause `regression`: the previous fix broke something. Patching the patch is how ten-round items happen.
- A blocking finding that rule 4 above kept out of the fix round (it needs new machinery).
- The reviewer's scope lane flagged a whole subsystem the spec never asked for.

Verdicts, one of three, all real results: `REVERT TO SPEC SCOPE` (the item is sized wrong: strip to byte-identical, restore pre-existing bugs to the backlog, one confirming cycle), `REDESIGN` (the item is shaped wrong: state the rebuild scope and what is kept; a redesign is a new build with its own cycle count), `NO REDESIGN` (a seam analysis and the fix brief for one round). Never `NO REDESIGN` twice on the same surface.

## Confirming cycles

A confirming cycle is a full review cycle run after a fix, to check the fix itself. It runs only after a fix that closed a blocking finding. A non-blocking fix, a cleanup, a file split, a docs change, or a test-only change closes on green tests with no confirming cycle. A confirming cycle that finds nothing blocking is the qualifying cycle.

## The exit gate

An item closes on a **qualifying cycle**: a full review cycle by the locked reviewer, every finding verified, zero blocking findings, every `Must not regress` surface answered, tests green, the structure gate clean. No cycle cap. Nothing else closes an item: not green tests alone, not a spot-check, not a reviewer's opinion that the work looks converged, not a partial cycle.

## Residuals and backlog

Every non-blocking CONFIRMED finding left unfixed goes in `## Accepted residuals`, grouped by item: what it is, its scores, and what a real fix would take. Every confirmed pre-existing defect found and not fixed goes in `## Triage backlog`. Both are carried verbatim into the final report. A finding written down nowhere is a blocking finding that got laundered.
