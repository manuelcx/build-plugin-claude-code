# build

A [Claude Code](https://docs.claude.com/en/docs/claude-code) plugin for unattended, end-to-end builds. You write a spec with `/build:spec`, harden it with `/build:spec-certify`, then hand it to `/build:build`, which cuts it into items and drives each one through the same loop: build, review, fix, gate. It never asks you a question mid-run.

The point of the plugin is that Claude does not write the project code. Four roles are locked at invocation, each one an engine plus a model plus an effort level, and Claude orchestrates between them. Nothing is silently substituted: if a locked engine dies, the run stops and reports instead of quietly falling back to something else.

Shared as-is from my personal setup; expect rough edges. Read the skills before you run them. **macOS as shipped.**

## Install

```
/plugin marketplace add manuelcx/build-plugin-claude-code
/plugin install build@build-plugin-claude-code
```

## The four roles

| Role | What it does | Default engine |
|---|---|---|
| `executor` | Builds every backend, mixed-logic and non-visual item, runs the fix rounds on those layers, and does the end-to-end work. | `agy` (top Gemini model, High) |
| `frontend` | Builds and fixes every visual surface, under the impeccable design discipline. | `agy` (top Gemini model, High) |
| `reviewer` | Runs every review cycle: per item, and the whole-build gate. Reports only, never fixes. | `codex:gpt-6-astra:medium` |
| `consult` | The redesign consult, called when fix rounds stop making progress. Reads the ledger and the code, returns one of three verdicts. | `claude:fable:high` |

An engine value is `agy`, `codex:<model>:<effort>`, or `claude:<model>[:<effort>]`. Any role you do not name takes its default.

```
/build:build specs/dm-inbox.md
/build:build specs/dm-inbox.md reviewer=claude:opus executor=codex:gpt-6-astra:high
/build:build resume
```

Full rules: [`reference/roles.md`](./reference/roles.md).

### Changing the models

The defaults in the table above are only defaults. Nothing in the plugin is hardwired to a particular vendor or model, and you can change what runs in two ways.

**Per run, on the invocation line.** Name any role and it uses your engine for that build instead of its default. Roles you leave out keep theirs. This is the normal way to work, and it is why the run is reproducible: the resolved model for every role is recorded in the ledger at the start.

```
/build:build specs/dm-inbox.md reviewer=codex:gpt-5.6-sol:high
/build:build specs/dm-inbox.md executor=claude:opus frontend=claude:opus
/build:build specs/dm-inbox.md executor=agy frontend=agy reviewer=agy consult=agy
```

**Permanently, by editing your copy.** The defaults live in one table at the top of [`reference/roles.md`](./reference/roles.md). Change that table and every future build picks up the new defaults.

What a valid engine value looks like:

- **`agy`** takes no model and no effort. It always resolves to whatever sits at the top of `agy models` when the build starts, which is the newest Gemini at its highest reasoning level. Passing it an effort flag fails the run.
- **`codex:<model>:<effort>`** needs both parts spelled out. Model slugs come from your own `~/.codex/models_cache.json`; efforts are `low`, `medium`, `high`, `xhigh` and `max`. Do not use `ultra`, which delegates internally and so is not a pinned role.
- **`claude:<model>[:<effort>]`** takes `fable`, `opus`, `sonnet` or `haiku`, where `fable` and `opus` mean the latest of each line. The model is set per run, but the effort is not: Claude roles run at whatever their agent file under [`agents/`](./agents) declares, all of them `high` as shipped, because the harness has no per-call effort override. A third part here is recorded in the ledger for the reader and has to match that file. Raising or lowering a Claude role's effort means editing its agent file.

Your choice is final, whatever it is. Putting all four roles on one model family, or the consult on the same model as the executor, is allowed; pre-flight records what you asked for and proceeds. The mixed defaults exist because a consult from a different model family gives a genuinely independent second opinion, but that is a recommendation, not a rule the orchestrator enforces. Pre-flight fails only when an engine does not answer, never because of how you combined them.

### The orchestrator, the fifth model

The four roles above are the models the plugin delegates to. There is a fifth model in every build that the invocation line cannot set: the Claude Code session you type `/build:build` into. That session is the orchestrator. It never writes project code, but it does everything around it: cutting the spec into items, writing each brief, holding the contracts, verifying every reported finding against the real code, deciding when an item is done, and keeping the ledger honest across a long unattended run.

**Run the orchestrator on an Opus model at medium reasoning effort.** Pick it with `/model` before you invoke the build.

Opus rather than a smaller model because the orchestrator is the only participant holding the whole run in its head, and every judgement call that is not delegated is made there. Medium rather than high because orchestration is mostly reading, routing and bookkeeping against contracts that are already written down, not open-ended reasoning: high effort spends tokens and time on a job that is largely mechanical, and a build is long enough that the difference compounds. The deep thinking is supposed to happen in the delegated roles, which carry their own effort settings.

**Skills**

| Skill | What it does |
|---|---|
| [`/build:spec`](./skills/spec/SKILL.md) | Writes the short, high-level spec that `/build:build` consumes, into `specs/<name>.md`. Defines what to build and the non-obvious constraints, verified against the real code, and leaves the how to the implementer. |
| [`/build:spec-certify`](./skills/spec-certify/SKILL.md) | Hardens an already-written spec before anyone builds from it. Loops adversarial review over the spec file, two external reviewers per cycle, until no verified Critical or High finding is left. Edits the spec only, never implementation code. |
| [`/build:build`](./skills/build/SKILL.md) | The orchestrator. Locks the four roles, cuts the spec into items, and runs each through the golden standard: a TDD-mandated build under a scope contract, a pre-review scope gate, review cycles scored on impact and likelihood, fix rounds, a redesign consult when fixing stops working, then the structure, frontend, backend, e2e, docker and whole-build gates. No cycle cap, no questions, one ledger. |
| [`/build:review`](./skills/review/SKILL.md) | The single adversarial review. One external reviewer reads the target under the shared reviewer contract, then Claude verifies every finding against the real code and scores it. Report-only inside a build; standalone it also routes the blocking fixes to the executor. |
| [`/build:frontend-review-loop`](./skills/frontend-review-loop/SKILL.md) | Verifies a frontend change by using it like a human in a real browser through Playwright, then loops fix and re-check until nothing blocking remains. |
| [`/build:backend-review-loop`](./skills/backend-review-loop/SKILL.md) | Boots the service, exercises the touched entrypoint like a real client, verifies the side effects in the database, queue, cache and logs, then loops fix and re-check. |
| [`/build:docker-test`](./skills/docker-test/SKILL.md) | Pre-deploy smoke test: exercises the real worker and queue path locally, then simulates the full Docker build and run topology to catch deploy-only failures. |

**Commands** (delegation to the external engines)

| Command | What it does |
|---|---|
| [`/build:codex`](./commands/codex.md) | Delegates one task to the OpenAI `codex` CLI through the launch script: trust pre-flight, explicit model and effort, JSONL heartbeat, watchdog, oversized backstop, verbatim change report. |
| [`/build:agy`](./commands/agy.md) | The same for `agy`, the Antigravity (Gemini) CLI: brief-by-file, explicit model, stream-json heartbeat, watchdog with automatic relaunch and resume. |

**Agents** — `agents/` holds the four Claude subagent definitions (`build:executor`, `build:frontend`, `build:reviewer`, `build:consult`), used when a role is set to a `claude:` engine.

**Contracts** — `reference/` is the rulebook every role reads before it acts: the unattended contract, roles, executor, frontend and reviewer contracts, the consult contract, the scoring model, the gate frame and the ledger format.

**Scripts** — `scripts/` holds the launch scripts with their watchdogs (`run-agy.sh`, `run-codex.sh`), the pre-flight check, the report parsers, the snapshot and structure gates, and the ledger tool.

## Requirements

- **Claude Code** on macOS.
- **[`codex`](https://github.com/openai/codex)** (OpenAI CLI), authenticated, for any role set to a codex engine, which includes the default reviewer.
- **`agy`** (Antigravity CLI, Gemini), authenticated, for any role set to `agy`, which includes both default executor roles.
- **Playwright MCP** in the session, for any spec that declares a frontend surface.
- The **impeccable** design skill at `~/.claude/skills/impeccable/`, for frontend items.
- **Docker** (colima by default) for `/build:docker-test`.

Every one of these is checked by pre-flight before item 1. A missing dependency stops the run with a report rather than a silent downgrade.

## License

MIT. See [LICENSE](./LICENSE).
