---
name: docs
description: Write and keep up to date the repository's code docs as standalone HTML pages under docs/code/ (frontend, backend, data, features, operations and deploy, environment variables), in the house picture-first style, then verify every file, route, symbol, and environment variable they name exists in the repo. Called by /build:build after the whole-build review (docs=yes by default, docs=full adds verification rounds, docs=no skips); also runs standalone to document an existing repo. Use on /build:docs, or when asked to write, refresh, or verify the code docs of a repo.
argument-hint: "[mode=yes|full] [docs=<engine>] [changed paths]"
---

# Docs

Keep `docs/code/` true to the code, so a human who knows nothing about the repo can understand it from the pages. The writing rules are in `reference/doc-writer-contract.md`; the look is `reference/doc-template.html`, with `reference/doc-example.html` as the worked reference. Resolve the plugin root once with the command in `reference/roles.md`; every `$PLUGIN_ROOT` below is that printed path, written literally. The unattended contract applies: never ask anything, never poll, end a turn only right after a background launch.

Inside `/build:build`, the docs engine is the locked `docs` role and the mode comes from the invocation. Standalone, the engine defaults to agy and the mode to `yes`.

## 1. Plan the pages

Read `docs/code/_map.json` when it exists: it maps each page to the source folders it describes. The pages to write are:

- **First run (no `docs/code/`):** every page: `index.html`, plus one page per area that exists in the repo (frontend, backend, data, features, operations and deploy, environment variables). Skip an area the repo does not have.
- **Later runs:** only pages whose mapped folders contain a changed path (from the build's `snapshot.sh changed pre-build`, or the paths the caller gave), plus a new page for an area the build created, plus `index.html` when a page was added.

Write `.build/briefs/docs-r1.md`: the round, the pages to write with the folders each describes, the project guidance files, and the changed paths. Log with `ledger.py section --title "Docs"` inside a build.

## 2. Round 1 (always)

One doc writer writes or updates every planned page and `_map.json`. Stop your own dev server first (`local-environment.md`), then launch per `roles.md` with the run tag `docs-r1` and `--read $PLUGIN_ROOT/reference/doc-writer-contract.md --read $PLUGIN_ROOT/reference/doc-template.html --read $PLUGIN_ROOT/reference/doc-example.html --read $PLUGIN_ROOT/reference/local-environment.md` before the brief (for a Claude writer, the Agent tool with `subagent_type: build:docs`). The first full run on a large repo may need `--backstop 14400`.

## 3. The mechanical check (always)

`docs-check.py docs/code <project>`. Every `MISSING` reference goes back to the same writer once, as a fix brief listing the missing references and their pages. A reference still missing after that is logged as a note; it never blocks.

## 4. Verification rounds (`mode=full` only)

Each round, split the pages into up to three disjoint groups, reshuffled every round so each page meets a fresh writer, and launch one fresh doc writer per group (tags `docs-rN-gK`), each verifying its pages against the code and fixing what is wrong or missing. The groups run one at a time, never in parallel: parallel engines are what exhausts the machine's memory. Take `snapshot.sh save docs-rN` before each round. After the round, `docs-check.py` again, then the judge classifies the round's diff (`snapshot.sh diff docs-rN`, which also covers new untracked pages) as fact changes or wording changes, per `judge-contract.md`, launched exactly as in `/build:review` step 4c with a doc-round brief naming the diff. The docs converge on a round with no fact changes. The safety stop is five rounds, logged with the reason.

## 5. Record and return

Inside a build: one ledger row per round (`--kind gate --engine docs --heading "## Docs"`), then `ledger.py state --set "gates.docs=<written | converged after N rounds | not produced: <reason>>"`. A docs engine still dead after the retry ladder records `not produced` and returns; it is never a stop, and the build's report still prints. Standalone: report the pages written, the check result, and the rounds, with absolute paths.

Docs never block a build, and this skill never edits anything outside `docs/code/`.
