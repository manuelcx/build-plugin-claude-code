#!/usr/bin/env python3
"""ledger.py: the build ledger and state file, written only through this tool.

All commands take --dir </abs/project> (default cwd) and act on <dir>/.build/ledger.md and
<dir>/.build/state.json. See reference/ledger.md for the semantics of each command. The final
report and the discipline check live in ledger_report.py next to this file.
"""
import argparse
import datetime
import json
import os
import shutil
import sys

ROW_HEADER = "| # | Trigger | Engine | Raw | Verified | Blocking | Tests | Action |\n|---|---|---|---|---|---|---|---|\n"
ROLES = ("executor", "frontend", "reviewer", "consult", "judge", "docs")
# Files that belong to the session, not to one build: they survive the archive step of `init`.
CARRY = ("owner-session", "queue", "preflight.txt")
PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def now():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


class Ledger:
    def __init__(self, d):
        self.root = d
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
        lines = self.read().split("\n")
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
    carried = {f: open(os.path.join(L.dir, f)).read() for f in CARRY if os.path.exists(os.path.join(L.dir, f))}
    try:
        os.remove(os.path.join(L.dir, "stop-record"))   # a new build starts unstopped
    except OSError:
        pass
    arch = None
    if os.path.exists(L.st):
        prev = L.state()
        if prev.get("status") != "closed":
            sys.exit(f"a build is still open here ({prev.get('build')}, status {prev.get('status', 'open')}); "
                     "resume it with `/build:build resume`, or run `ledger.py close --abandon` to archive it as abandoned")
        arch = os.path.join(a.dir, ".build-archive", f"{prev.get('build')}-{prev.get('closed', 'closed').replace(':', '')}")
        os.makedirs(os.path.dirname(arch), exist_ok=True)
        os.rename(L.dir, arch)
        print(f"archived closed build to {arch}")
    for sub in ("briefs", "runs", "gates"):
        os.makedirs(os.path.join(L.dir, sub), exist_ok=True)
    for f, body in carried.items():
        if f != "preflight.txt":   # read once into the state below; never reused by a later build
            open(os.path.join(L.dir, f), "w").write(body)
    pin = os.path.join(L.dir, "plugin")
    src = PLUGIN
    if os.path.abspath(PLUGIN).startswith(os.path.abspath(L.dir) + os.sep) and arch:
        # run from the previous build's pinned copy, which the archive step just moved
        src = os.path.join(arch, os.path.relpath(PLUGIN, L.dir))
    for part in ("scripts", "reference", "skills"):
        if os.path.isdir(os.path.join(src, part)):
            shutil.copytree(os.path.join(src, part), os.path.join(pin, part), dirs_exist_ok=True)
    preflight = a.preflight or carried.get("preflight.txt", "").strip().replace("\n", "; ") or "not recorded"
    roles = {r: getattr(a, r) for r in ROLES}
    s = {"build": a.name, "spec": a.spec, "started": now(), "commit": a.commit, "status": "open",
         "plugin": os.path.abspath(pin), "roles": roles, "preflight": preflight, "items": [], "current": {},
         "gates": {"frontend": "pending", "backend": "pending", "e2e": "pending", "docker": "pending",
                   "whole_build": "pending", "docs": "n/a" if roles["docs"] == "none" else "pending"},
         "rows": [], "violations": [], "notes": [], "residuals": [], "backlog": [], "live": [],
         "unbuilt": [], "deviations": [], "backoffs": []}
    L.save(s)
    L.write(f"# Build ledger: {a.name}\n\nStarted {s['started']}. Spec: `{a.spec}`. Pre-build commit `{a.commit}`.\n"
            f"Pinned plugin copy: `{s['plugin']}`.\n\n## Roles\n\n"
            + "".join(f"- {r}: `{v}`\n" for r, v in roles.items())
            + f"- pre-flight: {preflight}\n\n## Item manifest\n\n## Accepted residuals\n\n## Triage backlog\n\n"
              "## Discipline violations\n\n## Notes\n")
    exclude = os.path.join(a.dir, ".git", "info", "exclude")
    if os.path.isdir(os.path.dirname(exclude)):
        cur = open(exclude).read() if os.path.exists(exclude) else ""
        for line in (".build/", ".build-archive/"):
            if line not in cur.split("\n"):
                open(exclude, "a").write(f"\n{line}\n")
    print(f"initialized {L.md}; pinned plugin copy at {s['plugin']}")


