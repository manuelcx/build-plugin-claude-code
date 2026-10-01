# The unattended contract

Every skill in this plugin runs under this contract. It is the single source for when a run may stop, what it may never do, and how it behaves when something it depends on fails. A skill body may add rules on top; it may never contradict this file.

## The run never asks

A build is one long agentic cycle. Nobody is watching. So:

- Never ask the user anything: no `AskUserQuestion`, no question in prose, no "want me to", no pause for approval. Not about scope, not about a model, not about non-convergence, not about a fix that feels risky, not about committing.
- Never announce a choice you are told to make silently (engine, model, effort, review tier). The ledger is the audit trail; prose is not.
- Never wait for a user turn between two steps. End a turn only right after a background launch (an engine, a subagent, a backoff wait), never after a sub-skill returns and never after writing a summary. Ending a turn with the next step undone is a stop, and an unexplained stop is a discipline violation named in the final report. The plugin's stop guard (`hooks/hooks.json`) blocks such a turn end and names the phase to continue from.
- No summary goes to the user before the final report. The one exception is the one-line status that answers a goal check-in (below).
- Decide under the rules you have, log the reason in the ledger, keep going.

Any instruction elsewhere that says "ask", "confirm", "stop and ask", or "state your pick" is subordinate to this file when the skill runs inside `/build:build`. The three permitted stops below are the complete list.

The machine the build runs on has its own rules (memory, processes, worktrees, outbound delivery): `local-environment.md`, which every role follows.

## The three permitted stops (reports, never questions)

Every permitted stop is recorded with `ledger.py stop --reason "<which stop and why>"` before the report, so the stop guard lets the turn end. After a recorded stop, any later prompt in that session gets one line pointing at the report; only `/build:build resume` continues, and it clears the record.

1. **Pre-flight failure**, before item 1. A chosen role does not answer, a model slug is invalid, a model is out of quota (the report names the override flag, for example `executor=codex:gpt-6-astra:medium`), a tool the spec needs is absent (a browser for a frontend spec), or a credential the spec depends on is missing. Nothing has been built, so stop with a report naming exactly what failed and what would fix it.
2. **A chosen engine is dead after the retry ladder.** Roles are locked at invocation (see `roles.md`). When a role's engine stops answering mid-run, retry that same engine per the ladder. If it is still dead, stop with a report: what died, what was tried, where the build stands in the ledger. Never substitute another engine, never do the work on the main thread, never spawn a different subagent "to keep going". Substitution is a discipline violation of the same class as asking. That includes substituting to satisfy a rule in this plugin: the user's explicit role choice outranks every rule here, and a rule that seems to conflict with it is recorded in the ledger and ignored, never "resolved" by changing a role.
3. **Low context.** When the harness is about to summarize and the state file cannot describe the position precisely enough to resume, write the state, then stop with a one-paragraph report pointing at the ledger. A fresh session resumes with `/build:build resume`.

The docs role is the one exception to stop 2: a docs engine still dead after the ladder records `docs: not produced` with the reason (`ledger.py state --set "gates.docs=not produced: <reason>"`), and the final report still prints.

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
| The build finishes | Report. Do not commit, do not push. Those are user actions after the report. Inside a build this rule wins over a repo's CLAUDE.md that says to commit. When the spec's deliverable is itself a git operation, the executor does it (never the orchestrator), never with `--no-verify`, and that item's brief lifts the executor contract's ban on `git push` when a push is part of the deliverable. |

## The retry ladder (same engine, then stop)

Applies to any external engine call (agy, codex, a Claude subagent) that fails to launch, is killed, hangs, or returns an error with no usable output.

1. The launch script's own recovery (an automatic relaunch on a startup hang, an automatic resume on a freeze or on an exit with no report). One attempt each, inside the script.
2. One orchestrator-level relaunch of the same call with the same brief.
3. One relaunch after a 5-minute wait (one background `sleep 300`, then end the turn), in case the failure was load or a transient outage.

Three failures in a row on one call is the dead-engine stop above. Log every attempt in the ledger row that was in flight.

Three cases are handled before the ladder counts anything:

- **A harness kill of the launch script** (the background job reports `killed` without the watchdog having acted). The engine runs detached and may still be alive: check `.build/runs/<tag>.pid`. Alive: re-attach with `--attach <tag>` in one background call; it is not a failure. Dead: it counts as one failure, and a cold relaunch restores the snapshot first (`local-environment.md`).
- **Exit 6, the engine died on SIGKILL** (usually macOS memory pressure). Free memory per `local-environment.md` and relaunch; the first one in a row on a run does not count, a second consecutive one counts as a normal failure.
- **Exit 7, quota or rate limit.** Back off 5, then 15, then 30 minutes, each one background `sleep` recorded with `ledger.py backoff --minutes N --reason "<engine> quota"`, relaunching after each. Only after the 30-minute wait does a further quota failure count on the ladder. Never swap engines to escape a quota.

## Never on the main thread

The orchestrator (main-thread Claude) never writes project code. It briefs, launches, reads results, decides from the judge's table, records, and routes. The only main-thread writes are: the ledger and state file, brief files, scratch under `.build/`, and mechanical byte-identical restores per the actor rule in the build skill. "It is faster to fix it myself" is the failure mode this line exists to prevent.

## Under a goal (`/goal`)

The user often starts a build as a goal. The goal's own hook evaluates whether the goal is met and sends check-ins while background work runs.

- **A goal check-in gets one line** from `ledger.py status`, and nothing else: no log reads, no `tail`, no progress narrative. Then end the turn if a launch is in flight.
- **An engine's age is read from its files** (`.build/runs/<tag>.pid` and the log's modification time), never from the check-in's wording. A check-in's "deferred for 67 minutes" counts all background work in the session, not the run that just launched.
- **A permitted stop stays a stop.** The goal hook may push to continue; the recorded stop and its report stand, and the report names the exact command that resumes.
- **Wording goals.** The plugin notes advise the user to phrase a build goal as "the final report for <spec> has printed", so the goal evaluator cannot mark it met after one item.

## Token discipline

- Never poll. Every external run is one background Bash call of a launch script that carries its own watchdog and wakes you exactly once, on exit. No `Monitor`, no `ScheduleWakeup`, no sleep loops, no `tail` on a log to see how it is going. The only waits are the ones named in this file (a backoff or the ladder's five minutes, each one background `sleep`) and `--attach` on a detached engine.
- Never inline fixed text. Executor and reviewer contracts live in `reference/`; a brief file carries only what is specific to the item or the cycle, and the engine is pointed at both.
- Never read a raw event log. The report scripts print the report text, the trail summary, and the exit state; that is what you read.
- Ledger rows are one line each, in the fixed format. Narrative goes in the final report.
- Start a build in a fresh session. A build inherits every token of the session it runs in, on every turn.
