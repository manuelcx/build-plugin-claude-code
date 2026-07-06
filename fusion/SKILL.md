---
name: fusion
description: Answer an open-ended prompt by running a diverse multi-model panel in parallel (Claude lenses + GPT-5 via /codex), then a judge produces a structured JSON analysis (consensus, contradictions, partial coverage, unique insights, blind spots) and a synthesized final answer. Use on /fusion, or when the user wants several models' perspectives fused: research, hard or ambiguous decisions, compare/contrast, expert critique, high-stakes questions where diverse views plus synthesis beat one model. Domain-agnostic.
---

# Fusion

Diverse panel runs in parallel on the same prompt -> a judge emits a structured JSON analysis -> a synthesized final answer. The deliverable is the JSON analysis followed by the synthesis. Run autonomously end to end. Works for any prompt; never narrow by domain.

## 1. Pin the prompt
Take the user's prompt verbatim as the shared task. If it references files, pin them as absolute paths so every panelist hits the identical target. The SAME prompt goes to every panelist (Fusion's core principle); the only per-panelist variation is the Claude lenses in step 2.

## 2. Panel: fire all four in the SAME turn (parallel)
Genuine model diversity is the whole point; identical models would just echo each other.

- **GPT-5 -> `/codex`**: invoke it as the actual slash command (via the Skill tool), passing this answer-brief as the argument:
  > *"Answer this fully: \<PROMPT\>. This is an analysis/answer task, NOT a coding task: do NOT edit any files. Output only your complete answer. Be thorough; state key assumptions and flag any uncertainty."*

  You MUST use the command, never hand-roll `codex exec` (the raw CLI hangs; the command carries the only working anti-hang recipe and backgrounds itself). codex answers from model knowledge (its command disables network); the guaranteed live-web layer is the Claude panelists and the judge below.

- **Claude -> 3 lens panelists**, fired as parallel `Agent()` calls, each given the identical prompt under a distinct lens so they don't converge:
  1. **Direct** — the strongest straightforward, complete answer.
  2. **Skeptic** — challenge assumptions, surface failure modes, what's likely wrong or overstated.
  3. **First-principles** — reframe the problem; alternative approaches and non-obvious angles.

  Each panelist uses **WebSearch** for anything time-sensitive or factual. Set an explicit `model` on every call (e.g. `opus`/`sonnet`), **never `fable`**.

Wait for all four to return. If one can't run, hangs, or errors (e.g. codex needs a trusted dir), note it and proceed with whatever returned — a dead panelist never blocks the run. Discard any stray file edits.

## 3. Judge + synthesize (Workflow)
Pass the original prompt + all returned answers (each labeled by source) into a Workflow with two stages:

- **Judge agent** (WebSearch on, non-fable): read every answer and emit ONLY this schema. It may search to verify claims and resolve disagreements.
  ```json
  {
    "consensus":     [ { "claim": "...", "confidence": "high|med", "verified": "yes|no|n/a" } ],
    "contradictions":[ { "point": "...", "positions": {"claude":"...","gpt5":"..."}, "verdict": "judge's resolution, web-checked when possible" } ],
    "partial":       [ { "claim": "...", "covered_by": ["..."] } ],
    "unique":        [ { "insight": "...", "from": "..." } ],
    "blind_spots":   [ "what NONE of the panel addressed" ],
    "open_questions":[ "still unresolved / worth digging into next" ]
  }
  ```
  Two non-negotiables: consensus is not truth — flag agreement the judge could not independently verify as `verified: "no"`; and every contradiction must be resolved in `verdict`, not just listed.
- **Synthesis agent** (non-fable): write the final answer grounded in the judge JSON. Lead with verified consensus, settle contradictions per the judge's verdicts, fold in the best unique insights, and state remaining blind spots / open questions honestly. Cite sources where web was used.

The Workflow returns both the filled-in JSON and the synthesis.

## 4. Output
Show the user, in this order:
1. The judge's **structured JSON analysis** (the schema above, filled in).
2. The **synthesized final answer**.

Keep both — the JSON is half the value.

## 5. Cleanup
Remove scratch files however each panelist ended: `rm -f .codex-run.jsonl .codex-last-message.md`.

## Rules
- codex ALWAYS runs through its `/codex` command. Never reconstruct the raw CLI or choose your own flags — it hangs. If the command is unavailable, drop that panelist and proceed with the rest.
- Never spawn `fable` subagents; set an explicit non-fable `model` on every Agent/Workflow call.
- Same prompt to every panelist; the lenses vary only the three Claude panelists.
- Agnostic: never refuse or narrow by domain. Even for coding, run it as asked.
- Be concise. No em dashes.
