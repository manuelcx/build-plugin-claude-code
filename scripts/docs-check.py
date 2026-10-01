#!/usr/bin/env python3
"""docs-check.py: verify that everything the code docs name actually exists in the repo.

Usage:
  docs-check.py <docs dir> <project dir>

Reads every .html file under the docs dir and takes the text of each <code> element. Each one is
classified and checked:
  - a path (contains a slash and a file extension, or ends with a slash): the file or folder exists;
  - an environment variable (UPPER_SNAKE_CASE, four characters or more): the name appears in a
    project file (code, config, or an .env example);
  - a route (starts with a slash, no extension): the route text appears in a project file;
  - a symbol (an identifier, optionally followed by parentheses): the name appears as a whole
    word in a project file.
Anything else (commands, prose, values) is skipped. Prints MISSING lines with the page they came
from and exits 1 when any reference is missing, else 0.
"""
import html
import os
import re
import subprocess
import sys

CODE = re.compile(r"<code[^>]*>(.*?)</code>", re.S | re.I)
TAG = re.compile(r"<[^>]+>")
ENV = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
PATH = re.compile(r"^[\w.@~-]*(?:/[\w.@\[\]-]+)+/?$")
SYMBOL = re.compile(r"^[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*(?:\(\))?$")


def project_files(root):
    out = subprocess.run(["git", "-C", root, "ls-files", "-co", "--exclude-standard"],
                         capture_output=True, text=True).stdout.split("\n")
    return [f for f in out if f and not f.startswith((".build/", ".build-archive/", "docs/code/"))]


def app_routes(files):
    """Routes implied by app-router and pages folders, with (group) segments removed."""
    routes = set()
    for f in files:
        parts = f.split("/")
        for base in (["app"], ["src", "app"], ["pages"], ["src", "pages"]):
            if parts[:len(base)] == base:
                segs = [p for p in parts[len(base):-1] if not (p.startswith("(") and p.endswith(")"))]
                for i in range(len(segs) + 1):
                    routes.add("/" + "/".join(segs[:i]))
    return routes


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(5)
    docs, root = sys.argv[1], sys.argv[2]
    files = project_files(root)
    blob = []
    for f in files:
        p = os.path.join(root, f)
        try:
            if os.path.getsize(p) < 2_000_000:
                blob.append(open(p, errors="ignore").read())
        except OSError:
            continue
    blob = "\n".join(blob)
    listed = set(files) | {os.path.dirname(f) + "/" for f in files}
    routes = app_routes(files)
    missing, checked = [], 0
    for dirpath, _, names in os.walk(docs):
        for name in names:
            if not name.endswith(".html"):
                continue
            page = os.path.join(dirpath, name)
            for raw in CODE.findall(open(page, errors="ignore").read()):
                ref = html.unescape(TAG.sub("", raw)).strip()
                if not ref or " " in ref or len(ref) > 200:
                    continue
                if ENV.match(ref) and len(ref) >= 4:
                    ok = re.search(rf"\b{re.escape(ref)}\b", blob) is not None
                elif ref.startswith("/") and "." not in ref.rsplit("/", 1)[-1]:
                    ok = ref in blob or ref.rstrip("/") in routes
                elif PATH.match(ref) and ("." in ref.rsplit("/", 1)[-1] or ref.endswith("/")):
                    rel = ref.lstrip("./")
                    ok = rel in listed or os.path.exists(os.path.join(root, rel)) or any(f.endswith(rel) for f in files)
                elif SYMBOL.match(ref) and len(ref) > 2 and re.search(r"[(._]|[a-z][A-Z]", ref):
                    word = ref.rstrip("()").split(".")[-1]
                    ok = re.search(rf"\b{re.escape(word)}\b", blob) is not None
                else:
                    continue
                checked += 1
                if not ok:
                    missing.append((os.path.relpath(page, docs), ref))
    for page, ref in missing:
        print(f"MISSING: {ref}  (in {page})")
    print(f"docs check: {checked - len(missing)} of {checked} references found")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
