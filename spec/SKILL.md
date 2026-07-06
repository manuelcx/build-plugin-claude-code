---
name: spec
description: Write a short, high-level build spec into specs/<name>.md. Defines WHAT to build and the non-obvious constraints (verified against code), leaving the HOW to the implementer. Use on /spec, or when asked to write/create/draft a spec, spec out a feature, or turn an idea into a build spec for an agent.
---

# /spec

Turn an idea into a spec an implementer (agent or human) can build from. Write it to `specs/<name>.md`, where `<name>` is the kebab-case feature name.

Works in whatever mode the conversation is already in: one-shot (you are handed a brief and write the spec) or collaborative (explore, gather info, discuss, iterate the spec together). Do not force an interview. Ask only when something is genuinely ambiguous and blocks writing.

## The spec's job

Define the build at a high level: **what it must do**, and the **non-obvious constraints** the implementer must respect. Nothing more.

- **The HOW is always the implementer's call.** Component decomposition, file layout, naming, data structures, library choices: not yours to dictate. Any code shape, component, or name you mention is intent or example, never a prescription to follow literally.
- **Not a line-by-line build script.** If you start enumerating steps or pasting code, you have dropped too low. Climb back up.
- **Verify every constraint against the code.** A constraint is real only if it is true in this repo. Search first. Do not invent limits, invariants, or integration points from imagination. Name the file or system each constraint comes from.

## Concision (non-negotiable)

The spec is SHORT. Every line earns its place.

- No preamble, no "this document describes...", no restating the obvious.
- No hedging, no motivational padding, no summarizing what you just wrote.
- Cut adjectives and adverbs that do not change meaning.
- If a sentence can be removed without losing information, remove it.

You default to long. Fight it. Reread the draft once and delete everything that is not load-bearing.

## Build toward production, always

What you spec is **the real product, production-ready from day 0**, unless the user explicitly says otherwise.

- Never frame it as a "v1", "v2", "MVP", "demo", "prototype", "initial version", or "throwaway we will rework later". That framing is banned.
- Incremental is fine: a spec can cover one slice of the real product. "Work-in-progress toward the final thing" is not "disposable." The quality bar is the final bar.
- No escape hatches: no "good enough for now", "we can harden it later", "placeholder until".

## Do not over-index on security or compliance

Leave out security, privacy, GDPR, data-sharing, and compliance unless the user explicitly asks for them. These are handled separately from the main build. Adding them unprompted bloats the spec and is not this skill's job.

## What a good spec covers (guidance, not a template)

In tight prose, in whatever order fits the build:

- **Goal:** one or two lines. What this is and why it exists.
- **What it must do:** the observable behavior and outcomes. The contract the build is judged against.
- **Constraints:** the non-obvious rules, invariants, and integration points the implementer cannot infer alone. Each one verified against code.
- **Out of scope:** what NOT to build, so the implementer does not gold-plate.

Drop any heading with nothing real to say. Never pad to fill a structure.

## Frontend UI/UX work

For each spec item that involves frontend UI/UX work, add one short sentence under that item telling the executor to use Claude subagents for it if available. Repeat per item, one line each, no elaboration. Items with no UI/UX work get no such line.

## Always close with a review offer

After writing the spec, offer to stress-test it before anyone builds from it. A spec with a wrong or unverified constraint costs more than the review. Ask whether to run a sub-agent review, naming a concrete option:

> Spec written to `specs/<name>.md`. Want me to run `/multi-review` on it (sub-agents check the constraints against the code and flag anything weak or missing)? Or a lighter single sub-agent pass?

Do not run the review unprompted. Just always make the offer.
