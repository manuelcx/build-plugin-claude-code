#!/bin/bash
# snapshot.sh: record the exact bytes of the working tree, list what changed since, diff, restore.
#
#   snapshot.sh save <tag> [--dir </abs/project>]
#       records HEAD, a manifest of every tracked and untracked (non-ignored) file's sha256,
#       and a byte copy of every file that differs from HEAD, under .build/snap/<tag>/
#   snapshot.sh changed <tag> [--dir ...]
#       prints one line per file added (A), modified (M), or deleted (D) relative to the snapshot
#   snapshot.sh diff <tag> [<path>...] [--dir ...]
#       unified diff of the snapshot bytes against the current bytes (all changed files by default)
#   snapshot.sh restore <tag> <path>... [--dir ...]
#       restores each path to its snapshot bytes (or deletes it if it did not exist then)
#   snapshot.sh verify <tag> <path>... [--dir ...]
#       exit 0 when every listed path is byte-identical to the snapshot, else lists mismatches
#
# Restoring recorded bytes is mechanical, not authorship: this is the one write the
# orchestrator may perform on project files, per the actor rule. Paths may contain spaces.

set -u
CMD="${1:-}"; shift || true
TAG="${1:-}"; shift || true
DIR="$PWD"; PATHS=()
while [ $# -gt 0 ]; do
  case "$1" in --dir) DIR="$2"; shift 2;; *) PATHS+=("$1"); shift;; esac
done
[ -n "$CMD" ] && [ -n "$TAG" ] || { sed -n '2,18p' "$0"; exit 5; }
cd "$DIR" || exit 5
SNAP=".build/snap/$TAG"

# manifest lines are "<64-char sha>  <path>"; the path starts at column 67 and may contain spaces
manifest() { git ls-files -co --exclude-standard -z | grep -zvE '^\.build(-archive)?/' | xargs -0 shasum -a 256 2>/dev/null | LC_ALL=C sort -k2; }
sha_of() { local f="$1"; [ -f "$f" ] && shasum -a 256 "$f" | cut -c1-64; }
snap_sha() { awk -v p="$1" 'substr($0,67)==p {print substr($0,1,64); exit}' "$SNAP/manifest"; }
# Byte copies are stored with a `.bytes` suffix so no test runner, linter, or type checker ever
# collects them as project files (a copied `x.test.ts` would otherwise run as a test).
snap_bytes() {  # print the snapshot bytes of a path to stdout; exit 1 if it did not exist at snapshot
  local f="$1" commit
  if [ -f "$SNAP/files/$f.bytes" ]; then cat "$SNAP/files/$f.bytes"; return 0; fi
  commit=$(cat "$SNAP/commit")
  if [ -n "$(snap_sha "$f")" ] && [ "$commit" != "none" ] && git cat-file -e "$commit:$f" 2>/dev/null; then git show "$commit:$f"; return 0; fi
  return 1
}

case "$CMD" in
  save)
    mkdir -p "$SNAP/files"
    git rev-parse HEAD > "$SNAP/commit" 2>/dev/null || echo "none" > "$SNAP/commit"
    manifest > "$SNAP/manifest"
    git --no-pager diff HEAD > "$SNAP/dirty.patch" 2>/dev/null || true
    { git diff --name-only HEAD 2>/dev/null; git ls-files --others --exclude-standard; } | grep -vE '^\.build(-archive)?/' | LC_ALL=C sort -u | while IFS= read -r f; do
      [ -f "$f" ] || continue
      mkdir -p "$SNAP/files/$(dirname "$f")"; cp "$f" "$SNAP/files/$f.bytes"
    done
    echo "snapshot $TAG saved: commit $(cat "$SNAP/commit"), $(wc -l < "$SNAP/manifest" | tr -d ' ') files"
    ;;
  changed)
    [ -f "$SNAP/manifest" ] || { echo "no snapshot $TAG" >&2; exit 5; }
    manifest > "$SNAP/manifest.now"
    awk '{print substr($0,67)"\t"substr($0,1,64)}' "$SNAP/manifest" | LC_ALL=C sort > "$SNAP/a.tsv"
    awk '{print substr($0,67)"\t"substr($0,1,64)}' "$SNAP/manifest.now" | LC_ALL=C sort > "$SNAP/b.tsv"
    LC_ALL=C join -t "$(printf '\t')" -a1 -a2 -e MISSING -o 0,1.2,2.2 "$SNAP/a.tsv" "$SNAP/b.tsv" | awk -F'\t' '
      $2=="MISSING" {print "A\t"$1; next}
      $3=="MISSING" {print "D\t"$1; next}
      $2!=$3 {print "M\t"$1}'
    ;;
  diff)
    [ -f "$SNAP/manifest" ] || { echo "no snapshot $TAG" >&2; exit 5; }
    if [ ${#PATHS[@]} -eq 0 ]; then
      while IFS=$'\t' read -r kind path; do PATHS+=("$path"); done < <("$0" changed "$TAG" --dir "$DIR")
    fi
    for f in ${PATHS[@]+"${PATHS[@]}"}; do
      tmp=$(mktemp); if snap_bytes "$f" > "$tmp" 2>/dev/null; then old="$tmp"; else old=/dev/null; fi
      [ -f "$f" ] && new="$f" || new=/dev/null
      diff -u --label "snapshot/$f" --label "current/$f" "$old" "$new"
      rm -f "$tmp"
    done
    ;;
  restore)
    [ -f "$SNAP/manifest" ] || { echo "no snapshot $TAG" >&2; exit 5; }
    for f in "${PATHS[@]}"; do
      if [ -f "$SNAP/files/$f.bytes" ]; then mkdir -p "$(dirname "$f")"; cp "$SNAP/files/$f.bytes" "$f"; echo "restored (dirty copy) $f"
      elif [ -n "$(snap_sha "$f")" ]; then
        mkdir -p "$(dirname "$f")"
        if snap_bytes "$f" > "$f.snaprestore" 2>/dev/null; then mv "$f.snaprestore" "$f"; echo "restored (from commit) $f"
        else rm -f "$f.snaprestore"; echo "CANNOT RESTORE $f: not in snapshot copies or commit" >&2; fi
      else rm -f "$f"; echo "deleted (did not exist at snapshot) $f"; fi
    done
    ;;
  verify)
    [ -f "$SNAP/manifest" ] || { echo "no snapshot $TAG" >&2; exit 5; }
    bad=0
    for f in "${PATHS[@]}"; do
      want=$(snap_sha "$f")
      if [ -z "$want" ]; then [ -e "$f" ] && { echo "MISMATCH $f: exists now, absent at snapshot"; bad=1; } || echo "ok (absent both) $f"; continue; fi
      have=$(sha_of "$f")
      [ "$want" = "$have" ] && echo "ok $f" || { echo "MISMATCH $f"; bad=1; }
    done
    exit $bad
    ;;
  *) sed -n '2,18p' "$0"; exit 5;;
esac
