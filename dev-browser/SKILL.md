---
name: dev-browser
description: Control the user's real Chrome browser via dev-browser CLI. Use when the user invokes /dev-browser to interact with their actual logged-in Chrome session programmatically.
---

# dev-browser

Control the user's real Chrome browser (with all logged-in sessions, cookies, extensions) via the `dev-browser` CLI and Chrome DevTools Protocol.

## When to Use This

Only when the user explicitly invokes `/dev-browser`. This skill is for tasks that need the user's real Chrome session: checking dashboards, reading logged-in pages, filling forms on authenticated sites, scraping data from services the user is already signed into.

## Safety Rules

**Financial sites are off-limits.** Never navigate to, interact with, or scrape data from:
- Banking sites (any bank login, account, or transaction page)
- Payment processors (Stripe dashboard, PayPal, Square, etc.)
- Credit card portals or billing pages
- Cryptocurrency exchanges or wallets
- Investment/brokerage platforms

If a task requires interacting with a financial site, stop and tell the user to do it manually. No exceptions.

## Prerequisites

The user must have:
1. `dev-browser` installed globally (`npm i -g dev-browser`)
2. Chrome running (no special launch flags needed on recent Chrome versions; the CLI auto-discovers via `DevToolsActivePort`)

If either is missing, tell the user what to enable before proceeding.

## Core Syntax

Use `--connect` with **no URL** to attach to the user's real Chrome. The CLI auto-discovers the debugging endpoint by reading the `DevToolsActivePort` file Chrome writes inside its user data dir (dynamically-allocated port + WS path, no special launch flags required). Without `--connect`, dev-browser launches a separate managed Chromium instance.

```bash
dev-browser --connect <<'EOF'
const page = await browser.getPage("descriptive-name");
await page.goto("https://example.com");
console.log(await page.title());
EOF
```

**Fallback (explicit URL):** Use `--connect http://localhost:<port>` only when the user manually launched Chrome with both `--remote-debugging-port=<port>` and `--remote-allow-origins=*`. On modern Chrome, omitting `--remote-allow-origins=*` makes the WebSocket handshake return 403 and the connection fails. The auto-discovery path above avoids this entirely.

**Timeout:** Default is 30s. For longer operations, pass `--timeout 60`.

## Key Patterns

### List open tabs
```bash
dev-browser --connect <<'EOF'
const tabs = await browser.listPages();
console.log(JSON.stringify(tabs, null, 2));
EOF
```

### Connect to an existing tab by ID
```bash
dev-browser --connect <<'EOF'
const tabs = await browser.listPages();
// Find the tab you want from the list, then:
const page = await browser.getPage("TARGET_ID_HERE");
console.log(JSON.stringify({ url: page.url(), title: await page.title() }, null, 2));
EOF
```

### Discover page structure (unknown pages)
```bash
dev-browser --connect <<'EOF'
const page = await browser.getPage("main");
const result = await page.snapshotForAI();
console.log(result.full);
EOF
```

### Take a screenshot
```bash
dev-browser --connect <<'EOF'
const page = await browser.getPage("main");
const buf = await page.screenshot();
const path = await saveScreenshot(buf, "debug.png");
console.log(path);
EOF
```

### Fill a form
```bash
dev-browser --connect <<'EOF'
const page = await browser.getPage("form");
await page.fill("#email", "user@example.com");
await page.click("button[type=submit]");
await page.waitForURL("**/success");
console.log("Done:", page.url());
EOF
```

### Wait for elements
```bash
dev-browser --connect <<'EOF'
const page = await browser.getPage("results");
await page.waitForSelector(".results-list");
const count = await page.$$eval(".results-list li", els => els.length);
console.log("Results:", count);
EOF
```

### Save data to file
```bash
dev-browser --connect <<'EOF'
const page = await browser.getPage("data");
const data = await page.$$eval("table tr", rows =>
  rows.map(r => Array.from(r.cells).map(c => c.textContent.trim()))
);
const path = await writeFile("export.json", JSON.stringify(data, null, 2));
console.log("Saved to:", path);
EOF
```

## Script Rules

Scripts run in a QuickJS sandbox, not Node.js. The following are NOT available:
- `require()` / `import()` - no modules
- `process`, `fs`, `path`, `os` - no system access
- `fetch` / `WebSocket` - no direct network access

Available globals: `browser`, `console`, `setTimeout`, `saveScreenshot()`, `writeFile()`, `readFile()`.

Inside `page.evaluate(...)`, use plain JavaScript only (no TypeScript).

## Page Object API

Pages returned by `browser.getPage()` are Playwright Page objects. Common methods:

| Method | Purpose |
|--------|---------|
| `page.goto(url)` | Navigate to URL |
| `page.title()` | Get page title |
| `page.url()` | Get current URL |
| `page.snapshotForAI()` | AI-optimized DOM snapshot |
| `page.getByRole(role, { name })` | Target elements from snapshot |
| `page.click(selector)` | Click an element |
| `page.fill(selector, value)` | Fill an input |
| `page.type(selector, text)` | Type character by character |
| `page.press(selector, key)` | Press a key (Enter, Tab, etc.) |
| `page.waitForSelector(sel)` | Wait for element |
| `page.waitForURL(pattern)` | Wait for navigation |
| `page.screenshot()` | Capture screenshot buffer |
| `page.evaluate(fn)` | Run JS in page context |
| `page.textContent(sel)` | Get element text |
| `page.$$eval(sel, fn)` | Run function on all matches |
| `page.locator(sel)` | Create locator for chaining |

## Best Practices

- **One script, one job.** Keep scripts small and focused. Do one thing, log the result.
- **Use descriptive page names.** `browser.getPage("analytics")` not `browser.getPage("p1")`. Named pages persist between script runs.
- **Snapshot first, then act.** On unknown pages, run `snapshotForAI()` to discover elements before clicking or filling.
- **Use JSON output.** End scripts with `console.log(JSON.stringify(...))` for structured, parseable results.
- **Handle errors by reconnecting.** If a script fails, the page stays where it stopped. Reconnect to the same page name, take a screenshot, and check the URL/title.
- **Short timeouts for fast failure.** Use `--timeout 10` for quick checks so scripts fail fast instead of hanging on missing elements.

## Error Recovery

```bash
dev-browser --connect <<'EOF'
const page = await browser.getPage("checkout");
const path = await saveScreenshot(await page.screenshot(), "debug.png");
console.log(JSON.stringify({
  screenshot: path,
  url: page.url(),
  title: await page.title(),
}, null, 2));
EOF
```

Then read the screenshot with the Read tool to see what went wrong.
