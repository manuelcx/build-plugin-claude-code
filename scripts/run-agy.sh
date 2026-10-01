#!/bin/bash
# run-agy.sh: launch one agy run with the watchdog built in, and exit exactly once.
#
# Usage:
#   run-agy.sh --tag <tag> --brief </abs/brief.md> --model "<name>" [--plan]
#              [--read </abs/file>]... [--conversation <id>] [--prompt "<text>"]
#              [--add-dir </abs/dir>]... [--dir </abs/project>] [--backstop 3600]
#              [--print-timeout <duration>] [--startup-limit 300] [--freeze-limit 1200]
#   run-agy.sh --attach <tag> [--dir </abs/project>]     # watch a run whose launcher was killed
#
# Writes <dir>/.build/runs/<tag>.jsonl (event log), <tag>.pid, and <tag>.exit (the engine's wait
# status when this script saw it exit). Prints the report at exit.
# Exit codes: 0 report present, 2 finished with no report, 3 startup hang (killed after one
# automatic relaunch), 4 frozen (killed after one automatic resume), 5 launch failed,
# 6 engine killed by SIGKILL (usually macOS memory pressure), 7 quota or rate limit.
#
# Recipe notes, all load-bearing:
# - agy hangs on a large inline -p, so the prompt is tiny and points at files.
# - --output-format stream-json gives a heartbeat (log mtime) and a salvageable trail.
# - --dangerously-skip-permissions is required even in plan mode or agy prompts and hangs.
# - --mode plan is structurally read-only; the contract file must ALSO say report-only.
# - Never pass --effort: it is rejected for any model whose name carries a level.
# - The engine runs in its own session (perl POSIX setsid; macOS has no setsid command), so a
#   harness kill of this script leaves it running; `--attach <tag>` picks it up again.
# - The print timeout sits two minutes under the perl backstop, so agy's own timeout fires first
#   and the resume path runs; the backstop is only for the case where everything else died.
# - Liveness and kills go by the captured PID, never by a process-table pattern.

set -u
TAG=""; BRIEF=""; MODEL=""; PLAN=0; CONV=""; PROMPT=""; DIR="$PWD"; ATTACH=""
BACKSTOP=3600; PT=""; STARTUP_LIMIT=300; FREEZE_LIMIT=1200
READS=(); ADDDIRS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG="$2"; shift 2;;
    --brief) BRIEF="$2"; shift 2;;
    --model) MODEL="$2"; shift 2;;
    --plan) PLAN=1; shift;;
    --read) READS+=("$2"); shift 2;;
    --conversation) CONV="$2"; shift 2;;
    --prompt) PROMPT="$2"; shift 2;;
    --add-dir) ADDDIRS+=("--add-dir" "$2"); shift 2;;
    --dir) DIR="$2"; shift 2;;
    --backstop) BACKSTOP="$2"; shift 2;;
    --print-timeout) PT="$2"; shift 2;;
    --startup-limit) STARTUP_LIMIT="$2"; shift 2;;
    --freeze-limit) FREEZE_LIMIT="$2"; shift 2;;
    --attach) ATTACH="$2"; TAG="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 5;;
  esac
done
cd "$DIR" || { echo "cannot cd to $DIR" >&2; exit 5; }
mkdir -p .build/runs
HERE="$(cd "$(dirname "$0")" && pwd)"
LOG=".build/runs/$TAG.jsonl"; PIDF=".build/runs/$TAG.pid"; EXITF=".build/runs/$TAG.exit"
[ -n "$PT" ] || PT="$((BACKSTOP > 240 ? BACKSTOP - 120 : BACKSTOP))s"
alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null; }
has_report() { python3 "$HERE/agy-report.py" --check "$1" >/dev/null 2>&1; }
is_quota() { python3 "$HERE/agy-report.py" --quota "$1" >/dev/null 2>&1; }
conv_id() { python3 "$HERE/agy-report.py" --id "$1" 2>/dev/null; }
rm -f .build/stop-guard.count

