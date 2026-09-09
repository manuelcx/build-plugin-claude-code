---
name: frontend-review-loop
description: Verify a frontend change by using it like a human in a real browser (Playwright MCP), then loop fix and re-check until no blocking issue remains. Boots the dev server, walks the real journey, watches the console, checks responsive, visual, accessibility, and performance, scores issues on impact and likelihood, and routes blocking fixes to the frontend executor. Use on /build:frontend-review-loop, or as the verification step after building or fixing any frontend feature.
argument-hint: "[pages or flows] [frontend=agy|codex:m:e|claude:m]"
---

# Frontend Review Loop

The shared loop shape, scoring, and stop policy are in `reference/gate-frame.md`; read it first. This file is the checklist.

<HARD-GATE>
Drive the page in a real browser and use it like a human. Reading the code or assuming a click probably works does not count. The browser is the Playwright MCP tools (`mcp__playwright__*`); `dev-browser` is used only when the user names it. With no browser tools in the session, the gate is `not runnable` (inside a build, pre-flight already stopped the run before any work).
</HARD-GATE>

## Scope

The pages and flows the item touched. Not the whole app unless the whole app changed.

## Each cycle

1. **Boot** the dev server (read the package manifest scripts). Confirm it boots clean and the page renders.
2. **Use it like a human:** pick the user's goal and walk the real journey end to end. Navigate, fill forms with good and bad input, submit, open modals and dropdowns, watch state actually update. Be a user with a task, not an auditor ticking buttons.
3. **Console, the whole time:** JS errors, warnings, failed network calls (4xx, 5xx), each tied to the action that caused it.
4. **Responsive:** mobile, tablet, desktop; overflow, clipping, nav collapse.
5. **Visual:** screenshot and look: alignment, spacing, broken images, fonts, contrast, empty and long-content states.
6. **Accessibility:** keyboard navigation, visible focus, alt text, semantic headings.
7. **Performance:** load time, layout shift, oversized bundles, render-blocking calls.
8. **Score** every issue: impact (3 a flow cannot complete or data is wrong; 2 works but clearly wrong: failed call, broken validation, layout broken at a common viewport, primary control unusable by keyboard; 1 cosmetic) times likelihood (3 the normal journey hits it; 2 an unusual but real path; 1 contrived). Blocking at 6 or more.
9. **Route** blocking issues to the frontend executor as a fix brief (pointing at `reference/executor-contract.md` and `reference/frontend-contract.md`); never edit on the main thread. Then re-run from step 1 against the touched surface.

## Exit

All seven checks ran against the current state, and no blocking issue remains. Non-blocking issues are reported, not chased. Log the row per `gate-frame.md`. Report: what you checked, what was routed and fixed, what remains.