def _manifest_lines(it):
    lines = [f"{it['n']}. **{it['name']}**"]
    lines += [f"   - spec unit (verbatim): {u}" for u in it.get("units", [])]
    return lines


def cmd_manifest(L, a):
    s = L.state()
    items = json.load(open(a.items))
    lines = []
    for it in items:
        lines += _manifest_lines(it)
        s["items"].append({"n": it["n"], "name": it["name"], "status": "pending", "cycles": 0})
    if a.whole_build_unit:
        lines.append(f"- spec unit mapped to the whole-build review gate (never built): {a.whole_build_unit}")
    L.insert_under("## Item manifest", "\n".join(lines) + "\n")
    L.save(s)
    print(f"manifest: {len(items)} items")


def cmd_item_add(L, a):
    s = L.state()
    if any(it["n"] == a.item for it in s["items"]):
        sys.exit(f"item {a.item} already exists")
    it = {"n": a.item, "name": a.name, "units": a.unit or []}
    s["items"].append({"n": a.item, "name": a.name, "status": "pending", "cycles": 0, "added": now()})
    L.insert_under("## Item manifest", "\n".join(_manifest_lines(it)) + f"\n   - added mid-build: {a.reason}\n")
    L.save(s)
    print(f"item {a.item} added")


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
        sys.exit(f"item {a.item} is not in the manifest; run `ledger.py manifest` or `item-add` first")
    s["current"] = {"item": a.item, "phase": "build", "cycle": 0, "brief": a.brief, "snapshot": f"item-{a.item}"}
    L.save(s)
    L.append(f"\n## Item {a.item} -- {name} -- surface: {a.surface} -- greenfield: {a.greenfield} -- brief: {a.brief}\n\n{ROW_HEADER}")
    print(f"item {a.item} opened")


def cmd_row(L, a):
    s = L.state()
    cur = s.get("current", {})
    n = a.item if a.item is not None else (None if a.heading else cur.get("item"))
    if a.heading and a.item is None:
        _point_current_at_heading(s, a.heading)
    heading = a.heading or (L.item_heading(n) if n is not None else None)
    if heading is None and a.item is None and cur.get("section"):
        heading = "## " + cur["section"]
    if heading is None:
        sys.exit(f"no heading for item {n}; open it first or pass --heading")
    if a.kind == "cycle":
        if not a.findings or not os.path.exists(a.findings):
            sys.exit("a cycle row needs --findings <path> to an existing findings file (run /build:review for this cycle)")
        prior = sum(1 for r in s["rows"] if r["heading"] == heading and r["kind"] == "cycle")
        num = prior + 1
        s["current"]["cycle"] = num
        for it in s["items"]:
            if it["n"] == n:
                it["cycles"] = num
    else:
        num = "-"
    row = f"| {num} | {a.trigger} | {a.engine} | {a.raw} | {a.verified} | {a.blocking} | {a.tests} | {a.action} |\n"
    L.insert_under(heading, row, create=False)
    s["rows"].append({"heading": heading, "kind": a.kind, "engine": a.engine, "trigger": a.trigger, "at": now(),
                      "findings": a.findings})
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
        s["abandoned"] = True
        s["violations"].append({"at": now(), "text": "build abandoned before its final report"})
    L.save(s)
    print(f"build {s['build']} marked closed{' (abandoned)' if a.abandon else ''}")


def cmd_subheading(L, a):
    """A redesign restarts the cycle count under its own sub-heading inside the item."""
    s = L.state()
    s["current"]["cycle"] = 0
    heading = L.item_heading(a.item)
    title = f"### Item {a.item} {a.title}"
    L.insert_under(heading, f"\n{title}\n\n{ROW_HEADER}", create=False)
    # cycle numbers restart: earlier cycle rows on this item stop counting toward the new numbering
    for r in s["rows"]:
        if r["heading"] == heading and r["kind"] == "cycle":
            r["kind"] = "cycle-before-redesign"
    L.save(s)
    print("sub-heading added; cycle count restarts")


