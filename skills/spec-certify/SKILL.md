---
name: spec-certify
description: Certify an already-written spec by looping external adversarial review over it until no verified Critical or High findings remain. Each cycle runs /build:review report-only twice on the spec file: a first reviewer the user picks at intake (codex or a Claude subagent) and then an agy reviewer. Claude verifies every finding against the real repo, rejects anything that would push the spec below its altitude, and edits the spec itself. Use on /build:spec-certify, or when asked to certify, harden, stress-test to convergence, or sign off a spec before anyone builds from it. Reviews and revises the spec only; never writes implementation code.
---

# /build:spec-certify

Take an existing spec and drive it to a certified state: **zero verified Critical or High findings, from both review engines, in one cycle.**

The deliverable is a revised spec plus a certification record. Nothing else is built, and no implementation code is written at any point.

## Unattended operation

This is a long agentic loop. Once invoked it runs to convergence without the user. After the intake question in section 0, never stop to ask another one: never ask for approval to fix, never ask whether to run one more cycle, never use the AskUserQuestion tool.

There is no cycle cap. Non-convergence is not a reason to stop, park the work, or fall back to something lighter: run another cycle.

Exactly one question is ever asked, and it is asked in section 0 before the first cycle starts. After that there are exactly two permitted stops, both of them reports and neither of them a question:

- **Hard tooling failure:** both engines are unavailable or die repeatedly and the loop cannot run at all. Report what failed and where the spec stands.
- **Low context:** report the cycle you finished, the state of the ledger, and what the next cycle should carry forward, so a fresh session resumes cleanly.

## 0. Intake: which engine fills the first reviewer slot

Every cycle runs two reviewers of different model families, sequentially. The **second** slot is always agy and is never up for discussion. The **first** slot is the user's choice between two engines:

- **`codex:gpt-6-astra:medium`**, an external OpenAI CLI run. Slower, a genuinely foreign model family, the strongest lens this skill has.
- **`claude:fable:high`**, a Claude subagent through the Agent tool. Faster and cheaper, no external CLI to hang, but a nearer neighbour to the main thread doing the adjudicating.

**There is no default. Ask, in plain prose in the conversation, and wait for the answer before anything else runs.** Do not use the AskUserQuestion tool. One short question naming the two options and their tradeoff, nothing else.

Skip the question only when the choice is already unambiguous:

- The invocation carried it: `/build:spec-certify specs/foo.md reviewer=codex` or `reviewer=claude` (also accepted: a full triple such as `reviewer=codex:gpt-6-astra:high` or `reviewer=claude:opus:high`, which is used verbatim).
- The user said which engine they wanted earlier in this conversation, in any words.

When you skip it, say in one line which engine you are using and where that instruction came from. When you ask, ask once: an unclear answer gets one clarification, and a genuinely unreadable second answer means you stop and report rather than guessing.

Whatever is chosen becomes the first-slot engine for **every** cycle of this run. It is locked from that point: a run does not switch engines mid-loop, and a failing first-slot engine is retried on itself, never silently swapped for the other one.

## 1. Target

The spec file, as an **absolute path**. An explicit argument wins (`/build:spec-certify specs/foo.md`). Otherwise take the most recently modified file in `specs/`, and state which one you picked in one line before firing.

Read the whole spec first. Also read the spec skill that ships beside this one, at `$PLUGIN_ROOT/skills/spec/SKILL.md` (resolve the root once per session with `PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(ls -d ~/.claude/plugins/cache/*/build/*/ | sort -V | tail -1)}"`), so the shape rules you enforce below are the current ones and not your memory of them.

Snapshot the starting state before cycle 1: `git --no-pager diff -- <spec-path> > <scratch>/spec-certify-baseline.patch` when the tree is dirty, or note the commit hash when it is clean. Every "what did this run change" claim is measured against that snapshot.

## 2. The altitude contract (read before every fix round)

