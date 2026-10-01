#!/usr/bin/env python3
"""stop-guard.py: the build plugin's own hook, for UserPromptSubmit and Stop.

UserPromptSubmit: when the prompt starts with `/build:build` (or `/goal` followed by it), record
this session as the build's owner in <cwd>/.build/owner-session; a `resume` prompt also clears a
recorded permitted stop.

Stop: block the end of a turn in the owner session while the build is open and nothing is in
flight. "In flight" comes from the Stop input's live `background_tasks` list when the harness
sends one; otherwise it is read from the whole transcript: a background Bash or Agent launch opens
its id, a task notification with a final status closes it, and a SendMessage to an agent reopens
that agent. A live engine pid with no open job blocks with an "attach" reason. After three
consecutive blocks the stop goes through and a violation is recorded. Never blocks any other
session, a closed build with no queued spec, or a build with a recorded permitted stop.
"""
import json
import os
import re
import sys
import time

TASK_DONE = re.compile(r"<task-id>(\w+)</task-id>.*?<status>(completed|failed|killed|stopped|error)</status>", re.S)
STOPPED = re.compile(r"Successfully stopped task: (\w+)")
OWNER_PROMPT = re.compile(r"^\s*(/goal\s+)?/build:build\b")
BLOCK_CAP = 3
LEDGER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ledger.py")


def read(path, default=""):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return default


def open_jobs(transcript):
    """Ids of background jobs launched in this session and still unfinished.
    Only structured fields count (a launch's toolUseResult, a notification entry's own content, a
    TaskStop result), never text quoted inside a report or a message. A fast job's notification
    can be written before its launch record, so launches and completions are matched by position:
    a job is open when its latest launch or SendMessage comes after its latest completion."""
    started, finished = {}, {}
    try:
        f = open(transcript, errors="ignore")
    except OSError:
        return {}
    agents = set()
    for i, line in enumerate(f):
        try:
            d = json.loads(line)
        except ValueError:
            continue
        r = d.get("toolUseResult")
        if isinstance(r, dict):
            if r.get("backgroundTaskId"):
                started.setdefault(r["backgroundTaskId"], i)
            if r.get("status") == "async_launched" and r.get("agentId"):
                started[r["agentId"]] = i
                agents.add(r["agentId"])
        msg = d.get("message") if isinstance(d.get("message"), dict) else {}
        content = msg.get("content")
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") == "tool_use" and part.get("name") == "SendMessage":
                    to = (part.get("input") or {}).get("to", "")
                    if to in agents:
                        started[to] = i
                if part.get("type") == "tool_result":
                    body = part.get("content")
                    body = body if isinstance(body, str) else json.dumps(body)
                    for m in STOPPED.finditer(body):
                        finished[m.group(1)] = i
        att = d.get("attachment") if isinstance(d.get("attachment"), dict) else {}
        note = d.get("content") if d.get("type") == "queue-operation" else att.get("prompt") if att else content
        if isinstance(note, str) and note.lstrip().startswith("<task-notification>"):
            for m in TASK_DONE.finditer(note):
                finished[m.group(1)] = max(finished.get(m.group(1), -1), i)
    out = {}
    for job, at in started.items():
        done = finished.get(job)
        # a bash job cannot be relaunched, so any completion closes it; an agent reopens on SendMessage
        if done is None or (job in agents and at > done):
            out[job] = "agent" if job in agents else "bash"
    return out


def live_pids(build):
    runs = os.path.join(build, "runs")
    alive = []
    for name in sorted(os.listdir(runs)) if os.path.isdir(runs) else []:
        if not name.endswith(".pid"):
            continue
        try:
            pid = int(read(os.path.join(runs, name)).strip())
            os.kill(pid, 0)
            alive.append(name[:-4])
        except (ValueError, OSError):
            continue
    return alive


def record_violation(build, text):
    st = os.path.join(build, "state.json")
    try:
        s = json.load(open(st))
        s.setdefault("violations", []).append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "text": text})
        json.dump(s, open(st, "w"), indent=2)
    except (OSError, ValueError):
        pass


def on_prompt(inp, build):
    prompt = inp.get("prompt") or inp.get("user_input") or ""
    stop = os.path.join(build, "stop-record")
    if not OWNER_PROMPT.match(prompt):
        if prompt.lstrip().startswith("<task-notification>"):
            return
        try:
            is_open = json.load(open(os.path.join(build, "state.json"))).get("status") == "open"
        except (OSError, ValueError):
            is_open = False
        if is_open and os.path.exists(stop) and read(os.path.join(build, "owner-session")).strip() == inp.get("session_id"):
            # UserPromptSubmit stdout becomes context: remind the orchestrator the build is stopped
            print(f"The build in this folder is stopped ({read(stop).strip()}). Answer in one line pointing at "
                  "the final report in .build/ledger.md; only `/build:build resume` continues the build.")
        return
    os.makedirs(build, exist_ok=True)
    with open(os.path.join(build, "owner-session"), "w") as f:
        f.write(inp.get("session_id", ""))
    if re.search(r"/build:build\s+resume\b", prompt):
        for name in ("stop-record", "stop-guard.count"):
            try:
                os.remove(os.path.join(build, name))
            except OSError:
                pass


def on_stop(inp, build):
    if read(os.path.join(build, "owner-session")).strip() != inp.get("session_id"):
        return None
    try:
        s = json.load(open(os.path.join(build, "state.json")))
    except (OSError, ValueError):
        return None
    queued = read(os.path.join(build, "queue")).strip()
    if s.get("status") != "open" and not queued:
        return None
    if os.path.exists(os.path.join(build, "stop-record")):
        return None
    counter = os.path.join(build, "stop-guard.count")
    tasks = inp.get("background_tasks")
    if isinstance(tasks, list):
        # the harness's live list: exact, and it knows about jobs a resumed or transcript-less session lost
        jobs = {t.get("id"): t.get("type") for t in tasks if isinstance(t, dict) and t.get("status") == "running"}
    else:
        jobs = open_jobs(inp.get("transcript_path", ""))
    if jobs:
        try:
            os.remove(counter)
        except OSError:
            pass
        return None
    pids = live_pids(build)
    if pids:
        reason = (f"Engine {pids[0]} is alive with no watcher. Re-attach with the launch script's "
                  f"`--attach {pids[0]}` in one background Bash call, then end the turn.")
    elif s.get("status") != "open":
        reason = f"Build closed but specs are still queued: {queued.splitlines()[0]}. Start the next one."
    else:
        cur = s.get("current") or {}
        where = f"item {cur['item']}" if cur.get("item") else cur.get("section", "the build")
        reason = (f"The build is open and nothing is running: {where}, phase {cur.get('phase', 'unknown')}. "
                  "Continue with the next step; end the turn only right after a background launch, or "
                  f"record a permitted stop with `python3 {LEDGER} stop --reason \"...\"`.")
    n = int(read(counter, "0").strip() or 0) + 1
    if n > BLOCK_CAP:
        os.remove(counter)
        record_violation(build, f"turn ended {BLOCK_CAP} times in a row with the build open and nothing running")
        return None
    with open(counter, "w") as f:
        f.write(str(n))
    return reason


def main():
    try:
        inp = json.load(sys.stdin)
    except ValueError:
        return
    build = os.path.join(inp.get("cwd") or os.getcwd(), ".build")
    event = inp.get("hook_event_name")
    if event == "UserPromptSubmit":
        on_prompt(inp, build)
    elif event == "Stop":
        reason = on_stop(inp, build)
        if reason:
            print(json.dumps({"decision": "block", "reason": reason}))


if __name__ == "__main__":
    main()
