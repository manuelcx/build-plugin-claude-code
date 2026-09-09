#!/bin/bash
# run-agy.sh: launch one agy run with the watchdog built in, and exit exactly once.
#
# Usage:
#   run-agy.sh --tag <tag> --brief </abs/brief.md> --model "<name>" [--plan]
#              [--read </abs/file>]... [--conversation <id>] [--prompt "<text>"]
#              [--add-dir </abs/dir>]... [--dir </abs/project>] [--backstop 3600]
#              [--print-timeout 20m] [--startup-limit 300] [--freeze-limit 1200]
#
# Writes <dir>/.build/runs/<tag>.jsonl (event log) and <tag>.pid. Prints the report at exit.
# Exit codes: 0 report present, 2 finished with no report, 3 startup hang (killed after one
# automatic relaunch), 4 frozen (killed after one automatic resume), 5 launch failed.
#
# Recipe notes, all load-bearing:
# - agy hangs on a large inline -p, so the prompt is tiny and points at files.
# - --output-format stream-json gives a heartbeat (log mtime) and a salvageable trail.
# - --dangerously-skip-permissions is required even in plan mode or agy prompts and hangs.
# - --mode plan is structurally read-only; the contract file must ALSO say report-only.
# - Never pass --effort: it is rejected for any model whose name carries a level.
# - perl alarm is the oversized backstop for the case where this script itself dies.
# - Liveness and kills go by the captured PID, never by a process-table pattern.

set -u
TAG=""; BRIEF=""; MODEL=""; PLAN=0; CONV=""; PROMPT=""; DIR="$PWD"
BACKSTOP=3600; PT="20m"; STARTUP_LIMIT=300; FREEZE_LIMIT=1200
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
    *) echo "unknown arg: $1" >&2; exit 5;;
  esac
done
[ -n "$TAG" ] && [ -n "$MODEL" ] || { echo "need --tag and --model" >&2; exit 5; }
[ -n "$BRIEF" ] || [ -n "$PROMPT" ] || { echo "need --brief, or --prompt for a resume" >&2; exit 5; }
[ -z "$BRIEF" ] || [ -f "$BRIEF" ] || { echo "brief not found: $BRIEF" >&2; exit 5; }
MODEL="${MODEL#agy:}"   # accept the ledger's role triple form as well as the bare model name
cd "$DIR" || { echo "cannot cd to $DIR" >&2; exit 5; }
mkdir -p .build/runs
HERE="$(cd "$(dirname "$0")" && pwd)"
LOG=".build/runs/$TAG.jsonl"; PIDF=".build/runs/$TAG.pid"

# Every --read file (a contract from the plugin) is copied INTO the project so the engine never
# reads outside its workspace root, and the copy pins the exact contract text this run used.
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

MODE=(); [ "$PLAN" -eq 1 ] && MODE=(--mode plan)
AGY_PID=""
cleanup() { [ -n "$AGY_PID" ] && kill -0 "$AGY_PID" 2>/dev/null && kill "$AGY_PID" 2>/dev/null; rm -f "$PIDF"; }
trap cleanup EXIT INT TERM

launch() {  # $1 = log file, $2 = conversation id or empty, $3 = prompt
  local log="$1" conv="$2" prompt="$3"
  local convargs=(); [ -n "$conv" ] && convargs=(--conversation "$conv")
  : > "$log"
  perl -e 'alarm shift; exec @ARGV' "$BACKSTOP" \
    agy ${convargs[@]+"${convargs[@]}"} --dangerously-skip-permissions ${MODE[@]+"${MODE[@]}"} --model "$MODEL" \
    --output-format stream-json --print-timeout "$PT" ${ADDDIRS[@]+"${ADDDIRS[@]}"} \
    -p "$prompt" > "$log" 2>&1 &
  AGY_PID=$!
  echo "$AGY_PID" > "$PIDF"
  echo "launched agy pid=$AGY_PID log=$log model=$MODEL plan=$PLAN"
}

# watch: returns 0 exited, 1 startup hang, 2 frozen
watch() {
  local log="$1" started now mt
  started=$(date +%s)
  sleep 10
  while kill -0 "$AGY_PID" 2>/dev/null; do
    now=$(date +%s)
    if [ ! -s "$log" ]; then
      [ $((now - started)) -ge "$STARTUP_LIMIT" ] && return 1
    else
      mt=$(stat -f %m "$log" 2>/dev/null || echo "$now")
      if [ $((now - mt)) -gt "$FREEZE_LIMIT" ]; then
        grep -q '"event": *"result"' "$log" && return 0   # finished; lingering zombie
        return 2
      fi
    fi
    sleep 30
  done
  return 0
}

conv_id() { python3 -c "import json,sys
try: print(json.loads(open(sys.argv[1]).readline()).get('conversation_id',''))
except Exception: print('')" "$1"; }

has_report() { python3 "$HERE/agy-report.py" --check "$1" >/dev/null 2>&1; }

# ---- attempt 1
launch "$LOG" "$CONV" "$PROMPT"
watch "$LOG"; rc=$?
if [ "$rc" -eq 1 ]; then
  echo "STARTUP HANG: no events in ${STARTUP_LIMIT}s; killing and relaunching once"
  kill "$AGY_PID" 2>/dev/null; sleep 3
  launch "$LOG" "$CONV" "$PROMPT"
  watch "$LOG"; rc=$?
  if [ "$rc" -eq 1 ]; then echo "STARTUP HANG again; giving up"; kill "$AGY_PID" 2>/dev/null; exit 3; fi
fi
if [ "$rc" -eq 2 ]; then
  echo "FROZEN: no events for ${FREEZE_LIMIT}s; killing and resuming once"
  kill "$AGY_PID" 2>/dev/null; sleep 3
  ID=$(conv_id "$LOG")
  if [ -n "$ID" ]; then
    cp "$LOG" "$LOG.frozen"
    launch "$LOG" "$ID" "Continue from where you stopped, then produce the report your brief asks for."
    watch "$LOG"; rc=$?
    if [ "$rc" -eq 2 ]; then echo "FROZEN again; giving up"; kill "$AGY_PID" 2>/dev/null; python3 "$HERE/agy-report.py" "$LOG"; exit 4; fi
  else
    echo "no conversation id in log; cannot resume"; python3 "$HERE/agy-report.py" "$LOG"; exit 4
  fi
fi
wait "$AGY_PID" 2>/dev/null; AGY_PID=""

# ---- print-timeout without a report: one resume with a bigger bound
if ! has_report "$LOG" && grep -q 'timeout waiting for response' "$LOG"; then
  ID=$(conv_id "$LOG")
  if [ -n "$ID" ]; then
    echo "response-wait timeout with no report; resuming once with --print-timeout 40m"
    PT="40m"; cp "$LOG" "$LOG.timeout"
    launch "$LOG" "$ID" "Produce the report your brief asks for, for the work you completed."
    watch "$LOG" >/dev/null; wait "$AGY_PID" 2>/dev/null; AGY_PID=""
  fi
fi

python3 "$HERE/agy-report.py" "$LOG"
if has_report "$LOG"; then exit 0; else exit 2; fi
