#!/usr/bin/env python3
"""ledger.py: the build ledger and state file, written only through this tool.

All commands take --dir </abs/project> (default cwd) and act on <dir>/.build/ledger.md and
<dir>/.build/state.json. See reference/ledger.md for the semantics of each command.
"""
import argparse
import datetime
import json
import os
import sys

ROW_HEADER = "| # | Trigger | Engine | Raw | Verified | Blocking | Tests | Action |\n|---|---|---|---|---|---|---|---|\n"


def now():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


class Ledger:
    def __init__(self, d):
        self.dir = os.path.join(d, ".build")
        self.md = os.path.join(self.dir, "ledger.md")
        self.st = os.path.join(self.dir, "state.json")

    def state(self):
        return json.load(open(self.st)) if os.path.exists(self.st) else None

    def save(self, s):
        json.dump(s, open(self.st, "w"), indent=2)

    def append(self, text):
        with open(self.md, "a") as f:
            f.write(text)

    def read(self):
        return open(self.md).read() if os.path.exists(self.md) else ""

    def write(self, text):
        open(self.md, "w").write(text)

    def insert_under(self, heading, text, create=True):
        """Append text at the end of the section that starts with `heading` (exact line).
        A heading given without its `## ` prefix is normalized. With create=False a missing
        heading is an error, never a silent new section."""
        if not heading.startswith("#"):
            heading = "## " + heading
        body = self.read()
        lines = body.split("\n")
        try:
            i = lines.index(heading)
        except ValueError:
            if not create:
                sys.exit(f"heading not found in ledger: {heading!r} (open the section first)")
            self.append(f"\n{heading}\n\n{text}")
            return
        j = i + 1
        while j < len(lines) and not lines[j].startswith("## "):
            j += 1
        while j > i + 1 and lines[j - 1].strip() == "":
            j -= 1
        lines[j:j] = text.rstrip("\n").split("\n")
        self.write("\n".join(lines))

    def item_heading(self, n):
        for line in self.read().split("\n"):
            if line.startswith(f"## Item {n} --"):
                return line
        return None


def cmd_init(L, a):
    if os.path.exists(L.st):
        prev = L.state()
        if prev.get("status") != "closed":
            sys.exit(f"a build is still open here ({prev.get('build')}, status {prev.get('status', 'open')}); "
                     "resume it with `/build:build resume`, or run `ledger.py close --abandon` to archive it as abandoned")
        arch = os.path.join(a.dir, ".build-archive", f"{prev.get('build')}-{prev.get('closed', 'closed').replace(':', '')}")
        os.makedirs(os.path.dirname(arch), exist_ok=True)
        os.rename(L.dir, arch)
        print(f"archived closed build to {arch}")
    os.makedirs(L.dir, exist_ok=True)
    s = {"build": a.name, "spec": a.spec, "started": now(), "commit": a.commit, "status": "open",
         "roles": {"executor": a.executor, "frontend": a.frontend, "reviewer": a.reviewer, "consult": a.consult},
         "preflight": a.preflight or "not recorded", "items": [], "current": {},
         "gates": {"backend": "pending", "e2e": "pending", "docker": "pending", "whole_build": "pending"},
         "violations": []}
    L.save(s)
    L.write(f"# Build ledger: {a.name}\n\nStarted {s['started']}. Spec: `{a.spec}`. Pre-build commit `{a.commit}`.\n\n"
            f"## Roles\n\n- executor: `{a.executor}`\n- frontend: `{a.frontend}`\n- reviewer: `{a.reviewer}`\n- consult: `{a.consult}`\n"
            f"- pre-flight: {s['preflight']}\n\n## Item manifest\n\n## Accepted residuals\n\n## Triage backlog\n\n## Discipline violations\n")
    exclude = os.path.join(a.dir, ".git", "info", "exclude")
    if os.path.isdir(os.path.dirname(exclude)):
        cur = open(exclude).read() if os.path.exists(exclude) else ""
        if ".build/" not in cur:
            open(exclude, "a").write("\n.build/\n")
    print(f"initialized {L.md}")


def cmd_manifest(L, a):
    s = L.state()
    items = json.load(open(a.items))
    lines = []
    for it in items:
        lines.append(f"{it['n']}. **{it['name']}**")
        for u in it.get("units", []):
            lines.append(f"   - spec unit (verbatim): {u}")
        s["items"].append({"n": it["n"], "name": it["name"], "status": "pending", "cycles": 0})
    if a.whole_build_unit:
        lines.append(f"- spec unit mapped to the whole-build review gate (never built): {a.whole_build_unit}")
    L.insert_under("## Item manifest", "\n".join(lines) + "\n")
    L.save(s)
    print(f"manifest: {len(items)} items")


