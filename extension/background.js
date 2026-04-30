// Background service worker — only responsible for the poll schedule.
// Data is sent directly from content.js via fetch (Flask has CORS headers).

const ALARM_NAME = "claude-usage-poll";
const INTERVAL_MINUTES = 3;
const SETTINGS_URL = "https://claude.ai/settings/usage";

chrome.runtime.onInstalled.addListener(() => {
  chrome.alarms.create(ALARM_NAME, { periodInMinutes: INTERVAL_MINUTES });
  console.log("[ClaudeTracker] Installed. Polling every", INTERVAL_MINUTES, "minutes.");
});

chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== ALARM_NAME) return;
  console.log("[ClaudeTracker] Alarm fired — refreshing settings page.");

  const tabs = await chrome.tabs.query({ url: "https://claude.ai/settings/usage*" });
  if (tabs.length > 0) {
    chrome.tabs.reload(tabs[0].id);
  } else {
    chrome.tabs.create({ url: SETTINGS_URL, active: false });
  }
});
