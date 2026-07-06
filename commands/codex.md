---
name: codex
description: Delegate a coding task to codex (GPT-5) with proper context. Codex starts fresh with no memory of our conversation, so this command briefs it on the task, points it at relevant files, and demands a structured change report back.
args:
  - name: task
    description: The coding task to delegate to codex
    required: true
---

The user wants to delegate this task to codex: $ARGUMENTS

## Step 1 — Understand and scope the task

Read the request carefully. If anything material is ambiguous (which file? which approach? what should the output look like?), ask the user before invoking codex. Burning a codex call on a misunderstood task is worse than a 10-second clarifying question.

## Step 2 — Gather context for codex

Codex starts cold. It has no awareness of:
- Our conversation
- The user's global CLAUDE.md (`~/.claude/CLAUDE.md`)
- Project-specific CLAUDE.md files
- Decisions, constraints, or preferences from earlier in this session

Identify what codex needs to know:
- **Target files** — the files it will read/edit
- **Context files** — relevant nearby code, types, configs
- **Project guidance** — any CLAUDE.md in the project root or relevant subdirs
- **Conversation constraints** — anything we agreed on that codex must respect (e.g. "don't introduce new dependencies," "match the existing pattern in X")

Prefer pointing codex to file paths rather than inlining content. Codex can read files directly; inlined content bloats the prompt and goes stale.

## Step 2.5 — Pre-flight: auto-trust the working dir

An **untrusted** project directory makes `codex exec` hang at startup on a trust prompt (zero output, process alive). Trust is per **exact** directory path (it is NOT inherited from parent dirs), stored in `~/.codex/config.toml`, and your home directory (`$HOME`) itself is `untrusted`: so any project not explicitly listed there will hang.

Do not surface this and stop. **Auto-trust the directory** before invoking, every time. This is exactly what choosing "trust" in an interactive codex run does, it just persists the entry, and it matches the `approval_policy = "never"` already in the config. Run the helper below on the target dir: it's a no-op if already trusted, flips an existing `untrusted` entry to trusted, or appends a fresh trusted block. It never produces a duplicate table.

```bash
ensure_codex_trust() {
  local dir="${1:-$PWD}" cfg="$HOME/.codex/config.toml"
  local hdr="[projects.\"$dir\"]"
  [ -f "$cfg" ] || { printf '[projects."%s"]\ntrust_level = "trusted"\n' "$dir" > "$cfg"; echo "trusted (new config)"; return; }
  # Already trusted inside this dir's own block? -> no-op.
  if awk -v h="$hdr" '$0==h{b=1;next} b&&/^\[/{b=0} b&&/trust_level[[:space:]]*=[[:space:]]*"trusted"/{f=1;exit} END{exit !f}' "$cfg"; then
    echo "already trusted"; return
  fi
  if grep -qxF "$hdr" "$cfg"; then          # header exists but not trusted -> flip in place
    awk -v h="$hdr" '$0==h{b=1;print;next} b&&/^trust_level[[:space:]]*=/{print "trust_level = \"trusted\"";b=0;next} b&&/^\[/{b=0} {print}' "$cfg" > "$cfg.tmp" && mv "$cfg.tmp" "$cfg"
    echo "flipped to trusted"
  else                                       # no entry at all -> append one
    printf '\n[projects."%s"]\ntrust_level = "trusted"\n' "$dir" >> "$cfg"
    echo "appended trusted entry"
  fi
}
ensure_codex_trust "<trusted-project-dir>"
```

Trusting is silent and persistent, so it only ever runs once per directory. If for a one-off you'd rather not persist a global edit, the per-run equivalent is to add `-c 'projects."<dir>".trust_level="trusted"'` to the `codex exec` call in Step 3 (same effect, scoped to that single invocation).

## Step 3 — Invoke codex (hardened against hangs)

Codex hangs frequently under the naive `codex exec <<EOF` recipe for a few reasons: it has no hard request timeout (a stalled SSE stream waits forever), a model-spawned pager or credential prompt deadlocks on a missing TTY, and a silent reasoning turn flushes nothing so "working" looks identical to "wedged." The invocation below removes every one of those failure modes. Keep all the flags.

```bash
cd <trusted-project-dir> || exit 1

# Backstop alarm: macOS has no `timeout`; perl's alarm kills codex after N seconds even if its
#   stream stalls. 7200s (2h) is deliberately OVERSIZED. This is disaster insurance for the case
#   where nothing is watching (the session died), NOT the primary hang defense. Wedges are caught
#   in minutes by the watchdog in Step 3.5. Do not size this down to the task.
# --json  : streams one JSONL event per step → the log gets a heartbeat the watchdog reads.
# --color never : keep the log clean (no ANSI escapes).
# -s workspace-write : explicit sandbox, no surprises.
# -o <file> : writes codex's final message to a file for clean verbatim relay (Step 4).
perl -e 'alarm shift; exec @ARGV' 7200 \
  codex exec --json --color never -s workspace-write \
  -o .codex-last-message.md \
  > .codex-run.jsonl 2>&1 <<'EOF'
## Task
<clear, specific description of what to do>

## Context
- Read these files first: <paths>
- Project guidance: <path to CLAUDE.md if relevant>
- Constraints from the user: <anything from our conversation codex must respect>

## Operational constraints (keep these verbatim — they prevent deadlocks)
- Never invoke a pager. Use `git --no-pager <cmd>` and append `| cat` to anything that could page.
- No network or credential-prompting commands: no `git push`, no `git fetch`, no interactive auth, no installs that hit the network unless the task explicitly requires it.
- Stay inside the workspace directory. Do not touch paths outside it.
- Any script you write must terminate cleanly on its own. Close DB/connection pools (`pool.end()`, `await payload.db.destroy()`), clear timers/intervals, and call `process.exit(0)` at the end if the runtime would otherwise stay alive. A script that does its work but never exits looks identical to a hang and stalls the run.

## Required output
After completing the task, report back with:
1. **Files changed** — every file you modified, with a one-line summary of the change per file
2. **Files considered but NOT changed** — anything you looked at and decided to leave alone, with the reason
3. **Incomplete or needs review** — anything you couldn't finish, anything you're unsure about, anything a human should verify
EOF
```

