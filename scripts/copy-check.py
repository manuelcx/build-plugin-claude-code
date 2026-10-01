#!/usr/bin/env python3
"""copy-check.py: confirm every approved copy string from a spec is present in the code verbatim.

Usage:
  copy-check.py <spec file> <project dir>

Reads only the spec section whose heading contains "Verbatim copy" (any heading level). Each
quoted string ("...", curly quotes, or a `> ` blockquote line) and each bullet line in that
section is one approved string. Every string must appear byte-for-byte (whitespace runs
normalized) in at least one tracked or untracked non-ignored project file outside `.build/` and
the spec itself. Prints MISSING lines and exits 1 when any string is absent; exits 0 when all
are present or when the spec has no such section.
"""
import html
import os
import re
import subprocess
import sys

HEADING = re.compile(r"^(#+)\s+.*verbatim copy.*$", re.I | re.M)
STRING = re.compile(r'"([^"\n]+)"|“([^”\n]+)”|^\s*>\s?(.+)$|^\s*[-*]\s+(.+)$', re.M)


def ws(s):
    return " ".join(s.split())


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(5)
    spec, root = sys.argv[1], sys.argv[2]
    text = open(spec, errors="ignore").read()
    h = HEADING.search(text)
    if not h:
        print("no Verbatim copy section in the spec; nothing to check")
        return
    level = len(h.group(1))
    rest = text[h.end():]
    end = re.search(rf"^#{{1,{level}}}\s", rest, re.M)
    section = rest[:end.start()] if end else rest
    strings = []
    for m in STRING.finditer(section):
        s = next(g for g in m.groups() if g).strip().strip('"“”')
        if s and s not in strings:
            strings.append(s)
    files = subprocess.run(["git", "-C", root, "ls-files", "-co", "--exclude-standard"],
                           capture_output=True, text=True).stdout.split("\n")
    spec_abs = os.path.abspath(spec)
    hay = []
    for f in files:
        p = os.path.join(root, f)
        if not f or f.startswith((".build/", ".build-archive/")) or os.path.abspath(p) == spec_abs:
            continue
        try:
            if os.path.getsize(p) < 2_000_000:
                hay.append(ws(html.unescape(open(p, errors="ignore").read())))
        except OSError:
            continue
    blob = "\n".join(hay)
    missing = [s for s in strings if ws(s) not in blob]
    for s in missing:
        print(f"MISSING: {s}")
    print(f"copy check: {len(strings) - len(missing)} of {len(strings)} approved strings present")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