A spec says **what** must be built and the **non-obvious constraints** the implementer cannot infer alone. The **how** belongs to the implementer. External reviewers do not know this, and both engines will push toward implementation detail because that is what a hostile code reviewer is trained to want.

**The line is existing code versus new code, not detail versus no detail.**

Naming code that already exists is the spec's job, and a bug-fix spec cannot do its job without it. Pointing at the exact function where the wrong behavior comes from, the call path that reaches it, the table or column that holds the bad state, the existing route or contract the fix must keep honouring, the concrete inputs that reproduce the bug: all of that is a verified constraint, and a reviewer who asks for it has found a real gap. Precision about what is already there is never overreach, however specific it gets.

Prescribing code the implementer has not written yet is where the spec drops below its altitude. A reviewer asking the spec to decide how the fix should be shaped is asking the spec to do the implementer's thinking.

Findings of these kinds are **rejected by construction**, whatever severity a reviewer gave them:

- Prescribing the shape of the new work: which files to create, how to decompose it, what to name a new function or component, its signature, its data structures, or which library to reach for. Naming an existing symbol the change must touch is the opposite of this and is welcome.
- Asking for code, pseudocode, or a step-by-step build order. Describing observed current behavior, or an exact reproduction of the bug, is not this.
- Asking the spec to design new error handling, retry, logging, or validation mechanics that an implementer settles while building. Recording error handling that already exists and must keep behaving identically, or a failure mode actually observed in the wild, is a constraint and stays.
- Asking to add security, privacy, GDPR, or compliance sections the user never requested.
- Asking to design for mixed-version deploys, in-flight work, rollback, or legacy data when the spec already declares a clean cutover.
- Asking for phasing, an MVP, a v1, a rollout plan, or a "harden it later" hedge.
- Asking for compatibility shims, dual-write paths, feature flags, background jobs, queues, new services, single-caller abstraction layers, caching layers, state machines, or config systems. The spec is judged on proportionality: if the reviewer's fix needs architecture, the reviewer is wrong about the spec, not the spec about the build.

**The test when a finding sits on the line:** does it make the spec more accurate about the system as it is today, or does it make a decision that belongs to whoever builds the change? The first is a fix. The second is a rejection. When you genuinely cannot tell, treat it as a fix and write it at the smallest altitude that resolves the ambiguity, because a spec that is too specific about the existing code costs a reader a few seconds, while one that is wrong or vague about it costs a whole build.

Any code shape or name the spec does mention is intent or example, never an instruction to follow literally, and the spec says so where that could be misread.

Rejecting a finding is a decision you record, not one you hide. Every rejected Critical or High goes in the ledger with the one-line reason, and it goes into the next cycle's brief so no engine re-raises it.

**The spec does not grow to satisfy a reviewer.** A fix replaces a wrong or missing line; it rarely appends a section. If a cycle's fixes made the spec meaningfully longer, reread it and cut what is not load-bearing in the same edit, never as a separate pass on a cycle that did not otherwise change the spec. A spec that doubled in length during certification failed certification. Detail about existing code is exempt from this pressure when it is load-bearing: cut padding, never cut a verified constraint.

## 3. What counts as a real finding

Blocking (Critical/High, must be fixed before the spec certifies):

- **False constraint:** the spec states something about this repo that is not true. Verified by reading the code.
- **Missing constraint:** a non-obvious rule, invariant, or integration point the implementer cannot discover alone and would plausibly get wrong. Verified by finding the code that imposes it.
- **Contradiction:** two lines that cannot both be satisfied.
- **Divergent ambiguity:** a line two competent implementers would read two different ways, producing different builds. "Could be more precise" is not this; two defensible readings is.
- **Behavior gap:** an outcome the goal implies that no line in "What it must do" actually requires, so nothing judges the build on it.
- **Unprotected live surface:** a production surface the described change can reach, traced through real call paths, that the `Must not regress` section leaves out.
- **Wrong or unproven diagnosis (bug-fix specs):** the spec names a cause, a location, or a reproduction that the code does not support, or it asserts one without having traced it. Blocking, because every downstream decision rests on it.
- **Unlocated fix (bug-fix specs):** the spec describes the broken behavior but never names where in the existing code it originates, so the implementer has to redo the diagnosis and may land somewhere else.
- **Unbuildable scope:** the spec asks for something the repo makes impossible, or depends on a system, endpoint, table, or flag that does not exist.