def cmd_protected(L, a):
    text = open(a.file).read().strip()
    L.insert_under("## Item manifest", "\n**Must not regress (verbatim, the single copy):**\n\n" + text + "\n")
    s = L.state(); s["protected"] = a.file; L.save(s)
    print("protected surfaces recorded")


def cmd_item_open(L, a):
    s = L.state()
    name = a.name
    for it in s["items"]:
        if it["n"] == a.item:
            name = name or it["name"]
            it.update({"status": "open", "surface": a.surface, "greenfield": a.greenfield, "brief": a.brief, "name": name})
    if not name:
        sys.exit(f"item {a.item} is not in the manifest; run `ledger.py manifest` first or pass --name")
    s["current"] = {"item": a.item, "phase": "build", "cycle": 0, "brief": a.brief, "snapshot": f"item-{a.item}"}
    L.save(s)
    L.append(f"\n## Item {a.item} -- {name} -- surface: {a.surface} -- greenfield: {a.greenfield} -- brief: {a.brief}\n\n{ROW_HEADER}")
    print(f"item {a.item} opened")


def cmd_row(L, a):
    s = L.state()
    n = a.item
    if a.heading and not n:
        _point_current_at_heading(s, a.heading)
    if a.kind == "cycle":
        s["current"]["cycle"] = s["current"].get("cycle", 0) + 1 if not a.cycle else a.cycle
        num = s["current"]["cycle"]
        for it in s["items"]:
            if it["n"] == n:
                it["cycles"] = it.get("cycles", 0) + 1
    else:
        num = "-"
    row = f"| {num} | {a.trigger} | {a.engine} | {a.raw} | {a.verified} | {a.blocking} | {a.tests} | {a.action} |\n"
    heading = a.heading or L.item_heading(n)
    if heading is None:
        sys.exit(f"no heading for item {n}; open it first or pass --heading")
    L.insert_under(heading, row, create=False)
    L.save(s)
    print(row.strip())


def _point_current_at_heading(s, heading):
    """A row on a non-item heading (a gate section, the whole-build review) counts cycles for that section."""
    title = heading.lstrip("#").strip()
    if s.get("current", {}).get("section") != title:
        s["current"] = {"section": title, "phase": "review", "cycle": 0}


def cmd_close(L, a):
    s = L.state()
    s["status"] = "closed"
    s["closed"] = now()
    if a.abandon:
        s["status"] = "closed"
        s["abandoned"] = True
        s["violations"].append({"at": now(), "text": "build abandoned before its final report"})
    L.save(s)
    print(f"build {s['build']} marked closed{' (abandoned)' if a.abandon else ''}")


def cmd_subheading(L, a):
    """A redesign restarts the cycle count under its own sub-heading inside the item."""
    s = L.state()
    s["current"]["cycle"] = 0
    L.save(s)
    heading = L.item_heading(a.item)
    L.insert_under(heading, f"\n### Item {a.item} {a.title}\n\n{ROW_HEADER}", create=False)
    print("sub-heading added; cycle count restarts")


def cmd_section(L, a):
    """Open a standalone section with a row table (Backend gate, E2E gate, Whole-build review)."""
    L.append(f"\n## {a.title}\n\n{ROW_HEADER}")
    s = L.state(); s["current"] = {"section": a.title, "phase": "review", "cycle": 0}; L.save(s)
    print(f"section {a.title} opened")


def cmd_residual(L, a):
    L.insert_under("## Accepted residuals", f"- Item {a.item}: {a.text}\n")
    print("residual recorded")


def cmd_backlog(L, a):
    L.insert_under("## Triage backlog", f"- Item {a.item}: {a.text}\n")
    print("backlog recorded")


def cmd_violation(L, a):
    s = L.state(); s["violations"].append({"at": now(), "text": a.text}); L.save(s)
    L.insert_under("## Discipline violations", f"- {now()}: {a.text}\n")
    print("violation recorded")


def cmd_item_close(L, a):
    s = L.state()
    for it in s["items"]:
        if it["n"] == a.item:
            it.update({"status": "closed", "critique": a.critique, "closed": now()})
            if a.cycles:
                it["cycles"] = a.cycles
    s["current"] = {"item": a.item, "phase": "closed"}
    L.save(s)
    print(f"item {a.item} closed")


def cmd_state(L, a):
    s = L.state()
    for kv in a.set or []:
        k, v = kv.split("=", 1)
        if k.startswith("gates."):
            s["gates"][k[6:]] = v
        else:
            s.setdefault("current", {})[k] = int(v) if v.isdigit() else v
    L.save(s)
    print(json.dumps(s["current"]))