if [ -z "$ATTACH" ]; then
  [ -n "$TAG" ] && [ -n "$MODEL" ] || { echo "need --tag and --model" >&2; exit 5; }
  [ -n "$BRIEF" ] || [ -n "$PROMPT" ] || { echo "need --brief, or --prompt for a resume" >&2; exit 5; }
  [ -z "$BRIEF" ] || [ -f "$BRIEF" ] || { echo "brief not found: $BRIEF" >&2; exit 5; }
  if [ -f "$PIDF" ] && alive "$(cat "$PIDF")"; then
    echo "engine for $TAG is still alive (pid $(cat "$PIDF")); use --attach $TAG, never a second launch" >&2; exit 5
  fi
  MODEL="${MODEL#agy:}"   # accept the ledger's role triple form as well as the bare model name
  case "$MODEL" in *$'\t'*) MODEL="$(printf '%s' "$MODEL" | cut -f2)";; esac   # a pasted `agy models` row
fi

# Every --read file (a contract from the plugin) is copied INTO the project so the engine never
# reads outside its workspace root, and the copy pins the exact contract text this run used.
mkdir -p .build/contracts
LOCAL_READS=()
for r in ${READS[@]+"${READS[@]}"}; do
  [ -f "$r" ] || { echo "read file not found: $r" >&2; exit 5; }
  cp "$r" ".build/contracts/$(basename "$r")"
  LOCAL_READS+=("$(pwd -P)/.build/contracts/$(basename "$r")")
done
if [ -z "$ATTACH" ] && [ -z "$PROMPT" ]; then
  PROMPT="Read, in this order:"
  for r in ${LOCAL_READS[@]+"${LOCAL_READS[@]}"}; do PROMPT="$PROMPT $r, then"; done
  PROMPT="$PROMPT $BRIEF. Then carry out the task the brief describes and produce the report it asks for."
fi

MODE=(); [ "$PLAN" -eq 1 ] && MODE=(--mode plan)
AGY_PID=""; CHILD=0
# On any exit, remove the pid file only when the engine is gone. A kill of this script leaves a
# live engine and its pid file in place, so `--attach` can pick it up.
cleanup() { alive "$AGY_PID" || rm -f "$PIDF"; }
trap cleanup EXIT
trap 'exit 130' INT TERM

launch() {  # $1 = conversation id or empty, $2 = prompt
  local conv="$1" prompt="$2"
  local convargs=(); [ -n "$conv" ] && convargs=(--conversation "$conv")
  : > "$LOG"; rm -f "$EXITF"
  perl -e 'use POSIX qw(setsid); setsid(); alarm shift; exec @ARGV' "$BACKSTOP" \
    agy ${convargs[@]+"${convargs[@]}"} --dangerously-skip-permissions ${MODE[@]+"${MODE[@]}"} --model "$MODEL" \
    --output-format stream-json --print-timeout "$PT" ${ADDDIRS[@]+"${ADDDIRS[@]}"} \
    -p "$prompt" > "$LOG" 2>&1 &
  AGY_PID=$!; CHILD=1
  echo "$AGY_PID" > "$PIDF"
  echo "launched agy pid=$AGY_PID log=$LOG model=$MODEL plan=$PLAN print-timeout=$PT"
}

# watch: returns 0 exited, 1 startup hang, 2 frozen
watch() {
  local started now mt
  started=$(date +%s)
  sleep 10 & wait $!
  while alive "$AGY_PID"; do
    now=$(date +%s)
    if [ ! -s "$LOG" ]; then
      [ $((now - started)) -ge "$STARTUP_LIMIT" ] && return 1
    else
      mt=$(stat -f %m "$LOG" 2>/dev/null || echo "$now")
      if [ $((now - mt)) -gt "$FREEZE_LIMIT" ]; then
        grep -q '"event": *"result"' "$LOG" && return 0   # finished; lingering zombie
        return 2
      fi
    fi
    sleep 30 & wait $!
  done
  return 0
}

