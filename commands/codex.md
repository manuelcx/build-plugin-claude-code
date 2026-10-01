---
name: codex
description: Delegate a coding task to codex (OpenAI CLI) through the plugin's launch script, which carries the trust pre-flight, the explicit model and effort, the JSONL heartbeat, the watchdog, and the backstop. Codex starts cold, so this command briefs it by file, points it at absolute paths, and relays its structured change report verbatim.
args:
  - name: task
    description: The coding task to delegate to codex
    required: true
---

Delegate this task to codex: $ARGUMENTS

Resolve the plugin root once per session with the command in `reference/roles.md` ("Where the plugin root is"): it prints the open build's pinned copy when there is one, otherwise the installed plugin, and every `$PLUGIN_ROOT` below is that printed path written literally. Then read `$PLUGIN_ROOT/reference/unattended-contract.md` and `$PLUGIN_ROOT/reference/local-environment.md` once; they govern this command inside a build, and the no-questions rule holds standalone too: an ambiguous request is resolved by reading the code and the project docs, and the resolution is stated in the brief.

## 1. Brief, to a file

Codex sees nothing from this conversation. Write `<project>/.build/briefs/<tag>.md` (create the folder if needed) with: the task, stated precisely; the target files as absolute paths with what to do in each; context files and project guidance files (`CLAUDE.md`, `AGENTS.md`) to read, not modify; constraints from the conversation; an **In scope / Out of scope** section; and the required output when it differs from the executor contract's. The standing rules (TDD, structure limits, operational constraints, report shape) come from `$PLUGIN_ROOT/reference/executor-contract.md`, which the launcher points codex at first; never paste them into the brief.

## 2. Model and effort (silent, explicit)

Inside `/build:build`, the locked executor triple is passed in; use it verbatim. Standalone, pick silently and never announce:

| Task shape | Pick |
|---|---|
| Mechanical: renames, config tweaks, boilerplate, doc edits, single-file fix with an exact spec | `gpt-5.6-luna` medium |
| Everyday: standard feature, straightforward bug fix, tests, routine refactor | `gpt-6-astra` low |
| Harder everyday: multi-file feature, unfamiliar area, non-obvious bug | `gpt-6-astra` medium |
| Complex: architecture, cross-cutting change, gnarly debugging, security or data integrity | `gpt-6-astra` high |
| Frontier-hard: a lower tier already failed on it | `gpt-6-astra` xhigh (max only in extremis) |

Never `ultra` (it auto-delegates inside codex). Slugs live in `~/.codex/models_cache.json`; if a slug errors, re-check that file. A retry of a failed round whose brief was sound escalates one step; a thin brief is fixed, not escalated.

## 3. Launch (one background Bash call, then wait)

```bash
"$PLUGIN_ROOT/scripts/run-codex.sh" --tag <tag> --dir <project> \
  --model <slug> --effort <effort> \
  --read "$PLUGIN_ROOT/reference/executor-contract.md" \
  --read "$PLUGIN_ROOT/reference/local-environment.md" \
  --brief <project>/.build/briefs/<tag>.md
```

Add `--readonly` for a review or answer-only task. Run it with `run_in_background: true` and end the turn; the script carries the watchdog and wakes you exactly once, on exit. The engine runs detached: if the background job is killed, check `.build/runs/<tag>.pid` and re-attach with `--attach <tag>` while it lives. Never run `codex exec` by hand, never poll the log, never arm a Monitor. Never start a second codex run in the same directory while one is live.

## 4. Read the exit

The script prints the final message verbatim (or a salvage from the event log, labelled as such) and exits `0` (message present), `2` (finished, no message), `4` (frozen and killed), `5` (launch failed, including a refused second launch on a live engine), `6` (engine killed by SIGKILL, usually memory), or `7` (quota or rate limit). Codes 2, 4, and 5 are one failure each on the retry ladder in the unattended contract: relaunch the same call, then once more after a five-minute wait, then report the engine dead. Codes 6 and 7 follow the contract's memory and quota rules.

## 5. Verify, relay, sweep

The report describes intent; the diff is the truth. Check the changed files against the report (`git --no-pager diff --stat`, read the files). Relay the report verbatim, then your verification in two or three sentences. Standalone, remove `.build/runs/<tag>.*` when done; inside a build, the build owns `.build/`.
