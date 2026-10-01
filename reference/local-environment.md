# The local environment: the machine a build runs on

A build shares one Mac with the user, other sessions, other builds, dev servers, browsers, and container runtimes. Every rule here exists because a build broke something on that machine or was broken by it. The executor, reviewer, judge, and unattended contracts all point here.

## Memory

The main cause of dead engine runs in real builds was macOS killing processes under memory pressure, not the engines themselves failing.

- **Before every engine launch**, stop what the orchestrator itself started: its dev server and its browser. Kill them by the pid recorded in `.build/gates/devserver.pid` (whoever boots a dev server, including a browser-walk subagent, writes its pid there). Never leave a dev server running while an engine works.
- **Engines run detached.** The launch scripts start each engine in its own session, so a harness kill of the launch script (the background Bash job) leaves the engine running. After any harness kill, check the recorded pid in `.build/runs/<tag>.pid` first: if the engine is alive, re-attach with `run-agy.sh --attach <tag>` or `run-codex.sh --attach <tag>` in one background Bash call. Only a dead engine is relaunched. Stopping a launch script no longer stops its engine; the only way to stop an engine is a kill by its recorded pid.
- **A memory kill of the engine itself** shows as launcher exit code 6 (the engine died on SIGKILL, status 137). The first one in a row on a run does not count on the retry ladder; a second consecutive one on the same run counts as a normal failure, so exhausted memory still ends in permitted stop 2 instead of looping.
- **A cold relaunch restores the tree first**, to the snapshot taken right before the run that died: `item-N` for the build run, `item-N-fix-K` for a fix round. The tree is never restored when the launcher resumes the conversation itself, since the resumed engine continues its own work.
- **Pre-flight prints free memory and any other open build on this machine.** Another open build shares the memory and the engine quotas; log it and proceed.

## Processes

- **Kill by recorded pid only.** Never `pkill -f`, `killall`, or any process-name pattern: another session on the same machine runs processes with the same names (a dev server, a test runner, a browser), and a pattern kill stops them too.
- **Never remove a worktree** (`git worktree remove`), even one that looks abandoned: it may belong to a live session in another window.
- **Never touch `.claude/`** in the project: it holds other sessions' worktrees and settings.
- **No `git checkout`, `git reset`, or `git clean`** on files the run does not own. Restoring a file the run changed is done with `snapshot.sh restore`, which is byte-exact and scoped.

## Scripts a gate writes

- A script that writes or deletes data is written by the builder (one executor launch writes all of a gate pass's data-changing scripts), never by the orchestrator. It checks the database name before any destructive step and refuses when the name does not match the dev or test database the gate booted.
- A read-only probe (a curl, a select, a page fetch) is orchestrator scratch under `.build/gates/`.
- Every gate script runs under a hard timeout, `perl -e 'alarm shift; exec @ARGV' <seconds> <command>`, since macOS has no `timeout` command. A script with no timeout once hung unwatched for 1 hour 42 minutes.

## Outbound delivery never fires from a local server

Every dev server the plugin starts runs with the project's outbound delivery variables (webhooks, email and messaging providers, automation endpoints) pointed at an unreachable local sink, `http://127.0.0.1:9/`, never emptied, so apps that validate their settings at startup still boot. Pre-flight prints the list it found (`REDIRECT:`), from the project's `.env` files: URL-valued variables (a URL value, or a name ending in `URL`, `ENDPOINT`, `WEBHOOK`, or `HOOK`) whose names carry `WEBHOOK`, `N8N`, `BREVO`, `SMTP`, `MAILGUN`, `SENDGRID`, `RESEND`, `POSTMARK`, `TELEGRAM`, `SLACK`, or `TWILIO`, plus anything the project's own test config already neutralizes. Ports, tokens, and flags keep their values. Pass the listed variables as environment overrides on the dev server command. A gate step that cannot run because a variable was redirected is `not runnable` for that step, never a blocking finding. Real builds once forwarded every test submission to a live n8n workflow as a real lead.
