# Roles: who does what, locked at invocation

A build has six roles. Each is one engine, one model, one effort, chosen when `/build:build` is invoked and never changed during the run.

| Role | What it does | Default |
|---|---|---|
| `executor` | Builds every backend, mixed-logic, and non-visual item; runs every fix round on those layers; runs the e2e work. | `agy` (top Gemini model, High) |
| `frontend` | Builds and fixes every visual surface, under the impeccable discipline. | `agy` (top Gemini model, High) |
| `reviewer` | Runs every review cycle: per item, and the whole-build gate. Reports only, never fixes. | `codex:gpt-6.1-sol:high` |
| `consult` | The redesign consult. Reads the ledger and the code, returns one of three verdicts. | `claude:fable:high` |
| `judge` | Verifies and scores every reviewer finding against the code and returns the findings table, so the orchestrator never opens code to check a finding (`judge-contract.md`). Also judges spec-certify cycles and doc rounds. | `claude:opus:medium` |
| `docs` | Writes and updates the code docs under `docs/code/` after the whole-build review (`/build:docs`). | `agy` (top Gemini model, High) |

The judge should come from a different model family than the reviewer, which the defaults give (codex reviews, Claude judges); pre-flight notes a same-family pair and never refuses it. A Claude judge can also run the failing test that confirms a finding, which a read-only codex sandbox cannot.

## Syntax

```
/build:build <spec-path> [<spec-path>...] [executor=<engine>] [frontend=<engine>] [reviewer=<engine>]
             [consult=<engine>] [judge=<engine>] [docs=<engine>] [docs=yes|full|no]
/build:build resume
```

An engine value is `agy`, `codex:<model>:<effort>`, or `claude:<model>[:<effort>]`. A role not given takes its default. A bare `codex` means `codex:gpt-6.1-sol:high`. `docs=yes` (the default) writes the docs once and runs the mechanical check; `docs=full` adds the verification rounds; `docs=no` skips docs. Several spec paths run in order, each with its own ledger. Examples:

```
/build:build specs/dm-inbox.md
/build:build specs/dm-inbox.md reviewer=claude:opus executor=codex:gpt-6-astra:high
/build:build specs/dm-inbox.md frontend=claude:fable consult=codex:gpt-6-astra:max
/build:build specs/a.md specs/b.md judge=codex:gpt-6-astra:high docs=full
```

**Roles come from the invocation only**: the `/build:build` line itself, or the same message when the user names engines in prose there. Never from an earlier message, an earlier build, or a spec.

## Resolution rules

- **agy** always resolves to the first row of `agy models` at invocation time, which is the newest Gemini at its top reasoning level (today `Gemini 3.8 Flash (High)`). Record the resolved name in the manifest and pass it explicitly on every call. Never pin a Gemini model by hand; the rule is "the top of the list at High", and it survives the next release without an edit. agy has no separate effort flag: the level is part of the model name, and passing `--effort` fails the run instantly.
- **codex** takes an explicit model slug and effort. Slugs come from `~/.codex/models_cache.json` (today `gpt-6.1-sol`, `gpt-6-astra`, `gpt-6-sol`, `gpt-6-luna`, `gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`; an older codex CLI may not list the newest slugs, so `codex update` first when one is missing). Efforts: `low`, `medium`, `high`, `xhigh`, `max`. Never `ultra` (it auto-delegates inside codex and is not a pinned role). Both flags are passed on every call so nothing inherits the global config, which pins its own default for interactive use.
- **claude** takes a model (`fable`, `opus`, `sonnet`, `haiku`; `fable`, `opus`, and `sonnet` are aliases that always mean the latest model of each line, so no version is ever pinned) and runs as a plugin subagent. The Agent tool accepts a per-call `model` override, so the model is set per run. Effort is fixed by the role's agent file under `agents/` (every agent file ships at `high` except `judge` and `walker`, which ship at `medium`) because the harness has no per-call effort override; a third part in a claude triple (`claude:fable:high`) is recorded in the ledger for the reader and must match the agent file. Changing a Claude role's effort is a draft edit to that agent file plus a version bump, never an edit to the installed cache.
- **The user's role choice is final, whatever it is.** Four roles on one family, the consult on the same model as the executor, any combination: pre-flight records it and proceeds. A different-family consult is a useful default (it gives an independent second opinion), which is why the defaults are shaped that way, but it is never a rule the orchestrator enforces against an explicit choice. Pre-flight fails only when an engine does not answer, never on a choice.

## Pre-flight (before item 1, every build)

