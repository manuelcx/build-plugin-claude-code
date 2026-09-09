#!/usr/bin/env python3
"""agy-report.py: read an agy stream-json event log and print what the orchestrator needs.

Usage:
  agy-report.py <log.jsonl>            print model, trail summary, outcome, and the report text
  agy-report.py --check <log.jsonl>    exit 0 if a non-empty report is present, else 1
  agy-report.py --id <log.jsonl>       print the conversation id
  agy-report.py --json <log.jsonl>     machine-readable summary

A non-empty response IS the report, whatever `status` says: agy stamps a whole run ERROR when a
single tool call fails while the report itself completes normally.
"""
import json
import sys


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
    if args and args[0] in ("--check", "--id", "--json"):
        mode = args[0][2:]
        args = args[1:]
    if not args:
        print(__doc__)
        sys.exit(5)
    res, model, conv, steps = load(args[0])
    resp = (res or {}).get("response") or ""
    failed = [s for s in steps if s[0] == "ERROR"]
    if mode == "check":
        sys.exit(0 if resp.strip() else 1)
    if mode == "id":
        print(conv or "")
        return
    if mode == "json":
        print(json.dumps({
            "model": model, "conversation_id": conv, "status": (res or {}).get("status"),
            "error": (res or {}).get("error"), "steps": len(steps), "failed_steps": len(failed),
            "report_chars": len(resp), "has_report": bool(resp.strip()),
        }))
        return
    print(f"MODEL: {model}")
    print(f"CONVERSATION: {conv}")
    reads = [s for s in steps if s[1] and ("read" in s[1].lower() or "view" in s[1].lower())]
    print(f"TRAIL: {len(steps)} tool steps, {len(reads)} reads, {len(failed)} failed")
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
    if resp.strip():
        print(f"--- REPORT ({len(resp)} chars) ---")
        print(resp)
    else:
        print("--- NO REPORT TEXT ---")


if __name__ == "__main__":
    main()
