---
name: spec
description: Write a short, high-level build spec into specs/<name>.md. Defines WHAT to build and the non-obvious constraints (verified against code), leaving the HOW to the implementer, under one governing rule, the smallest change to the existing codebase or the simplest structure for a greenfield project. Use on /build:spec, or when asked to write/create/draft a spec, spec out a feature, or turn an idea into a build spec for an agent.
---

# /build:spec

Turn an idea into a spec an implementer (agent or human) can build from. Write it to `specs/<name>.md`, where `<name>` is the kebab-case feature name.

Works in whatever mode the conversation is already in: one-shot (you are handed a brief and write the spec) or collaborative (explore, gather info, discuss, iterate the spec together). Do not force an interview. Beyond the one mandatory transition question below, ask only when something is genuinely ambiguous and blocks writing.

## Mandatory question before writing (transition scope)

Before you write a single line of the spec, ask the user this one question and wait for the answer. It is the only question you are required to ask, and it applies to every spec, every time.

Ask it in plain prose in the conversation. Never use the AskUserQuestion tool. Ask it once, get the answer, then write.

> Before I write this: should the spec assume a clean cutover? That would mean the implementer does not design for mixed-version deploy windows, in-flight or already-queued work, rollback to a previous release, or pre-existing legacy data.

Then say, in plain words, what a clean cutover would do to this specific change on deploy, so the user can answer: for example "existing accounts would keep their current sync position" or "comments already waiting would be dropped". Name the concrete existing data or work the change touches; never ask the question in the abstract.

**If the user says yes:** put this line verbatim in the spec's Out of scope section.

> Transition concerns are out of scope: assume a clean cutover. Do not design for mixed-version deploy windows, in-flight or already-queued work, rollback to a previous release, or pre-existing legacy data.

**If the user says no, or names specific transition concerns that do matter:** leave that line out and spec the transition concerns they named as real constraints, verified against the code like any other constraint. Do not spec the ones they did not name.

**If the answer is already unambiguous in the conversation** (the user has already stated the cutover assumption, or already asked for migration/rollback handling), skip the question and follow what they said.

## The spec's job

Define the build at a high level: **what it must do**, and the **non-obvious constraints** the implementer must respect. Nothing more.

- **The HOW is always the implementer's call.** Component decomposition, file layout, naming, data structures, library choices: not yours to dictate. Any code shape, component, or name you mention is intent or example, never a prescription to follow literally.
- **Not a line-by-line build script.** If you start enumerating steps or pasting code, you have dropped too low. Climb back up.
- **Verify every constraint against the code.** A constraint is real only if it is true in this repo. Search first. Do not invent limits, invariants, or integration points from imagination. Name the file or system each constraint comes from.

## The governing rule: the smallest change

Every other rule in this skill is read under this one. The spec provisions the **smallest change to the existing codebase** that fully satisfies "what it must do", or, for a greenfield project, the **simplest structure** that does. Write it into the spec as a constraint the implementer is judged against, and shape every line of the spec so it leaves room for that change instead of foreclosing it.

"Smallest" is measured in new behavior and new structure, never in lines of diff:

- **Existing codebase:** the change touches the fewest existing surfaces and adds the fewest new pieces that the behavior genuinely requires. For a bug fix, it is the smallest change at the located cause, never a patch at a call site that hides the symptom. A split of an over-cap file that the structure rules mandate is part of the smallest change, not an excess.
- **Greenfield:** the fewest moving parts that satisfy the behavior. No layer, abstraction, or indirection without at least two real callers in this spec. No piece added because it might be needed later.
- **When the user asks to simplify or remove** ("why all these checks", "simplify this", "remove that"), "smallest" is measured by the machinery left running afterwards, not by what is added. Deleting code that no longer feeds any decision counts as smaller than a bypass that leaves it running. A spec that answers a simplification request by adding a path around the old machinery has not done what was asked.

Treat these as evidence the design is wrong, not as things to spec: a new background job or queue, a new service or long-running process, a new abstraction layer with a single caller, a caching layer, a state machine, or a configuration system. If the change appears to need one, the shape is wrong. Redesign toward the smaller change, and say in the spec that the heavy version was considered and rejected, so nobody rediscovers it later and builds it.