def cmd_show(L, a):
    s = L.state()
    if not s:
        print("no build in progress"); return
    print(json.dumps({k: s.get(k) for k in ("build", "status", "spec", "roles", "gates", "current")}, indent=2))
    print("items:", ", ".join(f"{i['n']}:{i['status']}({i.get('cycles', 0)})" for i in s["items"]))
    cur = s.get("current", {}).get("item")
    if cur:
        body = L.read(); h = L.item_heading(cur)
        if h:
            i = body.index(h); j = body.find("\n## ", i + 1)
            print(body[i:j if j > 0 else None])


def cmd_report(L, a):
    s = L.state()
    out = ["\n## Final report\n", f"Build `{s['build']}` finished {now()}. Roles: " +
           ", ".join(f"{k}=`{v}`" for k, v in s["roles"].items()) + ".\n"]
    out.append("| Item | Status | Cycles | Surface | Greenfield | Critique |\n|---|---|---|---|---|---|")
    for it in s["items"]:
        out.append(f"| {it['n']} {it['name']} | {it['status']} | {it.get('cycles', 0)} | {it.get('surface', '?')} | {it.get('greenfield', '?')} | {it.get('critique', 'n/a')} |")
    out.append("\nGates: " + ", ".join(f"{k}={v}" for k, v in s["gates"].items()))
    missing = [it["n"] for it in s["items"] if it["status"] != "closed"]
    viol = list(s.get("violations", []))
    if missing:
        viol.append({"at": now(), "text": f"items without a closing row: {missing}"})
    for k, v in s["gates"].items():
        if v == "pending":
            viol.append({"at": now(), "text": f"gate left open: {k}"})
    out.append("\nDiscipline check: " + ("clean" if not viol else "\n".join(f"- DISCIPLINE VIOLATION: {v['text']}" for v in viol)))
    body = L.read()
    for sec in ("## Accepted residuals", "## Triage backlog"):
        i = body.find(sec)
        if i >= 0:
            j = body.find("\n## ", i + 1)
            out.append("\n" + body[i:j if j > 0 else None].rstrip())
    text = "\n".join(out) + "\n"
    L.append(text)
    s["status"] = "closed"
    s["closed"] = now()
    L.save(s)
    print(text)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dir", default=os.getcwd())
    sub = p.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("init"); x.add_argument("--name", required=True); x.add_argument("--spec", required=True); x.add_argument("--commit", required=True)
    for r in ("executor", "frontend", "reviewer", "consult"):
        x.add_argument(f"--{r}", required=True)
    x.add_argument("--preflight")
    x = sub.add_parser("manifest"); x.add_argument("--items", required=True); x.add_argument("--whole-build-unit")
    x = sub.add_parser("protected"); x.add_argument("--file", required=True)
    x = sub.add_parser("item-open"); x.add_argument("--item", type=int, required=True); x.add_argument("--name"); x.add_argument("--surface", required=True, choices=["backend", "frontend", "mixed"]); x.add_argument("--greenfield", required=True, choices=["yes", "no"]); x.add_argument("--brief", required=True)
    x = sub.add_parser("row"); x.add_argument("--item", type=int); x.add_argument("--heading"); x.add_argument("--kind", required=True, choices=["cycle", "gate", "consult"]); x.add_argument("--cycle", type=int)
    for f in ("trigger", "engine", "raw", "verified", "blocking", "tests", "action"):
        x.add_argument(f"--{f}", required=True)
    x = sub.add_parser("subheading"); x.add_argument("--item", type=int, required=True); x.add_argument("--title", required=True)
    x = sub.add_parser("section"); x.add_argument("--title", required=True)
    x = sub.add_parser("residual"); x.add_argument("--item", required=True); x.add_argument("--text", required=True)
    x = sub.add_parser("backlog"); x.add_argument("--item", required=True); x.add_argument("--text", required=True)
    x = sub.add_parser("violation"); x.add_argument("--text", required=True)
    x = sub.add_parser("item-close"); x.add_argument("--item", type=int, required=True); x.add_argument("--cycles", type=int); x.add_argument("--critique", default="n/a")
    x = sub.add_parser("state"); x.add_argument("--set", nargs="*")
    x = sub.add_parser("close"); x.add_argument("--abandon", action="store_true")
    sub.add_parser("show")
    sub.add_parser("report")
    a = p.parse_args()
    L = Ledger(a.dir)
    if a.cmd != "init" and not os.path.exists(L.st):
        sys.exit("no .build/state.json here; run `ledger.py init` first")
    globals()["cmd_" + a.cmd.replace("-", "_")](L, a)


if __name__ == "__main__":
    main()