def cmd_section(L, a):
    """Open a standalone section with a row table (Backend gate, E2E gate, Whole-build review)."""
    L.append(f"\n## {a.title}\n\n{ROW_HEADER}")
    s = L.state(); s["current"] = {"section": a.title, "phase": "review", "cycle": 0}; L.save(s)
    print(f"section {a.title} opened")


def _listed(L, a, key, heading):
    s = L.state()
    who = f"Item {a.item}" if a.item else "Whole build"
    s[key].append({"item": a.item, "text": a.text, "at": now()})
    L.save(s)
    L.insert_under(heading, f"- {who}: {a.text}\n")
    print(f"{key[:-1] if key.endswith('s') else key} recorded")


def cmd_residual(L, a):
    _listed(L, a, "residuals", "## Accepted residuals")


def cmd_backlog(L, a):
    _listed(L, a, "backlog", "## Triage backlog")


def cmd_violation(L, a):
    s = L.state(); s["violations"].append({"at": now(), "text": a.text}); L.save(s)
    L.insert_under("## Discipline violations", f"- {now()}: {a.text}\n")
    print("violation recorded")


def cmd_note(L, a):
    s = L.state(); s["notes"].append({"at": now(), "text": a.text}); L.save(s)
    L.insert_under("## Notes", f"- {now()}: {a.text}\n")
    print("note recorded")


def _report_list(key, label):
    def cmd(L, a):
        s = L.state(); s[key].append({"at": now(), "text": a.text}); L.save(s)
        print(f"{label} recorded")
    return cmd


cmd_live = _report_list("live", "make-it-live step")
cmd_unbuilt = _report_list("unbuilt", "unbuilt requirement")
cmd_deviation = _report_list("deviations", "spec deviation")


def cmd_backoff(L, a):
    s = L.state(); s["backoffs"].append({"at": now(), "minutes": a.minutes, "reason": a.reason}); L.save(s)
    print(f"backoff of {a.minutes} minutes recorded")


def cmd_stop(L, a):
    """A permitted stop (unattended contract): the stop guard lets the turn end and later prompts
    get one line pointing at the report; only `/build:build resume` continues. Works before `init`
    too (a pre-flight failure), when only the stop record is written."""
    os.makedirs(L.dir, exist_ok=True)
    open(os.path.join(L.dir, "stop-record"), "w").write(f"{now()} {a.reason}\n")
    s = L.state()
    if s and s.get("status") == "open":
        s["current"]["phase"] = "stopped"
        s["stopped"] = {"at": now(), "reason": a.reason}
        L.save(s)
        L.insert_under("## Notes", f"- {now()}: PERMITTED STOP: {a.reason}. Resume with `/build:build resume`.\n")
    print(f"permitted stop recorded: {a.reason}")


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
        if k == "cycle":
            print("ignored cycle=: cycle numbers come from the rows, never from state", file=sys.stderr)
        elif k.startswith("gates."):
            s["gates"][k[6:]] = v
        else:
            s.setdefault("current", {})[k] = int(v) if v.isdigit() else v
    L.save(s)
    print(json.dumps(s["current"]))


def cmd_queue(L, a):
    q = os.path.join(L.dir, "queue")
    os.makedirs(L.dir, exist_ok=True)
    specs = [x for x in (open(q).read().split("\n") if os.path.exists(q) else []) if x.strip()]
    if a.set:
        specs = a.set
    elif a.pop:
        specs = specs[1:]
    open(q, "w").write("\n".join(specs) + ("\n" if specs else ""))
    print("queue:", ", ".join(specs) if specs else "empty")


def cmd_show(L, a):
    s = L.state()
    if not s:
        print("no build in progress"); return
    print(json.dumps({k: s.get(k) for k in ("build", "status", "spec", "plugin", "roles", "gates", "current")}, indent=2))
    print("items:", ", ".join(f"{i['n']}:{i['status']}({i.get('cycles', 0)})" for i in s["items"]))
    cur = s.get("current", {}).get("item")
    if cur:
        body = L.read(); h = L.item_heading(cur)
        if h:
            i = body.index(h); j = body.find("\n## ", i + 1)
            print(body[i:j if j > 0 else None])


