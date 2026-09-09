#!/bin/bash
# structure-gate.sh: mechanical structure check over a list of files. No model judgment.
#
#   structure-gate.sh [--cap 1000] [--dir </abs/project>] <file>...
#   structure-gate.sh --changed <snapshot-tag> [--dir ...]     # files changed since a snapshot
#
# Reports: hand-written files over the line cap (machine-generated files exempt), test files
# whose tests sit in one flat describe (or none) with many cases, and build-process tags in
# test names. Exit 1 when any violation is found in the listed files, else 0.

set -u
CAP=1000; DIR="$PWD"; CHANGED=""; FILES=()
while [ $# -gt 0 ]; do
  case "$1" in
    --cap) CAP="$2"; shift 2;; --dir) DIR="$2"; shift 2;; --changed) CHANGED="$2"; shift 2;;
    *) FILES+=("$1"); shift;;
  esac
done
cd "$DIR" || exit 5
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ -n "$CHANGED" ]; then
  while IFS=$'\t' read -r kind path; do [ "$kind" != "D" ] && FILES+=("$path"); done < <("$HERE/snapshot.sh" changed "$CHANGED" --dir "$DIR")
fi
[ ${#FILES[@]} -gt 0 ] || { echo "no files to check"; exit 0; }

generated() {  # exempt: lockfiles, snapshots, minified, generated dirs, generated headers
  case "$1" in
    *package-lock.json|*pnpm-lock.yaml|*yarn.lock|*bun.lockb|*Cargo.lock|*poetry.lock|*Gemfile.lock|*composer.lock) return 0;;
    *.snap|*.min.js|*.min.css|*.map|*.svg|*.json) return 0;;
    node_modules/*|*/node_modules/*|dist/*|build/*|.next/*|out/*|coverage/*|*/generated/*|*/__generated__/*|*/meta/*_snapshot.json|*/migrations/meta/*) return 0;;
  esac
  head -5 "$1" 2>/dev/null | grep -qiE '@generated|DO NOT EDIT|automatically generated' && return 0
  return 1
}
is_test() { case "$1" in *.test.*|*.spec.*|*/__tests__/*|*_test.go|*_test.py|*/tests/*) return 0;; *) return 1;; esac; }

TAG_RE="(it|test|describe)[[:space:]]*\([[:space:]]*['\"\`][^'\"\`]*(^|[^a-zA-Z])(item|cycle|reviewer|round|rev|fix)[[:space:]]*[-#:]?[[:space:]]*[0-9]+"
viol=0
for f in "${FILES[@]}"; do
  [ -f "$f" ] || continue
  generated "$f" && continue
  n=$(wc -l < "$f" | tr -d ' ')
  if [ "$n" -gt "$CAP" ]; then echo "VIOLATION line-cap: $f has $n lines (cap $CAP)"; viol=1; fi
  if is_test "$f"; then
    d=$(grep -cE '^[[:space:]]*(describe|context|suite)[[:space:]]*\(' "$f")
    c=$(grep -cE '^[[:space:]]*(it|test)([[:space:]]*\.each[[:space:]]*\([^)]*\))?[[:space:]]*\(' "$f")
    if [ "$c" -ge 15 ] && [ "$d" -le 1 ]; then echo "VIOLATION flat-describe: $f has $c cases in $d describe block(s)"; viol=1; fi
    tags=$(grep -nE "$TAG_RE" "$f" | head -5)
    if [ -n "$tags" ]; then echo "VIOLATION build-tag in test name: $f"; echo "$tags" | sed 's/^/    /'; viol=1; fi
  fi
done
[ "$viol" -eq 0 ] && echo "structure gate clean over ${#FILES[@]} file(s)"
exit $viol
