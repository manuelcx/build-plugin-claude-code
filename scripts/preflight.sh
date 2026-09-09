#!/bin/bash
# preflight.sh: verify every locked role answers before a build starts. Stops at the first failure.
#
#   preflight.sh --executor <triple> --frontend <triple> --reviewer <triple> --consult <triple>
#
# A triple is `agy`, `agy:<model name>`, `codex:<slug>:<effort>`, or `claude:<model>[:<effort>]`.
# Prints one RESOLVED line per role (the exact string to record in the manifest) and exits 0,
# or prints FAIL with the reason and exits 1. Never fails on a role CHOICE: only on an engine that does not answer.

set -u
EXEC=""; FE=""; REV=""; CON=""
while [ $# -gt 0 ]; do
  case "$1" in
    --executor) EXEC="$2"; shift 2;; --frontend) FE="$2"; shift 2;;
    --reviewer) REV="$2"; shift 2;; --consult) CON="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 1;;
  esac
done
EXEC="${EXEC:-agy}"; FE="${FE:-agy}"; REV="${REV:-codex:gpt-6-astra:medium}"; CON="${CON:-claude:fable:high}"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
family() { echo "${1%%:*}"; }

AGY_TOP=""
resolve_agy() {  # agy or agy:<name>
  local t="$1"
  if [ -z "$AGY_TOP" ]; then
    command -v agy >/dev/null || fail "agy CLI not installed"
    AGY_TOP=$(agy models 2>/dev/null | head -1 | cut -f2)
    [ -n "$AGY_TOP" ] || fail "agy models returned nothing"
  fi
  if [ "$t" = "agy" ]; then echo "agy:$AGY_TOP"; else
    local want="${t#agy:}"
    agy models 2>/dev/null | cut -f2 | grep -qxF "$want" || fail "agy model not in list: $want"
    echo "agy:$want"
  fi
}
check_codex() {  # codex:<slug>:<effort>
  local slug effort out
  slug=$(echo "$1" | cut -d: -f2); effort=$(echo "$1" | cut -d: -f3)
  [ -n "$slug" ] && [ -n "$effort" ] || fail "codex role needs codex:<slug>:<effort>: $1"
  [ "$effort" != "ultra" ] || fail "effort ultra is not allowed for a locked role"
  command -v codex >/dev/null || fail "codex CLI not installed"
  out=$(cd "$TMP" && perl -e 'alarm shift; exec @ARGV' 300 codex exec --skip-git-repo-check -s read-only --color never \
        -m "$slug" -c model_reasoning_effort="$effort" "Reply with exactly: PREFLIGHT OK" 2>&1)
  echo "$out" | grep -q "PREFLIGHT OK" || fail "codex $slug@$effort did not answer: $(echo "$out" | grep -viE '^hook:' | tail -3 | tr '\n' ' ')"
  echo "$1"
}
check_claude() {  # claude:<model>[:<effort>]  (effort is recorded only; the agent file governs it)
  local model out
  model=$(echo "$1" | cut -d: -f2)
  [ -n "$model" ] || fail "claude role needs claude:<model>: $1"
  command -v claude >/dev/null || fail "claude CLI not installed"
  out=$(cd "$TMP" && echo "Reply with exactly: PREFLIGHT OK" | perl -e 'alarm shift; exec @ARGV' 300 claude -p --model "$model" 2>&1)
  echo "$out" | grep -q "PREFLIGHT OK" || fail "claude model $model did not answer: $(echo "$out" | tail -2 | tr '\n' ' ')"
  echo "$1"
}
resolve() {
  case "$(family "$1")" in
    agy) resolve_agy "$1";; codex) check_codex "$1";; claude) check_claude "$1";;
    *) fail "unknown engine in $1 (agy | codex:<slug>:<effort> | claude:<model>)";;
  esac
}

# The user's role choice is final. Same-family roles are noted for the ledger, never refused.
[ "$(family "$EXEC")" != "$(family "$CON")" ] || echo "NOTE: consult ($CON) shares a family with executor ($EXEC); recorded, not refused"
[ "$(family "$FE")" != "$(family "$CON")" ] || echo "NOTE: consult ($CON) shares a family with frontend ($FE); recorded, not refused"
for role in EXEC FE REV CON; do
  val="${!role}"; r=$(resolve "$val") || exit 1
  case "$role" in EXEC) n=executor;; FE) n=frontend;; REV) n=reviewer;; CON) n=consult;; esac
  echo "RESOLVED $n=$r"
done
rm -rf "$TMP"
echo "PREFLIGHT OK"
