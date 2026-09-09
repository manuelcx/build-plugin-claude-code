# Gate frame: the shared shape of the frontend and backend loops

Both gates verify a change by exercising it for real, then loop fix and re-check until nothing blocking remains. The checklists differ; this frame is shared.

## Hard gate

Exercising means running the thing and driving it the way its real client would. Reading the code and assuming it works does not count. A passing test suite does not count on its own. If the gate genuinely cannot run (no browser tools in the session, a service that needs a credential only the user holds), it is recorded as `not runnable` with the reason in its ledger row. Inside `/build:build` that is a gate result, not a stop; pre-flight is where a missing browser stops a build, before any work.

## Scope

The surfaces the item touched: the pages and flows, or the entrypoints and the state they read and write. Not the whole app unless the whole app changed.

## The loop

1. Boot what is needed (dev server, service and its dependencies, migrations, seed data). Infer the commands from the package manifest, compose file, Dockerfile, README. Provision tooling yourself. Confirm health before touching anything.
2. Run the gate's checklist against the current state of the touched surface.
3. Score every issue with the same two numbers the review uses (`scoring.md`): impact 1 to 3, likelihood 1 to 3. A gate issue blocks at 6 or more.
4. Route blocking issues to the locked executor for the layer (the frontend executor for visual issues, the executor for logic) as a fix brief. The gate never edits code itself.
5. Re-run the checklist from step 2 against the touched surface.

Exit when both hold: every checklist item ran against the current state, and no blocking issue remains. Non-blocking issues are recorded, not fixed unless the fix is trivial and local.

## Stop policy

Inside `/build:build`: none of the gate's own conditions is a stop. The unattended contract applies: a fix that keeps failing goes to the consult, a missing command is inferred and logged, a missing credential makes the gate `not runnable`. Standalone (invoked by the user outside a build): the same rules, with one difference: a credential only the user holds is reported as the reason the gate could not run, and the gate ends there, since a user is present to supply it. Commands, tooling, and seed data are still inferred and provisioned, never asked for.

## Ledger row

One row per pass under the item (or under the gate's own heading when run after the full first pass): `Engine` = the gate name, `Raw` = issues found, `Verified` = issues confirmed by re-exercising, `Blocking` = `n/a`, `Action` = what was routed and to whom, or `clean`. A gate closes on a pass with zero blocking issues.