Non-blocking (fix if cheap, never blocks certification): wording, ordering, redundancy, anything the altitude contract rejects, and any finding that is genuinely a build-time decision.

## 4. The cycle

One cycle is both engines over the same unchanged spec text, then one adjudication and fix round. "Both engines" means the first-slot engine locked in section 0, then agy.

**Run the two reviewers sequentially, never in the same turn.** Each `/build:review` pass is one external run; keep them one after the other so the second reviewer's cycle brief can list what the first already raised.

**4a. `/build:review reviewer=<the section 0 engine> report-only`.** Invoke the actual skill through the Skill tool. Pass it the spec's absolute path as the target and, verbatim in the argument: this is a non-code target, review only and make no edits, do not fix anything, hand the findings back. `/build:review` owns how each engine is launched, including the Claude subagent path (`subagent_type: build:reviewer` through the Agent tool), so this skill never launches one itself.

**4b. `/build:review reviewer=agy report-only`.** Same, through the Skill tool, with the first pass's findings listed as already raised so they are not duplicated.

**Vocabulary.** `/build:review` returns findings scored on impact times likelihood, not Critical/High labels. For this skill, "Critical or High" means a verified finding scoring 6 or more; everything below that is the Medium tier here. The reviewer contract's non-code remap applies because the target is a spec.

Both engines get the same context, and you state it in the invocation argument every cycle:

- The spec's absolute path, and the repo root the constraints must be checked against.
- The altitude contract from section 2, compressed: the spec deliberately leaves the shape of the new work to the implementer, so "decide the structure here" is not a finding, while "you are wrong or vague about the code that already exists" always is.
- What to attack instead: every factual constraint is checked against the actual code and reported as false if it does not hold; every claim about an existing file, route, table, job, or symbol is confirmed to exist; anything an implementer would have to guess is reported as a gap.
- The spec path as the scope reference, which activates each engine's Scope advisory lane.
- The spec's `Must not regress` list verbatim when it has one, which activates each engine's protected-surfaces roll-call.
- Findings already fixed in earlier cycles, and findings already rejected under the altitude contract, each with its reason. Neither list is to be re-raised.

**4c. Adjudicate.** Merge both engines' output, dedup, then take each Critical and High in turn:

- Reject it if the altitude contract rejects it. Record the reason.
- Otherwise verify it against the repo yourself: read the file, grep the symbol, trace the call path. A finding is real only when you have seen the code that makes it real. **Never edit the spec on a reviewer's word alone**, and treat an engine's confidence as an opinion, not evidence.
- Mark it UNVERIFIABLE when the check needs something you do not have (a running service, live data). Name the missing capability, report it, do not silently drop it, and do not let it block certification.

**4d. Fix.** Claude edits the spec directly. The spec is a non-code target, so neither engine's executor ever touches it, and no `/build:codex` or `/build:agy` write pass runs in this skill.

Whether the spec is edited at all depends on what survived adjudication:

- **At least one verified blocking finding:** apply every surviving Critical and High, and in the same edit apply any verified Medium or Low that is plainly right. This cycle already costs a confirming cycle, so the non-blocking fixes ride along for free.
- **Zero verified blocking findings:** the spec is frozen. Do not touch it, not for a cheap Medium, not for a one-word correction, not for a concision pass. Every verified Medium and Low goes into the ledger as a residual, and from there into the final report. A non-blocking finding is by definition one the builder can absorb, and editing for it would void a cycle that just qualified. The only exception is a new requirement the user states mid-run, which is applied and logged as an owner addition.

Non-blocking findings never cost a cycle. Two fresh reviewers on an unchanged spec will always return a few Mediums; if each of them restarted the clock, the loop would end only when both engines returned nothing at all, which is not the gate.

