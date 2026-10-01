"""ledger_report.py: render the final report and run the mechanical discipline check.

Called by `ledger.py report`. The report always renders and always closes the build: a failed
discipline check marks its line failed, it never refuses to close (a build that cannot close
would block the next `init`). Rendering replaces any earlier final report in the ledger.
"""
import datetime
import json
import os
import shutil
import subprocess

GATE_ENGINES = {"scope-gate", "structure-gate", "frontend-gate", "backend-gate", "e2e-gate",
                "docker-gate", "docs", "critique", "audit"}


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def _norm(triple):
    """(family, model) with the effort dropped, lowercased; `agy` alone has an empty model."""
    parts = (triple or "").strip().strip("`").split(":")
    return parts[0].lower(), (parts[1].strip().lower() if len(parts) > 1 else "")


def _same(a, b):
    fa, ma = _norm(a)
    fb, mb = _norm(b)
    return fa == fb and (not ma or not mb or ma == mb)


def discipline(s):
    """Violations: recorded ones, open items, open gates, and every row whose engine is not the
    role that row's kind belongs to (a substitution)."""
    out = [v["text"] for v in s.get("violations", [])]
    roles = s["roles"]
    for r in s.get("rows", []):
        kind, eng, heading = r["kind"], r["engine"], r["heading"]
        if kind in ("gate", "note", "restart") or eng.strip().lower() in GATE_ENGINES:
            continue
        if kind in ("cycle", "cycle-before-redesign"):
            allowed = [roles["reviewer"]]
            if "Whole-build" in heading:
                allowed += [roles["consult"], roles.get("judge", "")]
        elif kind == "consult":
            allowed = [roles["consult"]]
        elif kind == "fix":
            allowed = [roles["executor"], roles["frontend"]]
        else:
            continue
        if not any(_same(eng, x) for x in allowed if x):
            where = heading.lstrip("# ").split(" -- surface")[0]
            out.append(f"engine substitution: `{eng}` ran a {kind} row under {where}; locked: {', '.join(allowed)}")
    missing = [it["n"] for it in s["items"] if it["status"] != "closed"]
    if missing:
        out.append(f"items without a closing row: {missing}")
    for k, v in s["gates"].items():
        if v == "pending" and k != "docs":
            out.append(f"gate left open: {k}")
    return out


def gap_notes(L):
    """Gaps over 15 minutes between one run ending and the next starting, from the run files."""
    runs = os.path.join(L.dir, "runs")
    if not os.path.isdir(runs):
        return []
    spans = []
    for name in os.listdir(runs):
        if name.endswith((".jsonl", ".findings.md")):
            st = os.stat(os.path.join(runs, name))
            spans.append((getattr(st, "st_birthtime", st.st_mtime), st.st_mtime, name))
    spans.sort()
    s = L.state()
    backoffs = [datetime.datetime.fromisoformat(b["at"]).timestamp() for b in s.get("backoffs", [])]
    notes = []
    for (_, end, a), (start, _, b) in zip(spans, spans[1:]):
        gap = start - end
        if gap > 900 and not any(end - 60 <= t <= start for t in backoffs):
            notes.append(f"{int(gap // 60)} minutes idle between {a} and {b}")
    return notes


def main_commits(L, s):
    """Commits main gained since the pre-build commit on files this build touched."""
    snap = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshot.sh")
    try:
        changed = subprocess.run([snap, "changed", "pre-build", "--dir", L.root], capture_output=True, text=True).stdout
        files = [line.split("\t", 1)[1] for line in changed.splitlines() if "\t" in line]
        if not files:
            return []
        for ref in ("main", "origin/main"):
            r = subprocess.run(["git", "-C", L.root, "log", "--oneline", f"{s['commit']}..{ref}", "--", *files],
                               capture_output=True, text=True)
            if r.returncode == 0:
                return [l for l in r.stdout.splitlines() if l.strip()]
    except OSError:
        pass
    return []


def numbered(title, entries, empty):
    lines = [f"\n### {title}\n"]
    if not entries:
        return lines + [empty]
    for i, e in enumerate(entries, 1):
        who = f"Item {e['item']}" if e.get("item") else ("Whole build" if "item" in e else "")
        lines.append(f"{i}. {who + ': ' if who else ''}{e['text']}")
    return lines


def render(L):
    s = L.state()
    viol = discipline(s)
    notes = list(s.get("notes", [])) + [{"at": _now(), "text": g} for g in gap_notes(L)]
    items = s["items"]
    closed = sum(1 for i in items if i["status"] == "closed")
    bad_gates = {k: v for k, v in s["gates"].items() if v not in ("clean", "n/a") and k != "docs"}
    browser = s["gates"].get("frontend", "")
    if not viol and not bad_gates and closed == len(items) and not s.get("unbuilt"):
        verdict = f"Build `{s['build']}` is done: all {len(items)} items closed and every gate clean."
    else:
        why = []
        if closed != len(items):
            why.append(f"{len(items) - closed} of {len(items)} items not closed")
        if bad_gates:
            why.append("gates not clean: " + ", ".join(f"{k}={v}" for k, v in bad_gates.items()))
        if s.get("unbuilt"):
            why.append(f"{len(s['unbuilt'])} spec requirements not built")
        if viol:
            why.append(f"{len(viol)} discipline violations")
        verdict = f"Build `{s['build']}` finished with problems: " + "; ".join(why) + "."
    if browser.startswith("degraded") or browser.startswith("not runnable"):
        verdict += " NOT BROWSER-VERIFIED: " + browser
    out = ["## Final report\n", verdict]
    out += numbered("What you must do to make it live", s.get("live", []), "Nothing: no deploy step or setting was needed.")
    out += numbered("Required by the spec but not built", s.get("unbuilt", []), "None.")
    out += numbered("Spec deviations that change product behavior", s.get("deviations", []), "None.")
    out.append(f"\n### Items\n\nRoles: " + ", ".join(f"{k}=`{v}`" for k, v in s["roles"].items()) + ".\n")
    out.append("| Item | Status | Cycles | Surface | Greenfield | Critique |\n|---|---|---|---|---|---|")
    for it in items:
        out.append(f"| {it['n']} {it['name']} | {it['status']} | {it.get('cycles', 0)} | {it.get('surface', '?')} | "
                   f"{it.get('greenfield', '?')} | {it.get('critique', 'n/a')} |")
    out.append("\nGates: " + ", ".join(f"{k}={v}" for k, v in s["gates"].items()))
    out += numbered("Accepted residuals (known issues left in place)", s.get("residuals", []), "None.")
    out += numbered("Triage backlog (pre-existing problems found, not fixed)", s.get("backlog", []), "None.")
    commits = main_commits(L, s)
    out.append("\n### Commits main gained on files this build touched\n")
    out += commits or ["None."]
    out.append("\n### Discipline check\n")
    out += ["FAILED:"] + [f"- DISCIPLINE VIOLATION: {v}" for v in viol] if viol else ["clean"]
    if notes:
        out += numbered("Notes", notes, "")
    text = "\n".join(out) + "\n"
    body = L.read()
    i = body.find("\n## Final report")
    if i >= 0:
        j = body.find("\n## ", i + 1)
        body = body[:i] + (body[j:] if j > 0 else "")
    L.write(body.rstrip("\n") + "\n\n" + text)
    s["status"] = "closed"
    s["closed"] = _now()
    s["discipline"] = "failed" if viol else "clean"
    L.save(s)
    shutil.rmtree(os.path.join(L.dir, "gates"), ignore_errors=True)
    print(text)
