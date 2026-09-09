#!/usr/bin/env python3
"""codex-report.py <log.jsonl> <last-message.md>

Prints the codex final message verbatim when the -o file exists; otherwise salvages the agent
messages and the last events from the --json event log, clearly labelled as salvaged.
"""
import json
import os
import sys


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(5)
    log, last = sys.argv[1], sys.argv[2]
    events = []
    for line in open(log, errors="ignore"):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except Exception:
            continue
    tools = 0
    msgs = []
    for e in events:
        item = e.get("item") or e.get("msg") or {}
        t = (item.get("type") or e.get("type") or "")
        if "command" in t or "tool" in t or "function" in t:
            tools += 1
        text = item.get("text") or item.get("message") or item.get("content")
        if isinstance(text, str) and text.strip() and ("message" in t or t.endswith("agent_message")):
            msgs.append(text.strip())
    print(f"EVENTS: {len(events)} | tool-ish events: {tools} | agent messages: {len(msgs)}")
    if os.path.exists(last) and os.path.getsize(last) > 0:
        print("--- FINAL MESSAGE ---")
        print(open(last, errors="ignore").read())
        return
    print("--- NO FINAL MESSAGE: SALVAGED FROM EVENT LOG (label it salvaged) ---")
    for m in msgs[-3:]:
        print(m[:4000])
        print("...")
    print("--- LAST EVENTS ---")
    for e in events[-5:]:
        print(json.dumps(e)[:400])
    tail = open(log, errors="ignore").read()[-600:]
    if "trust" in tail.lower() and "directory" in tail.lower():
        print("NOTE: the tail mentions a trust prompt; the directory may not be trusted.")


if __name__ == "__main__":
    main()
