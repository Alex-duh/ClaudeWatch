// Scrapes Claude usage from claude.ai/settings/usage and POSTs to localhost:9999.

const SERVER_URL = "http://localhost:9999/usage";
const RETRY_INTERVAL_MS = 1500;
const MAX_RETRIES = 8;

function parseUsage() {
  const text = document.body.innerText;

  const result = {
    sessionPct: null,
    sessionReset: null,
    weeklyPct: null,
    weeklyReset: null,
    scrapedAt: new Date().toISOString(),
  };

  // Isolate the "Current session" block (everything up to the next major heading)
  const sessionBlock = text.match(
    /Current session([\s\S]{0,400}?)(?:Weekly limits|Claude Design|Additional features)/i
  );
  if (sessionBlock) {
    const pct   = sessionBlock[1].match(/(\d+)%\s*used/i);
    const reset = sessionBlock[1].match(/Resets\s+in\s+([^\n]+)/i);
    if (pct)   result.sessionPct   = parseInt(pct[1], 10);
    if (reset) result.sessionReset = "in " + reset[1].trim();
  }

  // Isolate the "Weekly limits" block
  const weeklyBlock = text.match(
    /Weekly limits([\s\S]{0,400}?)(?:Claude Design|Additional features|$)/i
  );
  if (weeklyBlock) {
    const pct   = weeklyBlock[1].match(/(\d+)%\s*used/i);
    // "Resets Thu 12:00 AM"  (no "in", just a day/time)
    const reset = weeklyBlock[1].match(/Resets\s+([^\n]+)/i);
    if (pct)   result.weeklyPct   = parseInt(pct[1], 10);
    if (reset) result.weeklyReset = reset[1].trim();
  }

  return result;
}

function hasData(d) {
  return d.sessionPct !== null || d.weeklyPct !== null;
}

async function scrapeAndSend() {
  for (let i = 0; i < MAX_RETRIES; i++) {
    const data = parseUsage();

    if (hasData(data)) {
      console.log("[ClaudeTracker] Found data:", data);
      try {
        const r = await fetch(SERVER_URL, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(data),
        });
        console.log("[ClaudeTracker] Sent. Status:", r.status);
      } catch (err) {
        console.warn("[ClaudeTracker] Server unreachable — is app.py running?", err.message);
      }
      return;
    }

    console.log(`[ClaudeTracker] Attempt ${i + 1}: no data yet, retrying…`);
    await new Promise(r => setTimeout(r, RETRY_INTERVAL_MS));
  }

  console.warn("[ClaudeTracker] Could not find usage data. Page snippet:",
    document.body.innerText.slice(0, 400));
}

scrapeAndSend();

// Catch React SPA in-page navigation
let _lastHref = location.href;
new MutationObserver(() => {
  if (location.href !== _lastHref) {
    _lastHref = location.href;
    if (location.pathname.startsWith("/settings/usage")) {
      console.log("[ClaudeTracker] SPA nav detected — scraping");
      scrapeAndSend();
    }
  }
}).observe(document.body, { childList: true, subtree: true });