Run `scripts/preflight.sh --dir <project>` with the six resolved triples (`--docs none` when `docs=no`). It verifies, in this order, and stops at the first failure with a report:

1. `agy models` answers and its first row is the resolved model (only if any role is agy).
2. A trivial codex call on each distinct codex model and effort returns (only if any role is codex). A quota or rate-limit answer is a failure that names the override flag.
3. A trivial `claude -p` call on each distinct Claude model returns (only if any role is claude), with the same quota rule.
4. It prints free memory, any other open build on this machine, and the outbound delivery variables a local dev server must redirect (`local-environment.md`), and writes everything to `.build/preflight.txt`, which `ledger.py init` records.
5. If the spec declares any frontend surface: the Playwright MCP tools are present in this session (the orchestrator checks its own tool list; the script cannot), and sign-in-protected routes have a way in: a saved Playwright login state or a local sign-in bypass the repo already has. With neither, the frontend gate for those routes will be `degraded`; log it.
6. If the spec names credentials, services, or databases it depends on: they are reachable from this machine.

Pre-flight failure is permitted stop 1 in `unattended-contract.md`. Nothing is built before it passes. The manifest records the pre-flight result and the six resolved triples verbatim.

## Locked means locked

During the run, a role's engine may fail. The retry ladder in `unattended-contract.md` applies, always on the same engine. If the ladder is exhausted, the run stops with a report (permitted stop 2). Under no circumstance does the orchestrator:

- route an executor task to the reviewer engine, or the reverse;
- spawn a Claude subagent because agy or codex is slow, rate-limited, or dead;
- do the work on the main thread;
- "just this once" downgrade or upgrade a model or effort.

Every one of those is a discipline violation named in the final report, in the same list as asking the user.

## How each engine is called

Every call is one background Bash invocation of a launch script under `$PLUGIN_ROOT/scripts/`, which carries the watchdog and wakes the orchestrator once, on exit. The scripts write everything under `<project>/.build/`. Every `--read` file is copied by the script into `<project>/.build/contracts/` and the engine is pointed at that local copy, so no engine ever reads outside its workspace and the exact contract text of each run is pinned. The one outside-workspace read that remains is the impeccable skill directory for a frontend item: pass `--add-dir "$HOME/.claude/skills/impeccable"` to `run-agy.sh` for those runs (codex reads it without a flag). The backstop alarm is oversized by design (3600s agy, 7200s codex); for a large item or an open-ended brief pass `--backstop` at four times the worst-case estimate (14400 is fine), never smaller.

- **agy, write mode** (executor, frontend): `run-agy.sh --tag <tag> --brief <abs path> --model "<resolved>"`.
- **agy, review mode**: add `--plan`. Plan mode is structurally read-only (agy will not modify a target file even when told to), and the reviewer contract says report-only as well; both are required.
- **codex, write mode**: `run-codex.sh --tag <tag> --brief <abs path> --model <slug> --effort <effort>`.
- **codex, review mode**: add `--readonly` (sandbox `read-only`).
- **claude**: the Agent tool with `subagent_type` set to the plugin agent for the role (`build:executor`, `build:frontend`, `build:reviewer`, `build:consult`, `build:judge`, `build:docs`) and `model` set to the role's model. The prompt is the same brief file path the other engines get, plus the reference file to read first. Claude subagents do not need the launch scripts; the harness notifies on completion.

Each launch script prints, at exit, the report text, the tool trail summary, the model that actually ran, and an exit code: `0` report present, `2` run finished with no report (the script already resumed once), `3` startup hang killed after one automatic relaunch, `4` frozen run killed after one automatic resume, `5` launch failed (including a refused second launch on a live engine), `6` the engine died on SIGKILL (usually memory), `7` quota or rate limit. Codes 2 to 5 are one failure each on the retry ladder; 6 and 7 follow their own rules in `unattended-contract.md`. `--attach <tag>` re-attaches to a detached engine whose launch script was killed.

## Where the plugin root is

The harness does not export the plugin root into Bash. Resolve it once per session, before any script call:

```bash
bash "$(ls -d ~/.claude/plugins/cache/claude-skills/build/*/ | sort -V | tail -1)scripts/root.sh" --dir <project>
```

It prints the pinned copy (`<project>/.build/plugin`) when an open build recorded one, otherwise the newest installed version. Write the printed absolute path literally into every later command, never through a shell variable: a variable in a command is what worktree isolation refuses. Every snippet in this plugin that says `$PLUGIN_ROOT` means that printed path. Agent files and hooks always come from the installed plugin.
