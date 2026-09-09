# The unattended contract

Every skill in this plugin runs under this contract. It is the single source for when a run may stop, what it may never do, and how it behaves when something it depends on fails. A skill body may add rules on top; it may never contradict this file.

## The run never asks

A build is one long agentic cycle. Nobody is watching. So:

- Never ask the user anything: no `AskUserQuestion`, no question in prose, no "want me to", no pause for approval. Not about scope, not about a model, not about non-convergence, not about a fix that feels risky, not about committing.
- Never announce a choice you are told to make silently (engine, model, effort, review tier). The ledger is the audit trail; prose is not.
- Never wait for a user turn between two steps. Ending a turn with the next step undone is a stop, and an unexplained stop is a discipline violation named in the final report.
- Decide under the rules you have, log the reason in the ledger, keep going.

Any instruction elsewhere that says "ask", "confirm", "stop and ask", or "state your pick" is subordinate to this file when the skill runs inside `/build:build`. The three permitted stops below are the complete list.

## The three permitted stops (reports, never questions)

1. **Pre-flight failure**, before item 1. A chosen role does not answer, a model slug is invalid, a tool the spec needs is absent (a browser for a frontend spec), or a credential the spec depends on is missing. Nothing has been built, so stop with a report naming exactly what failed and what would fix it.
2. **A chosen engine is dead after the retry ladder.** Roles are locked at invocation (see `roles.md`). When a role's engine stops answering mid-run, retry that same engine per the ladder. If it is still dead, stop with a report: what died, what was tried, where the build stands in the ledger. Never substitute another engine, never do the work on the main thread, never spawn a different subagent "to keep going". Substitution is a discipline violation of the same class as asking. That includes substituting to satisfy a rule in this plugin: the user's explicit role choice outranks every rule here, and a rule that seems to conflict with it is recorded in the ledger and ignored, never "resolved" by changing a role.
3. **Low context.** When the harness is about to summarize and the state file cannot describe the position precisely enough to resume, write the state, then stop with a one-paragraph report pointing at the ledger. A fresh session resumes with `/build:build resume`.

Everything else is a ledger row and a decision:

| Situation | What happens |
|---|---|
| The same finding survives several fix rounds | No cap. The consult fires per `scoring.md`; the loop continues. |
| A fix needs a product or architecture decision | The consult decides; the decision is logged as an accepted residual or a redesign. Never the user. |
| A dev server command cannot be inferred | Read the package manifest, the README, the compose file, the Dockerfile. Pick the most plausible and log it. |
| A test suite is slow, flaky, or missing | Run what exists; create what the spec requires; log the rest in the triage backlog. |
| An executor run returns nothing or the wrong thing | That is a failed round: re-brief and re-run on the same engine. |
| A reviewer finding cannot be reproduced for lack of a live service | UNVERIFIABLE, scored per `scoring.md`, never silently dropped and never a question. |
| Docker or e2e tooling is absent | Log the gate as not runnable with the reason; it is not a stop. |
| The spec is ambiguous | Choose the reading a careful engineer would, quote the spec line, log the choice. |
| The build finishes | Report. Do not commit, do not push. Those are user actions after the report. |

## The retry ladder (same engine, then stop)

Applies to any external engine call (agy, codex, a Claude subagent) that fails to launch, is killed, hangs, or returns an error with no usable output.

1. The launch script's own recovery (an automatic relaunch on a startup hang, an automatic resume on a mid-run kill). One attempt each, inside the script.
2. One orchestrator-level relaunch of the same call with the same brief.
3. One relaunch after a 5-minute wait, in case the failure was load or a transient outage.

Three failures in a row on one call is the dead-engine stop above. Log every attempt in the ledger row that was in flight.

A harness kill of a background job (the job reports `killed` without your watchdog having acted) counts as one failure on the ladder, not as a reason to change engines.

## Never on the main thread

The orchestrator (main-thread Claude) never writes project code. It briefs, launches, reads results, judges, records, and routes. The only main-thread writes are: the ledger and state file, brief files, scratch under `.build/`, and mechanical byte-identical restores per the actor rule in the build skill. "It is faster to fix it myself" is the failure mode this line exists to prevent.

## Token discipline

- Never poll. Every external run is one background Bash call of a launch script that carries its own watchdog and wakes you exactly once, on exit. No `Monitor`, no `ScheduleWakeup`, no sleep loops, no `tail` on a log to see how it is going.
- Never inline fixed text. Executor and reviewer contracts live in `reference/`; a brief file carries only what is specific to the item or the cycle, and the engine is pointed at both.
- Never read a raw event log. The report scripts print the report text, the trail summary, and the exit state; that is what you read.
- Ledger rows are one line each, in the fixed format. Narrative goes in the final report.
- Start a build in a fresh session. A build inherits every token of the session it runs in, on every turn.
