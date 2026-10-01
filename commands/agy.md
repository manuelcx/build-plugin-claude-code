---
name: agy
description: Delegate a coding task to agy (Antigravity CLI, Gemini) through the plugin's launch script, which carries the brief-file pattern, the explicit model, the stream-json heartbeat, the watchdog with automatic relaunch and resume, and the backstop. agy starts cold, so this command briefs it by file, points it at absolute paths, and relays its structured change report verbatim.
args:
  - name: task
    description: The coding task to delegate to agy
    required: true
---

Delegate this task to agy: $ARGUMENTS

Resolve the plugin root once per session with the command in `reference/roles.md` ("Where the plugin root is"): it prints the open build's pinned copy when there is one, otherwise the installed plugin, and every `$PLUGIN_ROOT` below is that printed path written literally. Then read `$PLUGIN_ROOT/reference/unattended-contract.md` and `$PLUGIN_ROOT/reference/local-environment.md` once; they govern this command inside a build, and the no-questions rule holds standalone too: an ambiguous request is resolved by reading the code and the project docs, and the resolution is stated in the brief.

## 1. Brief, to a file

agy sees nothing from this conversation, and it hangs at startup on a large inline prompt, so the brief is always a file. Write `<project>/.build/briefs/<tag>.md` (create the folder if needed) with: the task, stated precisely; the target files as absolute paths with what to do in each (agy does not search for files; a relative or bare path may land in its own scratch area and the work is then invisible); context files and project guidance (`GEMINI.md`, `AGENTS.md`, `CLAUDE.md`) to read, not modify; constraints from the conversation; an **In scope / Out of scope** section; and the required output when it differs from the executor contract's. The standing rules (TDD, structure limits, operational constraints, the heredoc workaround for a rejected write, the report shape) come from `$PLUGIN_ROOT/reference/executor-contract.md`, which the launcher points agy at first; never paste them into the brief.

## 2. Model (silent, explicit)

Always the first row of `agy models` at its top reasoning level (today `Gemini 3.8 Flash (High)`), passed explicitly with `--model` so nothing inherits agy's configured default. Inside `/build:build` the resolved name is passed in; use it verbatim. Drop to `(Medium)` only for genuinely mechanical work, never for review, debugging, security, or an ambiguous refactor. agy has no separate effort flag: the level is in the model name, and `--effort` fails the run instantly. Never announce the pick.

## 3. Launch (one background Bash call, then wait)

```bash
"$PLUGIN_ROOT/scripts/run-agy.sh" --tag <tag> --dir <project> \
  --model "<resolved model>" \
  --read "$PLUGIN_ROOT/reference/executor-contract.md" \
  --read "$PLUGIN_ROOT/reference/local-environment.md" \
  --brief <project>/.build/briefs/<tag>.md
```

Add `--plan` for a read-only review (plan mode is structurally read-only; the brief must also say report-only), `--add-dir` when the task spans several roots, `--conversation <id>` to continue an earlier run. Run it with `run_in_background: true` and end the turn; the script carries the watchdog, relaunches once on a startup hang, resumes once on a mid-run freeze or on an exit with no report, and wakes you exactly once, on exit. The engine runs detached: if the background job is killed, check `.build/runs/<tag>.pid` and re-attach with `--attach <tag>` while it lives. Never run `agy` by hand, never poll the log, never arm a Monitor.

## 4. Read the exit

The script prints the model that ran, the tool trail, the outcome, and the report text, and exits `0` (report present), `2` (finished, no report), `3` (startup hang twice), `4` (frozen twice), `5` (launch failed, including a refused second launch on a live engine), `6` (engine killed by SIGKILL, usually memory), or `7` (quota or rate limit). A report-bearing run with `status: ERROR` is a good run: agy stamps the whole run ERROR when one tool call fails. Codes 2 to 5 are one failure each on the retry ladder in the unattended contract: relaunch the same call, then once more after a five-minute wait, then report the engine dead. Codes 6 and 7 follow the contract's memory and quota rules.

## 5. Verify, relay, sweep

The report describes intent; the diff is the truth. Check the changed files against the report; if an expected file is missing from the project, look in `~/.gemini/antigravity-cli/scratch/` before concluding the work was not done. Relay the report verbatim, then your verification in two or three sentences. Standalone, remove `.build/runs/<tag>.*` when done; inside a build, the build owns `.build/`.