reap() {  # record the engine's wait status when it is our child; an attached run has none
  local st="unknown"
  if [ "$CHILD" -eq 1 ]; then wait "$AGY_PID" 2>/dev/null; st=$?; fi
  echo "$st" > "$EXITF"; AGY_PID=""
  [ "$st" = "137" ] && return 1 || return 0
}

finish() {  # print the report and exit with the code the ladder reads
  python3 "$HERE/agy-report.py" "$LOG"
  if grep -qiE 'time(d)? ?out waiting for response' "$LOG" && ! has_report "$LOG"; then echo "cut off by print timeout ($PT)"; fi
  if has_report "$LOG"; then exit 0; fi
  if [ "$(cat "$EXITF" 2>/dev/null)" = "137" ]; then echo "ENGINE KILLED (SIGKILL, status 137): usually macOS memory pressure"; exit 6; fi
  if is_quota "$LOG"; then echo "QUOTA OR RATE LIMIT: back off per the unattended contract"; exit 7; fi
  exit 2
}

# ---- attempt 1 (or attach to a run whose launcher died)
if [ -n "$ATTACH" ]; then
  [ -f "$PIDF" ] || { echo "no pid file for $TAG"; [ -f "$LOG" ] && finish; exit 5; }
  AGY_PID="$(cat "$PIDF")"
  alive "$AGY_PID" || { echo "engine for $TAG already exited"; AGY_PID=""; finish; }
  echo "attached to agy pid=$AGY_PID log=$LOG"
else
  launch "$CONV" "$PROMPT"
fi
watch; rc=$?
if [ -n "$ATTACH" ] && [ "$rc" -ne 0 ]; then
  # an attached run has no brief or model of its own: kill it and let the orchestrator relaunch cold
  echo "attached run $( [ "$rc" -eq 1 ] && echo 'hung at startup' || echo 'froze' ); killing it for a cold relaunch"
  kill "$AGY_PID" 2>/dev/null; AGY_PID=""; python3 "$HERE/agy-report.py" "$LOG"; exit $((rc == 1 ? 3 : 4))
fi
if [ "$rc" -eq 1 ]; then
  echo "STARTUP HANG: no events in ${STARTUP_LIMIT}s; killing and relaunching once"
  kill "$AGY_PID" 2>/dev/null; sleep 3
  launch "$CONV" "$PROMPT"
  watch; rc=$?
  if [ "$rc" -eq 1 ]; then echo "STARTUP HANG again; giving up"; kill "$AGY_PID" 2>/dev/null; exit 3; fi
fi
if [ "$rc" -eq 2 ]; then
  echo "FROZEN: no events for ${FREEZE_LIMIT}s; killing and resuming once"
  kill "$AGY_PID" 2>/dev/null; sleep 3; AGY_PID=""
  ID=$(conv_id "$LOG")
  if [ -n "$ID" ]; then
    cp "$LOG" "$LOG.frozen"
    launch "$ID" "Continue from where you stopped, then produce the report your brief asks for."
    watch; rc=$?
    if [ "$rc" -eq 2 ]; then echo "FROZEN again; giving up"; kill "$AGY_PID" 2>/dev/null; python3 "$HERE/agy-report.py" "$LOG"; exit 4; fi
  else
    echo "no conversation id in log; cannot resume"; python3 "$HERE/agy-report.py" "$LOG"; exit 4
  fi
fi
reap || finish   # a SIGKILL is reported as such, never resumed here

# ---- no report: classify a quota error first, otherwise resume the conversation once (never when attached)
if [ -z "$ATTACH" ] && ! has_report "$LOG" && ! is_quota "$LOG"; then
  ID=$(conv_id "$LOG")
  if [ -n "$ID" ]; then
    echo "exited with no report; resuming the conversation once"
    cp "$LOG" "$LOG.noreport"
    launch "$ID" "Produce the report your brief asks for, for the work you completed."
    watch >/dev/null; reap || true
  fi
fi
finish
