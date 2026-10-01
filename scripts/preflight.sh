#!/bin/bash
# preflight.sh: verify every locked role answers before a build starts. Stops at the first failure.
#
#   preflight.sh --executor <triple> --frontend <triple> --reviewer <triple> --consult <triple> \
#                --judge <triple> [--docs <triple>|none] [--dir </abs/project>]
#
# A triple is `agy`, `agy:<model name>`, `codex:<slug>:<effort>`, or `claude:<model>[:<effort>]`.
# Prints one RESOLVED line per role (the exact string to record in the manifest), a MEMORY line,
# any OPEN BUILD elsewhere on this machine, the REDIRECT list of outbound delivery variables,
# and exits 0; or prints FAIL with the reason and exits 1. A model out of quota is a FAIL that
# names the override flag. Never fails on a role CHOICE: only on an engine that does not answer.
# Writes everything it printed to <dir>/.build/preflight.txt, which `ledger.py init` reads.

set -u
EXEC=""; FE=""; REV=""; CON=""; JUD=""; DOCS=""; DIR="$PWD"
while [ $# -gt 0 ]; do
  case "$1" in
    --executor) EXEC="$2"; shift 2;; --frontend) FE="$2"; shift 2;;
    --reviewer) REV="$2"; shift 2;; --consult) CON="$2"; shift 2;;
    --judge) JUD="$2"; shift 2;; --docs) DOCS="$2"; shift 2;;
    --dir) DIR="$2"; shift 2;;
    *) echo "unknown arg: $1" >&2; exit 1;;
  esac
done
EXEC="${EXEC:-agy}"; FE="${FE:-agy}"; REV="${REV:-codex:gpt-6.1-sol:high}"; CON="${CON:-claude:fable:high}"
JUD="${JUD:-claude:opus:medium}"; DOCS="${DOCS:-agy}"
mkdir -p "$DIR/.build"
OUT="$DIR/.build/preflight.txt"; : > "$OUT"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
say() { echo "$*"; echo "$*" >> "$OUT"; }
fail() { echo "FAIL: $*" >&2; echo "FAIL: $*" >> "$OUT"; exit 1; }
family() { echo "${1%%:*}"; }
QUOTA_RE='429|rate.?limit|quota|usage limit|limit reached|RESOURCE_EXHAUSTED|insufficient_quota'

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
  if ! echo "$out" | grep -q "PREFLIGHT OK"; then
    echo "$out" | grep -qiE "$QUOTA_RE" && fail "codex $slug is out of quota or rate-limited; start the build with $2=<another engine> to override"
    fail "codex $slug@$effort did not answer: $(echo "$out" | grep -viE '^hook:' | tail -3 | tr '\n' ' ')"
  fi
  echo "$1"
}
check_claude() {  # claude:<model>[:<effort>]  (effort is recorded only; the agent file governs it)
  local model out
  model=$(echo "$1" | cut -d: -f2)
  [ -n "$model" ] || fail "claude role needs claude:<model>: $1"
  command -v claude >/dev/null || fail "claude CLI not installed"
  out=$(cd "$TMP" && echo "Reply with exactly: PREFLIGHT OK" | perl -e 'alarm shift; exec @ARGV' 300 claude -p --model "$model" 2>&1)
  if ! echo "$out" | grep -q "PREFLIGHT OK"; then
    echo "$out" | grep -qiE "$QUOTA_RE" && fail "claude $model is out of quota or rate-limited; start the build with $2=<another engine> to override"
    fail "claude model $model did not answer: $(echo "$out" | tail -2 | tr '\n' ' ')"
  fi
  echo "$1"
}
resolve() {  # $1 triple, $2 role name (for the override hint)
  case "$(family "$1")" in
    agy) resolve_agy "$1";; codex) check_codex "$1" "$2";; claude) check_claude "$1" "$2";;
    *) fail "unknown engine in $1 (agy | codex:<slug>:<effort> | claude:<model>)";;
  esac
}

# The user's role choice is final. Same-family roles are noted for the ledger, never refused.
[ "$(family "$EXEC")" != "$(family "$CON")" ] || say "NOTE: consult ($CON) shares a family with executor ($EXEC); recorded, not refused"
[ "$(family "$REV")" != "$(family "$JUD")" ] || say "NOTE: judge ($JUD) shares a family with reviewer ($REV); recorded, not refused"
[ "$(family "$REV")" != "$(family "$CON")" ] || say "NOTE: reviewer and consult share a family; the one-item fast lane is off for this build"
# resolve agy's top model once here: resolve() runs in a subshell, so a cache set inside it would not survive
case "$EXEC $FE $REV $CON $JUD $DOCS" in *agy*)
  command -v agy >/dev/null || fail "agy CLI not installed"
  AGY_TOP=$(agy models 2>/dev/null | head -1 | cut -f2); [ -n "$AGY_TOP" ] || fail "agy models returned nothing";;
esac
for role in EXEC FE REV CON JUD DOCS; do
  val="${!role}"   # indirect: a model name with spaces stays one value
  case "$role" in EXEC) n=executor;; FE) n=frontend;; REV) n=reviewer;; CON) n=consult;; JUD) n=judge;; DOCS) n=docs;; esac
  [ "$role" = "DOCS" ] && [ "$val" = "none" ] && continue
  r=$(resolve "$val" "$n") || exit 1
  say "RESOLVED $n=$r"
done
[ "$DOCS" = "none" ] && say "RESOLVED docs=none"

# Machine state: free memory, and any other open build that will compete for it.
page=$(pagesize); total=$(sysctl -n hw.memsize)
free_pages=$(vm_stat | awk '/Pages free|Pages inactive|Pages speculative/ {gsub("\\.","",$NF); s+=$NF} END {print s+0}')
say "MEMORY: $((free_pages * page / 1073741824)) GB free or reclaimable of $((total / 1073741824)) GB"
here=$(cd "$DIR" && pwd -P)
find "$HOME/github" -maxdepth 6 -name node_modules -prune -o -path '*/.build/state.json' -print 2>/dev/null | while read -r st; do
  proj=$(cd "$(dirname "$st")/.." && pwd -P)
  [ "$proj" = "$here" ] && continue
  python3 -c "import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get('status')=='open' else 1)" "$st" 2>/dev/null \
    && say "OPEN BUILD elsewhere: $proj (it shares this machine's memory and engine quotas)"
done

# Outbound delivery variables a local dev server must never fire for real (reference/local-environment.md).
# only URL-valued variables are redirected: a port, a token, or a flag keeps its value
names=$(cat "$DIR"/.env "$DIR"/.env.* 2>/dev/null | grep -E '^[A-Z0-9_]*(WEBHOOK|N8N|BREVO|SMTP|MAILGUN|SENDGRID|RESEND|POSTMARK|TELEGRAM|SLACK|TWILIO)[A-Z0-9_]*=' \
        | grep -iE '=["'"'"']?https?://|(URL|ENDPOINT|WEBHOOK|HOOK)[A-Z0-9_]*=' | cut -d= -f1 | sort -u | tr '\n' ' ')
say "REDIRECT: ${names:-none found}"
rm -rf "$TMP"
say "PREFLIGHT OK"