When this pulls against any other rule here, including the regression rule below, the smaller change wins. Regression safety is proven with tests and review, not bought with architecture. Do not spec compatibility shims, dual-write paths, or feature flags as the way to stay safe.

The rule is enforced by subtraction. When a line of the spec mandates or invites more change than the smallest one, the fix is to remove that line, never to prescribe the smaller shape in its place: the shape is still the implementer's call.

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

## Say only what was asked

- No figures, estimates, or notes to the reader that nobody asked for. A number in a spec is a constraint someone will build to; it must come from the user or from the code.
- User-visible side effects of the change (a delay a customer will wait, a message that changes, a step that disappears) are stated in plain words in the conversation before writing, and in the spec, so the user learns them before the build, not after it.
- A spec that defers to a guide document or house standard names the guide sections it inherits, so the user sees at spec time which rules the build will apply.
- **Verbatim copy.** When the build shows the user text that was approved (headlines, claims, prices, testimonials, legal lines), put those strings in a section headed `Verbatim copy`, one quoted string per line. The build copies them byte-for-byte and checks them mechanically; text outside that section is guidance, not copy.

## Do not over-index on security or compliance

Leave out security, privacy, GDPR, data-sharing, and compliance unless the user explicitly asks for them. These are handled separately from the main build. Adding them unprompted bloats the spec and is not this skill's job.

## No regressions on live surfaces

If the change touches a system that already runs in production, the spec must name what must not break. Do not write a blanket "no regressions" line: it is unverifiable, and every implementer will agree with it while breaking something.

Add a **Must not regress** section listing each live surface the change can reach, by name, verified to exist in this repo, with the behavior that must stay identical and how an implementer or reviewer would confirm it. Trace the actual call paths and shared state before writing the list; do not guess from file names or proximity at what is nearby.

That list is not decoration: `/build:build` copies it into the ledger manifest, into every executor brief, and into every review engine, where it becomes a required roll-call the reviewer answers surface by surface. A surface you leave off the list is a surface nobody checks.

Skip the section entirely when nothing live is in reach. Never include an empty or speculative one.

## What a good spec covers (guidance, not a template)

In tight prose, in whatever order fits the build:

- **Goal:** one or two lines. What this is and why it exists.
- **What it must do:** the observable behavior and outcomes. The contract the build is judged against.
- **Constraints:** the non-obvious rules, invariants, and integration points the implementer cannot infer alone. Each one verified against code. The smallest-change rule is always one of them, stated in one line, with any heavy shape that was considered and rejected.
- **Must not regress:** the named live surfaces the change can reach that must keep behaving identically, per the section above. Only when something live is in reach.
- **Out of scope:** what NOT to build, so the implementer does not gold-plate.

Drop any heading with nothing real to say. Never pad to fill a structure.

## Never name an engine or a model

The spec says what to build, never who builds it. Do not name an engine, a model, a subagent, or an effort level anywhere in the spec, and do not hint at one: no "use a Claude subagent for this", no "give this to codex", no "this item needs a stronger model". Engine and model assignment is decided at invocation time by `/build:build`'s four locked roles and by nothing else. This holds for frontend UI/UX items too: describe the interface and its behavior, and stop there.

## Final whole-build verification item (always)

End every spec's item list with one last item, always, phrased like this:

> Final item: once every other item is built and certified independently, review the entire build as one surface through the review engines, focusing on cross-item interactions, and loop fix and re-review until no verified Critical or High findings remain.

Per-item reviews certify each change in isolation; this item is the only place the interactions between items get reviewed. `/build:build` satisfies it with its whole-build review gate (map it there, never build it as an item); the line lives in the spec so the check survives even when someone builds the spec outside `/build:build`.

## Always close with a certification offer

After writing the spec, offer to certify it before anyone builds from it. A spec with a wrong or unverified constraint costs more than the review. Ask whether to run it, naming the concrete option:

> Spec written to `specs/<name>.md`. Want me to run `/build:spec-certify` on it? External reviewers check every constraint against the real code and the loop runs until nothing Critical or High is left, editing only the spec.

Do not run the certification unprompted. Just always make the offer.