Notes on the command:
- **Launch it with the Bash tool's `run_in_background: true`** so the harness deliberately tracks it and re-invokes you on completion. Do NOT run it foreground: the 2-min default Bash timeout would silently auto-background it into an unobservable state, which is exactly the confusing "is it alive?" condition to avoid.
- Add `--skip-git-repo-check` if working outside a git repo (codex refuses by default).
- Leave the `7200` oversized, and scale it UP for open-ended or multi-task "goal" briefs (14400 for a big build is fine). Rule of thumb: at least 4x your worst-case estimate. Never size it down "to fit the task": a hand-tuned 30-min ceiling once killed a nine-task run while it was writing its final report, with all work done and all verification passed. Oversizing is free; the alarm only matters if the watchdog AND the session both died, and then it just bounds how long an idle wedged process lingers.
- Codex defaults to `approval: never` — it edits without asking. The flags above make sandbox and output explicit on top of that.
- **Do not edit the same files yourself while codex runs.** Concurrent edits to the same paths corrupt the diff. Wait for the heartbeat to go quiet and the process to exit.

## Step 3.5: Arm the watchdog (primary hang defense)

Immediately after launching codex, start a **Monitor** watching the JSONL heartbeat. Monitor is a deferred tool in most sessions: load it FIRST with ToolSearch (`select:Monitor`). If the call fails with InputValidationError / "invalid tool parameters", the schema isn't loaded; load it and retry. That error never means "skip the watchdog." Set `persistent: true` (runs can exceed the default timeout). The script stays silent while codex works and only emits when something needs you:

```bash
LOG="<abs-path-to-project>/.codex-run.jsonl"
while pgrep -f "codex exec" >/dev/null; do
  now=$(date +%s); mt=$(stat -f %m "$LOG" 2>/dev/null || echo "$now")
  if [ $((now - mt)) -gt 180 ]; then
    echo "HEARTBEAT FROZEN $(( (now - mt) / 60 ))min. Last events:"; tail -n 3 "$LOG"
    sleep 180
  else
    sleep 30
  fi
done
echo "codex exec exited"
```

Reacting to events:
- **No events** → codex is working. Do nothing; the backgrounded Bash task re-invokes you when it exits.
- **HEARTBEAT FROZEN** → real deadlock (almost always a pager/credential subprocess; `--json` emits an event per step, so 3+ min of silence is never healthy). Read the emitted tail to see which command wedged, then kill it yourself: `pkill -f "codex exec"`. This is the informed kill. Never leave a confirmed wedge to the 2h backstop.
- **"codex exec exited"** → see exit states below. TaskStop the monitor if it's still armed.

The watchdog is NOT redundant with the background task's exit notification. The exit notification fires only when codex exits; a hung codex never exits, so without the watchdog a wedge silently waits out the full 2h backstop. Arm it every run. If Monitor genuinely cannot run, fall back to manual checks every few minutes: `ls -l .codex-run.jsonl` (mtime advancing in the last ~60s = alive and working), `tail -n 3 .codex-run.jsonl`, `pgrep -fl "codex exec"`. Byte-count of captured output is the wrong signal; the log's mtime is the heartbeat. Never run codex unwatched.

Exit states:
- **process gone + `.codex-last-message.md` exists** → finished cleanly. Go to Step 4.
- **process gone, no `.codex-last-message.md` (or log ends mid-stream)** → killed: either your watchdog `pkill`, or the 7200s backstop alarm (the alarm firing means the watchdog itself was dead; say so). Report it, show the last JSONL events and `git --no-pager diff --stat` so the user sees any partial edits.
- **Killed late, work looks complete, only the report is missing** → do not re-run codex just to regain prose. The JSONL log contains every event, including codex's own messages and command results: reconstruct the report from the tail of `.codex-run.jsonl`, label it as salvaged, and present it alongside the diff.

## Step 4 — Relay codex's report verbatim

Show the user the actual change report. Do not paraphrase it.
- Clean finish: relay the contents of `.codex-last-message.md` verbatim.
- Killed/hung: say so plainly, show the last few JSONL events and `git --no-pager diff --stat`, and ask whether to retry (e.g. with a higher ceiling or a tighter brief) or take it over.

Clean up the scratch files when done: `rm -f .codex-run.jsonl .codex-last-message.md`.

## Step 5 — Verify if asked

If the user wants to confirm, re-read the modified files and compare against codex's report. Codex's summary describes what it intended; the diff is the truth.