When the spec was edited, reread the whole spec once against `/build:spec`'s own rules and fix any of these the edits broke:

- Concision: nothing that can be removed without losing information survives.
- No `v1`, `MVP`, `prototype`, `initial version`, `placeholder`, or "we can harden it later" framing.
- Security, privacy, and compliance stay out unless the user asked for them.
- `Must not regress` names real, verified surfaces, with the behavior that must stay identical and how to confirm it, or the section is absent entirely. Never empty, never speculative.
- Proportionality is stated as a constraint, and no heavy machinery is specced as the way to stay safe.
- The final whole-build verification item is present as the last item.
- No em dashes anywhere.

**4e. Log the cycle** to `specs/<name>.certify-log.md`: cycle number, engines run, findings per severity from each, how many verified, how many rejected under the altitude contract and why, what changed in the spec, the verified non-blocking findings left as residuals (each with its score and a one-line description the builder can act on), spec line count before and after.

## 5. Certification gate

The spec certifies on a **qualifying cycle**: both engines ran to completion, both verification passes finished, and zero verified Critical or High findings survive adjudication.

- A cycle where an engine died, was killed, or returned nothing does not qualify. Rerun it.
- A cycle whose Criticals and Highs were all rejected under the altitude contract **does** qualify, since none of them were spec defects. Say so explicitly in the report rather than implying the reviewers found nothing.
- A cycle that changed the spec never certifies it. Fixes always cost one more confirming cycle, because a fix is itself new text nobody has reviewed.
- A cycle with zero verified blocking findings certifies **even when the reviewers returned Mediums and Lows**. Those are residuals, not a reason to edit and run again. The gate is zero Critical or High, not zero findings.
- UNVERIFIABLE findings do not block. They ship in the report as open questions for the user.

## 6. Final report

Lead with the verdict: certified after N cycles, or stopped for one of the two permitted reasons. Name the first-slot engine that ran alongside agy, and say whether it was chosen by the intake question or carried in the invocation.

Then, in plain sentences:

- What the spec now says that it did not say before, in terms someone who never read either version can follow.
- The blocking findings that were real, and what each one changed.
- The findings rejected under the altitude contract, with the reason each was out of bounds. This section is not optional: it is how the user sees what the reviewers wanted and why the spec did not give it to them.
- Anything left UNVERIFIABLE, naming the capability that was missing.
- **Residuals:** the verified non-blocking findings the spec did not absorb, from every cycle, each with its score and a one-line description. The user can apply any of them by hand or hand the list to the builder; the skill does not.
- Spec length before and after, and `git --no-pager diff --stat` on the spec plus a one-line revert pointer.

Close by offering the build: the spec is ready for `/build:build`.

## Rules

- **The spec is the only file this skill edits.** No implementation code, no tests, no config, ever, whatever a reviewer suggests.
- **Both engines run through `/build:review` via the Skill tool.** Never hand-roll `codex exec` or `agy`, and never spawn the Claude reviewer subagent directly: the review skill carries the reviewer contract, the anti-hang launch recipes, the interrogation round, and the scoring.
- **The first-slot engine is asked for once and then locked.** No default, no mid-run switch, no substituting the other engine when one fails.
- **Report-only, both engines, every cycle.** Adjudication is the main thread's job and it happens before a single character of the spec changes.
- **Verify before you edit.** A finding you have not confirmed against the repo does not change the spec.
- **Non-blocking findings never cost a cycle.** A cycle with zero verified blocking findings freezes the spec and certifies; its Mediums and Lows are residuals in the ledger and the report.
- **Never re-raise settled ground.** Fixed findings and rejected findings both travel forward in the next cycle's brief.
- **Never let the spec drift downward in altitude.** If certification would only pass by turning the spec into a build script, the finding is wrong, not the spec.
- **Sweep engine scratch files** after each cycle, exactly as the engines' own rules require.
- Be concise. No em dashes.
