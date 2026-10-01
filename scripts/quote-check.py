#!/usr/bin/env python3
"""quote-check.py: check every sentence a review report quotes against the target it claims to quote.

Usage:
  quote-check.py <report file> <target file or dir>...

Extracts quoted passages from the report (text inside "...", curly quotes, or `> ` blockquote
lines, 25 characters or more) and searches for each in the targets, ignoring case, whitespace
and surrounding punctuation. Prints one line per quote, FOUND, PARTIAL (a run of at least eight
consecutive words is present), or NOT FOUND, then a summary line. Always exits 0: the result is
evidence the judge weighs, never an automatic verdict.
"""
import os
import re
import subprocess
import sys

QUOTED = re.compile(r'"([^"\n]{25,})"|“([^”\n]{25,})”|^\s*>\s?(.{25,})$', re.M)
SKIP_DIRS = {".git", "node_modules", ".build", ".build-archive", ".next", "dist", "build", "coverage"}


def norm(text):
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def target_text(paths):
    chunks = []
    for p in paths:
        if os.path.isfile(p):
            files = [p]
        else:
            try:
                out = subprocess.run(["git", "-C", p, "ls-files", "-co", "--exclude-standard"],
                                     capture_output=True, text=True, check=True).stdout.split("\n")
                files = [os.path.join(p, f) for f in out if f and f.split("/")[0] not in SKIP_DIRS]
            except (subprocess.CalledProcessError, OSError):
                files = [os.path.join(r, f) for r, ds, fs in os.walk(p) for f in fs
                         if not (set(r.split(os.sep)) & SKIP_DIRS)]
        for f in files:
            try:
                if os.path.getsize(f) < 2_000_000:
                    chunks.append(open(f, errors="ignore").read())
            except OSError:
                continue
    return norm("\n".join(chunks))


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(0)
    report = open(sys.argv[1], errors="ignore").read()
    hay = target_text(sys.argv[2:])
    counts = {"FOUND": 0, "PARTIAL": 0, "NOT FOUND": 0}
    seen = set()
    for m in QUOTED.finditer(report):
        q = next(g for g in m.groups() if g).strip()
        n = norm(q)
        if len(n.split()) < 4 or n in seen:
            continue
        seen.add(n)
        if n in hay:
            verdict = "FOUND"
        else:
            words = n.split()
            windows = (" ".join(words[i:i + 8]) for i in range(max(1, len(words) - 7)))
            verdict = "PARTIAL" if len(words) >= 8 and any(w in hay for w in windows) else "NOT FOUND"
        counts[verdict] += 1
        print(f"{verdict}: \"{q[:160]}\"")
    print(f"SUMMARY: {counts['FOUND']} found, {counts['PARTIAL']} partial, {counts['NOT FOUND']} not found")


if __name__ == "__main__":
    main()
