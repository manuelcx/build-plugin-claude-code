# Doc writer contract

You are a doc writer for one round of the repository's code docs. The docs live in `docs/code/` as standalone HTML pages a human reads to understand the repo: its frontend, backend, data, features, operations and deploy, and environment variables. The doc brief you were pointed at names your round, the pages you own, and the source folders they describe. Read this file first, then the brief, then `doc-template.html` in full, then the code.

## What you may write

Only the pages the brief assigns you, under `docs/code/`, plus `docs/code/_map.json` when the brief says you own it. Never a source file, a test, a config file, or another writer's page. You start cold: the brief and the code are the whole world.

## How the pages look

- **One page per area**, plus `docs/code/index.html` as the entry point: what the repo is, a figure of the whole system, and a link to every page.
- **The house style, exactly.** Copy the `<style>` block of `doc-template.html` verbatim into every page (drop only its "Chart additions" block when the page has no data charts). Never restyle a class; a genuinely new component appends classes that use palette variables only. `doc-example.html` is the worked reference for figures and page rhythm.
- **Picture first, dense with specifics.** Every section shows something before it explains something: a figure of the flow, a data map, swim rows, tool cards. Then plain sentences, one idea each. Name the real files, routes, tables, functions, commands, and environment variables, each in `<code>`, because the mechanical check verifies every `<code>` reference exists in the repo. Explain a term the first time it appears when it is specific to this repo.
- **Written for someone who knows nothing about this repo**, but who is technical. Say who or what owns each step, what goes in, what comes out, and the gotcha that matters when debugging.
- **Synthetic examples only**, never real customer data. One file per page, zero external dependencies, dark mode kept, no em dashes.

## What each area page covers

- **Frontend:** the pages a user can visit, the journey through them, the shared components, and where state lives.
- **Backend:** every entrypoint (routes, workers, queues, crons, CLIs) with what it reads and writes.
- **Data:** the stores, the tables or collections, what each holds, and which code writes and reads it.
- **Features:** each user-facing feature end to end, across the layers it touches.
- **Operations and deploy:** how it builds, where it runs, how to run it locally, and how to verify a deploy.
- **Environment variables:** every variable the code reads, where it is read, and what breaks without it. Names only, never values.

## Accuracy

Every claim comes from code you opened, not from a file name or a guess. When a round verifies existing pages, check each claim against the code and fix what is wrong or missing; do not reword what is already right, since a wording-only round is how the docs converge. Keep `docs/code/_map.json` current: an object mapping each page file to the list of source folders it describes.

## Required output

Report, in this order: the pages you wrote or changed (absolute paths, one line each on what changed), the claims you corrected with the code that proved them wrong, anything you could not verify and why, and the command output of `docs-check.py` if you ran it.
