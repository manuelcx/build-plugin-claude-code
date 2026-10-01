#!/bin/bash
# run-codex.sh: launch one codex run with the trust pre-flight and watchdog built in; exit once.
#
# Usage:
#   run-codex.sh --tag <tag> --brief </abs/brief.md> --model <slug> --effort <effort> [--readonly]
#                [--read </abs/file>]... [--prompt "<text>"] [--dir </abs/project>]
#                [--backstop 7200] [--freeze-limit 1200]
#   run-codex.sh --attach <tag> [--dir </abs/project>]     # watch a run whose launcher was killed
#
# Writes <dir>/.build/runs/<tag>.jsonl (event log), <tag>.last.md (final message), <tag>.pid, and
# <tag>.exit (the engine's wait status when this script saw it exit).
# Exit codes: 0 final message present, 2 finished with no final message (salvage printed),
# 4 frozen and killed (salvage printed), 5 launch failed, 6 engine killed by SIGKILL (usually
# macOS memory pressure), 7 quota or rate limit.
#
# Recipe notes, all load-bearing:
# - An untrusted project dir makes codex hang silently on a trust prompt; trust is per exact
#   path and not inherited, so ensure_codex_trust runs every time (no-op when already trusted).
# - -m and model_reasoning_effort are always explicit; otherwise codex inherits the global
#   config default, which is pinned for interactive use.
# - --json streams one event per step: the heartbeat the watchdog reads and a salvage trail.
# - -o writes the final message to a file for verbatim relay.
# - The engine runs in its own session (perl POSIX setsid), so a harness kill of this script
#   leaves it running; `--attach <tag>` picks it up again.
# - The perl alarm is the oversized backstop for when this script itself dies. Never size it down.
# - Liveness and kills go by the captured PID, never by a process-table pattern.

set -u
TAG=""; BRIEF=""; MODEL=""; EFFORT=""; RO=0; PROMPT=""; DIR="$PWD"; BACKSTOP=7200; FREEZE_LIMIT=1200; ATTACH=""
READS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG="$2"; shift 2;;
    --brief) BRIEF="$2"; shift 2;;
    --model) MODEL="$2"; shift 2;;
    --effort) EFFORT="$2"; shift 2;;
    --readonly) RO=1; shift;;
    --read) READS+=("$2"); shift 2;;
    --prompt) PROMPT="$2"; shift 2;;
    --dir) DIR="$2"; shift 2;;
    --backstop) BACKSTOP="$2"; shift 2;;
    --freeze-limit) FREEZE_LIMIT="$2"; shift 2;;
    --attach) ATTACH="$2"; TAG="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 5;;
  esac
done
cd "$DIR" || { echo "cannot cd to $DIR" >&2; exit 5; }
mkdir -p .build/runs
HERE="$(cd "$(dirname "$0")" && pwd)"
LOG=".build/runs/$TAG.jsonl"; PIDF=".build/runs/$TAG.pid"; LAST=".build/runs/$TAG.last.md"; EXITF=".build/runs/$TAG.exit"
alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null; }
rm -f .build/stop-guard.count
CODEX_PID=""; CHILD=0

finish() {  # print the final message or the salvage, and exit with the code the ladder reads
  python3 "$HERE/codex-report.py" "$LOG" "$LAST"
  [ -s "$LAST" ] && exit 0
  if [ "$(cat "$EXITF" 2>/dev/null)" = "137" ]; then echo "ENGINE KILLED (SIGKILL, status 137): usually macOS memory pressure"; exit 6; fi
  if python3 "$HERE/codex-report.py" --quota "$LOG" >/dev/null 2>&1; then echo "QUOTA OR RATE LIMIT: back off per the unattended contract"; exit 7; fi
  exit "${1:-2}"
}
# On any exit, remove the pid file only when the engine is gone. A kill of this script leaves a
# live engine and its pid file in place, so `--attach` can pick it up.
cleanup() { alive "$CODEX_PID" || rm -f "$PIDF"; }
trap cleanup EXIT
trap 'exit 130' INT TERM

if [ -n "$ATTACH" ]; then
  [ -f "$PIDF" ] || { echo "no pid file for $TAG"; [ -f "$LOG" ] && finish; exit 5; }
  CODEX_PID="$(cat "$PIDF")"
  alive "$CODEX_PID" || { echo "engine for $TAG already exited"; CODEX_PID=""; finish; }
  echo "attached to codex pid=$CODEX_PID log=$LOG"
