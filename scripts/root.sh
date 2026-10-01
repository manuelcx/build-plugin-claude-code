#!/bin/bash
# root.sh: print the plugin root every build command should use, as an absolute path.
#
#   bash <installed plugin>/scripts/root.sh [--dir </abs/project>]
#
# When <dir>/.build/state.json records an open build with a pinned copy (`plugin`), print that
# copy, so a mid-build plugin update never changes what a running build executes. Otherwise print
# the installed plugin this script belongs to. Callers write the printed path literally into
# every later command, never through a shell variable.
DIR="$PWD"; [ "${1:-}" = "--dir" ] && DIR="$2"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
PINNED=$(python3 - "$DIR/.build/state.json" <<'PY' 2>/dev/null
import json, os, sys
try:
    s = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(0)
p = s.get("plugin", "")
if s.get("status") == "open" and p and os.path.isdir(p):
    print(p)
PY
)
echo "${PINNED:-$HERE}"
