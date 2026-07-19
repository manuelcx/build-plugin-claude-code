---
name: co
description: Orchestrate any task (code, strategy, text, docs, anything) by delegating execution to the /codex command and reviewing the result. Use when the user invokes /co or asks to orchestrate a task, delegate and review, or run something through codex with Claude as reviewer. Claude defines and reviews; codex executes.
---

# Claude Orchestrate

Claude is the orchestrator and reviewer. The orchestrator never executes the task itself, not even "just this small part." Execution goes to an executor: codex for non-visual work, and a Claude **subagent** for frontend/visual work (step 1.5). Main-thread Claude touches zero files either way.

## 1. Define the task

Identify what needs to be done. Any kind of task qualifies: code, strategy, copy, docs, plans. Pin down:

- The deliverable and where it lives (absolute file paths). If the deliverable is not naturally a file (an answer, a strategy, a recommendation), have codex write it to a markdown file and review that.
- Constraints from the conversation and project CLAUDE.md
- Explicit success criteria you will review against in step 3

## 1.5 Route frontend work (Claude subagent)

If the deliverable has a real user-facing visual surface (UI, UX, frontend), the executor is **a Claude subagent. Never codex.** This is a hard rule: do not ask which engine to use (no `AskUserQuestion`), and never route a visual surface to codex, even in an unattended run.

Once routed to a Claude subagent:
- **Predominantly UI** → the whole build goes to a Claude subagent (Agent tool).
- **Mixed (real logic too)** → split: `/codex` builds it working-but-plain end to end, then a Claude subagent does a visual pass over the UI files (restyle, layout, polish), never touching data logic.

**Mandatory for every frontend subagent** (both paths above, and every fix-round UI subagent in step 3): the brief MUST instruct the subagent that its FIRST action, before reading or writing any UI file, is to load the `impeccable` skill via the Skill tool (use its `craft` sub-command for building UI). Only after the skill is loaded does it read the project design system for tokens/components when present, then build. Spell this out as a hard requirement in the brief, not a suggestion. A subagent that touches frontend files without having loaded the skill is a failed run and gets re-briefed (counts as a fix round).

The subagent is the executor; main-thread Claude still edits nothing.

## 2. Execute via /codex (mandatory)

**When codex is the executor, you MUST invoke the `/codex` slash command via the Skill tool, passing the full brief (task, paths, constraints, success criteria) as the argument. This is not optional.**

`/codex` silently picks the codex model and reasoning effort from its own rubric; never pin one yourself unless the user explicitly named a model or effort (then pass that through in the brief). Help the rubric pick well: the brief must carry honest complexity signals (scope, stakes, what is genuinely hard about the task). On a fix round, first judge WHY the last round failed: if the brief was thin, ambiguous, or wrong, fix the brief and say so in the new one (no escalation trigger); only when the brief was sound do you flag "retry of a failed round" so `/codex`'s escalation rule applies. All of this stays silent; no model talk to the user.

Never run the underlying CLI (`codex exec ...`) directly: not in your own Bash call, not through a subagent, not with "improved" flags, no matter how confident you are in reproducing the anti-hang recipe. The `/codex` command is the only sanctioned path to codex, period. (The raw CLI deadlocks on trust prompts, pagers, and stalled streams; the command carries the only working recipe: trust pre-flight, perl wall-clock kill, JSONL heartbeat, backgrounded run.)

If `/codex` cannot run or dies (rate limits hit, untrusted dir, hang, wall-clock kill, command unavailable): **STOP.** Report exactly what failed and what the user can do about it (e.g. trust the dir in `~/.codex/config.toml`, wait out the rate limit), then ask the user how to proceed. Do not retry on your own, do not execute the task yourself, do not have a subagent execute it. Nothing executes without codex.

**Partial work after a kill or hang:** a killed run often leaves changed files behind. Those are part of the STOP report, not material to finish. Show `git --no-pager diff --stat` (or list the touched files outside a repo), leave them untouched, and let the user decide whether to revert, retry, or keep. Do not review-and-complete a dead run.

## 3. Review (Claude)

Codex's report describes what it intended; the files are the truth. Discover changes independently: `git status` / `git --no-pager diff` in a repo, otherwise check the expected deliverable paths from step 1. Never declare a run clean from codex's report alone; an empty or thin report with no verified files is a failed run, not a pass.

Check every changed file against the success criteria from step 1: correctness, completeness, constraint adherence. For code, run tests/build/lint if present. For a UI layer built by a subagent, review by screenshotting the rendered result and judging the pixels (hierarchy, spacing, polish, responsive), not by reading the diff. Rate each issue you find by severity: Critical / High / Med / Low.

- **Issues found:** send the confirmed issues back as a fix brief ("fix these, report what you changed"), then re-review. Fixes route to whoever built the layer: logic → a fresh `/codex` invocation (same rule as step 2); a subagent-built UI → a fresh Claude subagent. A run that returned but did the wrong thing, refused, or changed nothing counts as issues found. Loop fix → re-review until **no Critical or High issue remains** in the layer; there is no cap on the number of fix rounds. Remaining Med/Low issues don't force another round: fix them in-loop if cheap, otherwise report them to the user as optional. However many rounds it takes, execution always stays with the executor: never fix it on the main thread. The only thing that ends the loop early is the executor genuinely dying (rate limit, hang, wall-clock kill, command unavailable), which is the STOP in step 2, reported to the user.
- **Clean:** report what was delegated, what codex changed, what you verified, and the verdict.

## Rules

- codex ALWAYS runs through the `/codex` command, full stop. Never raw `codex exec`, never your own flags, never via a subagent, no exceptions for "simple" tasks.
- **Main-thread Claude** edits no project file as part of the task: not the deliverable, not a failing test, not a config "just so the build passes." Define, brief, review only. The only writers are the executors (codex, or a frontend subagent). "It's faster if I just fix it myself" is the failure mode this skill exists to prevent.
- Each fix round is a separate executor invocation (`/codex`, or a fresh Claude subagent for UI). Wait for each to return before reviewing.
- Sweep scratch files before the final report, however codex ended: `rm -f .codex-run.jsonl .codex-last-message.md`
- Be concise. No em dashes.