def cmd_status(L, a):
    s = L.state()
    if not s:
        print("no build in progress"); return
    items = s["items"]; done = sum(1 for i in items if i["status"] == "closed")
    cur = s.get("current", {})
    where = f"item {cur['item']}" if cur.get("item") else cur.get("section", "setup")
    heading = L.item_heading(cur["item"]) if cur.get("item") else (f"## {cur['section']}" if cur.get("section") else None)
    fixes = sum(1 for r in s["rows"] if r["heading"] == heading and r["kind"] == "fix")
    start = datetime.datetime.fromisoformat(s["started"])
    mins = int((datetime.datetime.now() - start).total_seconds() // 60)
    print(f"{s['build']}: {done} of {len(items)} items closed; now {where}, phase {cur.get('phase', '?')}, "
          f"{fixes} fix rounds on it; {mins // 60}h{mins % 60:02d}m elapsed; status {s['status']}")


def cmd_report(L, a):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ledger_report
    ledger_report.render(L)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dir", default=os.getcwd())
    sub = p.add_subparsers(dest="cmd", required=True)
    x = sub.add_parser("init"); x.add_argument("--name", required=True); x.add_argument("--spec", required=True); x.add_argument("--commit", required=True)
    for r in ROLES:
        x.add_argument(f"--{r}", required=r not in ("judge", "docs"), default={"judge": "claude:opus:medium", "docs": "agy"}.get(r))
    x.add_argument("--preflight")
    x = sub.add_parser("manifest"); x.add_argument("--items", required=True); x.add_argument("--whole-build-unit")
    x = sub.add_parser("item-add"); x.add_argument("--item", type=int, required=True); x.add_argument("--name", required=True); x.add_argument("--unit", action="append"); x.add_argument("--reason", required=True)
    x = sub.add_parser("protected"); x.add_argument("--file", required=True)
    x = sub.add_parser("item-open"); x.add_argument("--item", type=int, required=True); x.add_argument("--name"); x.add_argument("--surface", required=True, choices=["backend", "frontend", "mixed"]); x.add_argument("--greenfield", required=True, choices=["yes", "no"]); x.add_argument("--brief", required=True)
    x = sub.add_parser("row"); x.add_argument("--item", type=int); x.add_argument("--heading"); x.add_argument("--kind", required=True, choices=["cycle", "gate", "consult", "fix", "note"]); x.add_argument("--findings")
    for f in ("trigger", "engine", "raw", "verified", "blocking", "tests", "action"):
        x.add_argument(f"--{f}", required=f in ("trigger", "engine", "action"), default="n/a")
    x = sub.add_parser("subheading"); x.add_argument("--item", type=int, required=True); x.add_argument("--title", required=True)
    x = sub.add_parser("section"); x.add_argument("--title", required=True)
    for name in ("residual", "backlog"):
        x = sub.add_parser(name); x.add_argument("--item"); x.add_argument("--text", required=True)
    for name in ("violation", "note", "live", "unbuilt", "deviation"):
        x = sub.add_parser(name); x.add_argument("--text", required=True)
    x = sub.add_parser("backoff"); x.add_argument("--minutes", type=int, required=True); x.add_argument("--reason", required=True)
    x = sub.add_parser("stop"); x.add_argument("--reason", required=True)
    x = sub.add_parser("item-close"); x.add_argument("--item", type=int, required=True); x.add_argument("--cycles", type=int); x.add_argument("--critique", default="n/a")
    x = sub.add_parser("state"); x.add_argument("--set", nargs="*")
    x = sub.add_parser("queue"); x.add_argument("--set", nargs="+"); x.add_argument("--pop", action="store_true")
    x = sub.add_parser("close"); x.add_argument("--abandon", action="store_true")
    for name in ("show", "status", "report"):
        sub.add_parser(name)
    a = p.parse_args()
    L = Ledger(a.dir)
    if a.cmd not in ("init", "queue", "status", "show", "stop") and not os.path.exists(L.st):
        sys.exit("no .build/state.json here; run `ledger.py init` first")
    globals()["cmd_" + a.cmd.replace("-", "_")](L, a)


if __name__ == "__main__":
    main()
