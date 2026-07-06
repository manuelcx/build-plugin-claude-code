---
name: frontend-review-loop
description: Verify a frontend change by actually using it like a human in a real browser, then loop fix -> re-review until no Critical or High issues remain. Boots the dev server, drives the page via /dev-browser or Playwright, watches the console, and checks responsiveness, visuals, accessibility, and performance. Use on /frontend-review-loop, or as the verification step after building or fixing any frontend feature.
---

# Frontend Review Loop

Verify a frontend change the only honest way: open it in a real browser, use it like the user would, and keep fixing until it holds up.

<HARD-GATE>
You MUST drive the page in a real browser and use it like a human. Reading the code or assuming a click "probably works" does NOT count. Use /dev-browser OR Playwright. If NEITHER is available, STOP and ask the user immediately, before booting anything else.
</HARD-GATE>

## Browser (required, pick one)

- **/dev-browser** — drives the user's real Chrome session.
- **Playwright MCP** (`mcp__playwright__*`) — drives a managed browser.
- **Neither available?** STOP. Ask the user which to enable. Do not fall back to reading code or guessing behavior.

## Scope

Review the page(s) and flow(s) touched by the work you just did, the feature you built or the bug you fixed. Not the whole app unless the whole app changed. This skill is normally invoked as the verification step at the end of a build/fix task.

## Run it as a loop

This is objective-bound, not time-bound. Run under `/loop` with no interval so it self-paces:

```
/loop /frontend-review-loop
```

The Exit Criteria below ARE the loop's objective. Keep iterating until they are met.

## Each cycle

1. **Boot** — auto-detect and start the dev server (read `package.json` scripts; typically `npm run dev`, `pnpm dev`, `bun run dev`). Confirm it boots clean and the page renders. If the command can't be determined, ask.
2. **Use it like a human** — open the page in the browser, pick the user's goal, and walk the real journey end to end: navigate, fill forms with good AND bad input, submit, trigger modals/dropdowns, watch state actually update. Be the user with a task, not an auditor ticking off buttons.
3. **Watch the console the whole time** — JS errors, warnings, failed network calls (4xx/5xx), each tied to the action that caused it.
4. **Responsive** — resize to mobile / tablet / desktop; check overflow, clipping, nav collapse.
5. **Visual** — screenshot and actually look: alignment, spacing, broken images, fonts, contrast, empty and long-content states.
6. **Accessibility** — keyboard nav, focus visible, alt text, semantic headings.
7. **Performance** — load time, layout shift, oversized bundles, render-blocking calls.
8. **Classify** every issue found: Critical / High / Medium / Low.
9. **Fix all Critical and High**, then re-review from step 1 against the touched surface.

## Severity

- **Critical** — broken/unusable: crash, blank page, flow can't complete, console error that breaks function.
- **High** — works but clearly wrong: failed network call, broken validation, layout breaks at a common viewport, primary control unusable by keyboard.
- **Medium** — noticeable but non-blocking: spacing/alignment, minor console warning, sluggish load.
- **Low** — cosmetic polish.

## Exit Criteria

Stop the loop ONLY when both hold:

- All 7 checks ran against the current state of the touched surface, AND
- No Critical or High issues remain.

Medium and Low may remain. Report them, don't block on them.

Then report: what you checked, what you fixed, and any Medium/Low left open.

## Stop and ask (never loop forever)

- Neither /dev-browser nor Playwright available → ask immediately, before booting.
- Dev server start command can't be determined → ask.
- The same Critical/High issue survives 3 fix attempts → stop, report what you tried, ask.
- A fix needs a decision outside this task's scope → ask.