else
  [ -n "$TAG" ] && [ -n "$BRIEF" ] && [ -n "$MODEL" ] && [ -n "$EFFORT" ] || { echo "need --tag, --brief, --model, --effort" >&2; exit 5; }
  [ -f "$BRIEF" ] || { echo "brief not found: $BRIEF" >&2; exit 5; }
  if [ -f "$PIDF" ] && alive "$(cat "$PIDF")"; then
    echo "engine for $TAG is still alive (pid $(cat "$PIDF")); use --attach $TAG, never a second launch" >&2; exit 5
  fi
  rm -f "$LAST" "$EXITF"

  ensure_codex_trust() {
    local dir="$1" cfg="$HOME/.codex/config.toml"
    local hdr="[projects.\"$dir\"]"
    [ -f "$cfg" ] || { printf '[projects."%s"]\ntrust_level = "trusted"\n' "$dir" > "$cfg"; echo "trust: new config"; return; }
    if awk -v h="$hdr" '$0==h{b=1;next} b&&/^\[/{b=0} b&&/trust_level[[:space:]]*=[[:space:]]*"trusted"/{f=1;exit} END{exit !f}' "$cfg"; then
      echo "trust: already trusted"; return
    fi
    if grep -qxF "$hdr" "$cfg"; then
      awk -v h="$hdr" '$0==h{b=1;print;next} b&&/^trust_level[[:space:]]*=/{print "trust_level = \"trusted\"";b=0;next} b&&/^\[/{b=0} {print}' "$cfg" > "$cfg.tmp" && mv "$cfg.tmp" "$cfg"
      echo "trust: flipped to trusted"
    else
      printf '\n[projects."%s"]\ntrust_level = "trusted"\n' "$dir" >> "$cfg"
      echo "trust: appended"
    fi
  }
  ensure_codex_trust "$(pwd -P)"

  # Every --read file (a contract from the plugin) is copied INTO the project so the engine never
  # reads outside its workspace, and the copy pins the exact contract text this run used.
  mkdir -p .build/contracts
  LOCAL_READS=()
  for r in ${READS[@]+"${READS[@]}"}; do
    [ -f "$r" ] || { echo "read file not found: $r" >&2; exit 5; }
    cp "$r" ".build/contracts/$(basename "$r")"
    LOCAL_READS+=("$(pwd -P)/.build/contracts/$(basename "$r")")
  done
  if [ -z "$PROMPT" ]; then
    PROMPT="Read, in this order:"
    for r in ${LOCAL_READS[@]+"${LOCAL_READS[@]}"}; do PROMPT="$PROMPT $r, then"; done
    PROMPT="$PROMPT $BRIEF. Then carry out the task the brief describes and produce the report it asks for."
  fi
  SANDBOX="workspace-write"; [ "$RO" -eq 1 ] && SANDBOX="read-only"
  GITCHK=(); git rev-parse --is-inside-work-tree >/dev/null 2>&1 || GITCHK=(--skip-git-repo-check)

  : > "$LOG"
  printf '%s\n' "$PROMPT" > ".build/runs/$TAG.prompt"
  perl -e 'use POSIX qw(setsid); setsid(); alarm shift; exec @ARGV' "$BACKSTOP" \
    codex exec --json --color never -s "$SANDBOX" ${GITCHK[@]+"${GITCHK[@]}"} \
    -m "$MODEL" -c model_reasoning_effort="$EFFORT" -o "$LAST" - < ".build/runs/$TAG.prompt" > "$LOG" 2>&1 &
  CODEX_PID=$!; CHILD=1
  echo "$CODEX_PID" > "$PIDF"
  echo "launched codex pid=$CODEX_PID log=$LOG model=$MODEL effort=$EFFORT sandbox=$SANDBOX"
fi

started=$(date +%s); sleep 10 & wait $!; frozen=0
while alive "$CODEX_PID"; do
  now=$(date +%s)
  mt=$(stat -f %m "$LOG" 2>/dev/null || echo "$now")
  [ -s "$LOG" ] || mt=$started
  # all live children (codex keeps MCP servers alive too, so never judge by the first child only)
  childcmd=""
  for c in $(pgrep -P "$CODEX_PID" 2>/dev/null); do childcmd="$childcmd"$'\n'"$(ps -o command= -p "$c" 2>/dev/null)"; done
  # a pager or credential prompt child is the classic wedge: kill now, never wait the window.
  # (git itself is NOT in this list: a healthy review runs git diff and git log constantly.)
  if echo "$childcmd" | grep -qE '(^|/| )(less|more|ssh|security)( |$)|gh auth'; then
    echo "WEDGE: pager or credential child ($childcmd); killing"
    kill "$CODEX_PID" 2>/dev/null; sleep 3; CODEX_PID=""
    finish 4
  fi
  if [ $((now - mt)) -gt "$FREEZE_LIMIT" ]; then
    # a long test or build inside one tool call is silent; give a live test/build child more time once
    if [ "$frozen" -eq 0 ] && echo "$childcmd" | grep -qE 'vitest|jest|npm|pnpm|bun|tsc|next|python|pytest|cargo|go '; then
      frozen=1; echo "quiet ${FREEZE_LIMIT}s but a build/test child is live; allowing one more window"; sleep "$FREEZE_LIMIT"; continue
    fi
    echo "FROZEN: no events for ${FREEZE_LIMIT}s and no live work child; killing"
    kill "$CODEX_PID" 2>/dev/null; sleep 3; CODEX_PID=""
    finish 4
  fi
  sleep 30 & wait $!
done
st="unknown"
if [ "$CHILD" -eq 1 ]; then wait "$CODEX_PID" 2>/dev/null; st=$?; fi
echo "$st" > "$EXITF"; CODEX_PID=""
finish 2
