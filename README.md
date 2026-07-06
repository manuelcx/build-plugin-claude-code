# mc-ccXcodex-agentic-coding

An agentic-coding skills pack for [Claude Code](https://docs.claude.com/en/docs/claude-code), built around one end-to-end workflow: **`/build`**. It executes a plan, spec, or list of items (features or bug fixes) one at a time, using **codex (GPT-5)** as the executor and a fleet of adversarial reviewers as the quality gate. Claude orchestrates and reviews; codex writes the code.

Everything here exists to make `/build` run. Drop the folders into your Claude Code setup and invoke `/build` on a spec.

## What's inside

**The orchestrator**

| Skill | What it does |
|-------|--------------|
| [`build`](./build) | The end-to-end workflow. Works through items one at a time with a mandatory per-item loop (`/tdd` + `/co` to build, then `/loop /multi-review10x-lean` to review until a fleet pass logs **0 Critical / 0 High**), plus frontend, backend, e2e, and docker gates. Logs every review cycle to a live `.build-review-ledger.md`. |

**Executors** (how work gets written)

| Skill | What it does |
|-------|--------------|
| [`co`](./co) | Orchestrate a task by delegating execution to codex; Claude defines and reviews. Owns TDD enforcement in the brief. |
| [`codex`](./commands/codex.md) | The command `/co` delegates to. Hardened `codex exec` invocation: auto-trust, watchdog heartbeat, oversized backstop timeout, verbatim change report. **Installs as a command, not a skill** (see Install). |
| [`tdd`](./tdd) | Strict RED-GREEN-REFACTOR discipline. No production code before a failing test exists. |
| [`spec`](./spec) | Write a short, high-level build spec into `specs/<name>.md`. This is the input `/build` consumes. |

**Review gates** (nothing exits until these are clean)

| Skill | What it does |
|-------|--------------|
| [`multi-review10x-lean`](./multi-review10x-lean) | The per-item review engine. A fleet of 10+ external codex reviewers, each on a distinct dimension, then a second codex reproduction pass to keep only real flaws. Find, verify, fix. |
| [`frontend-review-loop`](./frontend-review-loop) | Verify a frontend change by actually using it in a real browser, then loop fix → re-review until no Critical/High remain. |
| [`backend-review-loop`](./backend-review-loop) | Boot the service, hit the touched entrypoint with real requests, verify real side effects (DB/queue/cache/logs), then loop fix → re-review. |
| [`docker-test`](./docker-test) | Pre-deploy smoke test: exercises the real worker/queue path and simulates the full Docker build/run topology to catch deploy-only failures. |
| [`dev-browser`](./dev-browser) | Drive your real Chrome session programmatically. Used by `frontend-review-loop` to exercise the UI. |

**Bonus** (standalone, not part of the `/build` flow)

| Skill | What it does |
|-------|--------------|
| [`fusion`](./fusion) | Run a diverse multi-model panel (Claude lenses + codex) in parallel, then a judge synthesizes consensus, contradictions, and blind spots. Useful for hard or ambiguous decisions. |

## How `/build` composes them

```
/build  (per item, one at a time)
  ├─ build  →  /tdd  +  /co  →  /codex        (write, test-first)
  │             └─ if frontend: /impeccable → /frontend-review-loop → /dev-browser
  ├─ review →  /loop /multi-review10x-lean  → /codex fleet   (until 0 Crit / 0 High)
  └─ after all items:
        /backend-review-loop      (backend gate)
        /co  e2e test             (e2e gate)
        /docker-test              (docker gate)
```

## Install

A skill is a folder containing a `SKILL.md`. A command is a single `.md` file. Claude Code auto-discovers both:

- Skills → `~/.claude/skills/` (user-level) or `<project>/.claude/skills/`
- Commands → `~/.claude/commands/`

```bash
git clone https://github.com/manuelcx/mc-ccXcodex-agentic-coding.git
cd mc-ccXcodex-agentic-coding

# Skills → ~/.claude/skills/
cp -R build tdd co spec multi-review10x-lean frontend-review-loop \
      backend-review-loop docker-test dev-browser fusion ~/.claude/skills/

# The codex command → ~/.claude/commands/
cp commands/codex.md ~/.claude/commands/
```

Then write a spec with `/spec` (or bring your own plan/list) and run `/build` on it.

## Dependencies

`/build` invokes other tools that are **not** bundled here. Install these separately or the workflow will stop partway.

**`impeccable`** (external — not mine to ship). Anthropic's frontend-design plugin. `/build` calls `/impeccable` before building any frontend item and `/loop /impeccable critique` to iterate on the design; `/co` references it to force a Claude subagent (never codex) as the frontend executor. Get it from the impeccable plugin. Without it, backend-only builds still work; frontend items will not.

**`/loop`** — built into Claude Code. `/build` wraps `/loop /multi-review10x-lean` and `/loop /impeccable critique`. Nothing to install; it ships with the CLI.

**codex CLI (GPT-5)** — required. The `codex` command shells out to `codex exec`. Install and authenticate the codex CLI, and note the directory-trust behavior documented inside `commands/codex.md` (an untrusted dir hangs the run).

**Playwright MCP** and/or the **`dev-browser` CLI** — required for frontend verification. `frontend-review-loop` and `dev-browser` drive a real browser to exercise the UI.

**Docker + a local runtime (colima)** — required for `docker-test`.

If you only build backends, you need: codex CLI + the skills above (skip impeccable, Playwright, dev-browser).

## Requirements

[Claude Code](https://docs.claude.com/en/docs/claude-code) installed, plus the codex CLI for any real build. Frontend and docker gates need the extra tooling listed under Dependencies.

## License

[The Unlicense](./LICENSE). Released into the public domain: use, adapt, sell, and share freely, no attribution required.
