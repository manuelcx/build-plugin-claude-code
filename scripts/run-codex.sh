#!/bin/bash
# run-codex.sh: launch one codex run with the trust pre-flight and watchdog built in; exit once.
#
# Usage:
#   run-codex.sh --tag <tag> --brief </abs/brief.md> --model <slug> --effort <effort> [--readonly]
#                [--read </abs/file>]... [--prompt "<text>"] [--dir </abs/project>]
#                [--backstop 7200] [--freeze-limit 1200]
#
# Writes <dir>/.build/runs/<tag>.jsonl (event log), <tag>.last.md (final message), <tag>.pid.
# Exit codes: 0 final message present, 2 finished with no final message (salvage printed),
# 4 frozen and killed (salvage printed), 5 launch failed.
#
# Recipe notes, all load-bearing:
# - An untrusted project dir makes codex hang silently on a trust prompt; trust is per exact
#   path and not inherited, so ensure_codex_trust runs every time (no-op when already trusted).
# - -m and model_reasoning_effort are always explicit; otherwise codex inherits the global
#   config default, which is pinned for interactive use.
# - --json streams one event per step: the heartbeat the watchdog reads and a salvage trail.
# - -o writes the final message to a file for verbatim relay.
# - The perl alarm is the oversized backstop for when this script itself dies. Never size it down.
# - Liveness and kills go by the captured PID, never by a process-table pattern.

set -u
TAG=""; BRIEF=""; MODEL=""; EFFORT=""; RO=0; PROMPT=""; DIR="$PWD"; BACKSTOP=7200; FREEZE_LIMIT=1200
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
    *) echo "unknown arg: $1" >&2; exit 5;;
  esac
done
[ -n "$TAG" ] && [ -n "$BRIEF" ] && [ -n "$MODEL" ] && [ -n "$EFFORT" ] || { echo "need --tag, --brief, --model, --effort" >&2; exit 5; }
[ -f "$BRIEF" ] || { echo "brief not found: $BRIEF" >&2; exit 5; }
cd "$DIR" || { echo "cannot cd to $DIR" >&2; exit 5; }
mkdir -p .build/runs
HERE="$(cd "$(dirname "$0")" && pwd)"
LOG=".build/runs/$TAG.jsonl"; PIDF=".build/runs/$TAG.pid"; LAST=".build/runs/$TAG.last.md"
rm -f "$LAST"

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

CODEX_PID=""
cleanup() { [ -n "$CODEX_PID" ] && kill -0 "$CODEX_PID" 2>/dev/null && kill "$CODEX_PID" 2>/dev/null; rm -f "$PIDF"; }
trap cleanup EXIT INT TERM

: > "$LOG"
printf '%s\n' "$PROMPT" | perl -e 'alarm shift; exec @ARGV' "$BACKSTOP" \
  codex exec --json --color never -s "$SANDBOX" ${GITCHK[@]+"${GITCHK[@]}"} \
  -m "$MODEL" -c model_reasoning_effort="$EFFORT" -o "$LAST" - > "$LOG" 2>&1 &
CODEX_PID=$!
echo "$CODEX_PID" > "$PIDF"
echo "launched codex pid=$CODEX_PID log=$LOG model=$MODEL effort=$EFFORT sandbox=$SANDBOX"

started=$(date +%s); sleep 10; frozen=0
while kill -0 "$CODEX_PID" 2>/dev/null; do
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
    python3 "$HERE/codex-report.py" "$LOG" "$LAST"
    exit 4
  fi
  if [ $((now - mt)) -gt "$FREEZE_LIMIT" ]; then
    # a long test or build inside one tool call is silent; give a live test/build child more time once
    if [ "$frozen" -eq 0 ] && echo "$childcmd" | grep -qE 'vitest|jest|npm|pnpm|bun|tsc|next|python|pytest|cargo|go '; then
      frozen=1; echo "quiet ${FREEZE_LIMIT}s but a build/test child is live; allowing one more window"; sleep "$FREEZE_LIMIT"; continue
    fi
    echo "FROZEN: no events for ${FREEZE_LIMIT}s and no live work child; killing"
    kill "$CODEX_PID" 2>/dev/null; sleep 3; CODEX_PID=""
    python3 "$HERE/codex-report.py" "$LOG" "$LAST"
    exit 4
  fi
  sleep 30
done
wait "$CODEX_PID" 2>/dev/null; CODEX_PID=""
python3 "$HERE/codex-report.py" "$LOG" "$LAST"
[ -s "$LAST" ] && exit 0 || exit 2
