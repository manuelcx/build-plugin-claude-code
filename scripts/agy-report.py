#!/usr/bin/env python3
"""agy-report.py: read an agy stream-json event log and print what the orchestrator needs.

Usage:
  agy-report.py <log.jsonl>            print model, trail summary, outcome, and the report text
  agy-report.py --check <log.jsonl>    exit 0 if a non-empty report is present, else 1
  agy-report.py --id <log.jsonl>       print the conversation id
  agy-report.py --json <log.jsonl>     machine-readable summary
  agy-report.py --quota <log.jsonl>    exit 0 if the run failed on a quota or rate limit, else 1
  agy-report.py --text <log.jsonl>     print only the report text (nothing when there is no report)

A non-empty response IS the report, whatever `status` says: agy stamps a whole run ERROR when a
single tool call fails while the report itself completes normally. A placeholder response (a
bare "<wait>", "Waiting for background task ...") is not a report. The WRITES line counts write
tool steps in the trail; it is a hint only, since a shell heredoc write is invisible to it (the
build decides "no changes" from the snapshot, never from this line).
"""
import json
import re
import sys

PLACEHOLDER = re.compile(r"^\s*(<wait>|waiting for (the )?background task|waiting for background)", re.I)
QUOTA = re.compile(r"\b429\b|RESOURCE_EXHAUSTED|rate[ _-]?limit|quota|limit reached|usage limit", re.I)
WRITE_TOOLS = re.compile(r"write|edit|replace|create|patch|apply", re.I)


def is_report(resp):
    return bool(resp.strip()) and not (len(resp) < 300 and PLACEHOLDER.search(resp))


def quota_hit(path, res):
    """Quota or rate limit, judged from the result's error and the non-JSON lines (stderr),
    never from tool output, which may legitimately mention a 429."""
    if res and res.get("error") and QUOTA.search(str(res.get("error"))):
        return True
    raw = [l for l in open(path, errors="ignore") if l.strip() and not l.lstrip().startswith("{")]
    return any(QUOTA.search(l) for l in raw[-40:])


def load(path):
    res = None
    model = None
    conv = None
    steps = []
    for line in open(path, errors="ignore"):
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except Exception:
            continue
        if conv is None and o.get("conversation_id"):
            conv = o["conversation_id"]
        ev = o.get("event")
        if ev == "init":
            model = (o.get("init") or {}).get("model")
        elif ev == "result":
            res = o.get("result") or {}
        elif ev == "step_update":
            st = o.get("step_update") or {}
            if st.get("step_type") == "tool":
                params = (st.get("tool_info") or {}).get("parameters")
                steps.append((st.get("state"), st.get("tool_name"), str(params)[:140]))
    return res, model, conv, steps


def main():
    args = sys.argv[1:]
    mode = "print"
    if args and args[0] in ("--check", "--id", "--json", "--quota", "--text"):
        mode = args[0][2:]
        args = args[1:]
    if not args:
        print(__doc__)
        sys.exit(5)
    res, model, conv, steps = load(args[0])
    resp = (res or {}).get("response") or ""
    failed = [s for s in steps if s[0] == "ERROR"]
    writes = [s for s in steps if s[1] and WRITE_TOOLS.search(s[1]) and s[0] != "ERROR"]
    if mode == "check":
        sys.exit(0 if is_report(resp) else 1)
    if mode == "text":
        if is_report(resp):
            print(resp)
        return
    if mode == "quota":
        sys.exit(0 if not is_report(resp) and quota_hit(args[0], res) else 1)
    if mode == "id":
        print(conv or "")
        return
    if mode == "json":
        print(json.dumps({
            "model": model, "conversation_id": conv, "status": (res or {}).get("status"),
            "error": (res or {}).get("error"), "steps": len(steps), "failed_steps": len(failed),
            "report_chars": len(resp), "has_report": is_report(resp), "writes": len(writes),
        }))
        return
    print(f"MODEL: {model}")
    print(f"CONVERSATION: {conv}")
    reads = [s for s in steps if s[1] and ("read" in s[1].lower() or "view" in s[1].lower())]
    print(f"TRAIL: {len(steps)} tool steps, {len(reads)} reads, {len(failed)} failed")
    print(f"WRITES: {len(writes)} write steps in the trail" + ("  (NO CHANGES hint: check the snapshot)" if not writes else ""))
    for state, name, params in steps[-12:]:
        print(f"  [{state}] {name} {params}")
    if failed:
        print("FAILED TOOL CALLS (do not by themselves invalidate the report):")
        for state, name, params in failed[:10]:
            print(f"  {name} {params}")
    if res is None:
        print("NO RESULT EVENT: the run died before flushing; the trail above is all there is.")
        return
    print(f"STATUS: {res.get('status')} | turns: {res.get('num_turns')} | seconds: {res.get('duration_seconds')}")
    if res.get("error"):
        print(f"ERROR: {res['error']}")
    if resp.strip() and not is_report(resp):
        print(f"--- PLACEHOLDER, NOT A REPORT: {resp.strip()[:120]} ---")
    elif resp.strip():
        print(f"--- REPORT ({len(resp)} chars) ---")
        print(resp)
    else:
        print("--- NO REPORT TEXT ---")


if __name__ == "__main__":
    main()
