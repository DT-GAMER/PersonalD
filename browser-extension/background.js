const ENDPOINT = "http://127.0.0.1:47833/browser/activity";

let lastSentKey = "";
let lastDriftWarningAt = 0;

async function activeTab() {
  const tabs = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
  return tabs && tabs.length > 0 ? tabs[0] : null;
}

async function sendActiveTab() {
  const tab = await activeTab();
  if (!tab || !tab.url || tab.url.startsWith("chrome://") || tab.url.startsWith("about:")) {
    return;
  }

  const key = `${tab.id}|${tab.url}|${tab.title}`;
  if (key === lastSentKey) {
    return;
  }
  lastSentKey = key;

  try {
    const response = await fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: tab.url,
        title: tab.title || "",
        browser: "browser-extension",
        tab_id: tab.id,
        active: true,
        sent_at: new Date().toISOString()
      })
    });

    const data = await response.json();
    maybeWarn(data);
  } catch (_) {
  }
}

function maybeWarn(data) {
  if (!data || !data.drifting) {
    return;
  }

  const now = Date.now();
  if (now - lastDriftWarningAt < 5 * 60 * 1000) {
    return;
  }
  lastDriftWarningAt = now;

  chrome.notifications.create({
    type: "basic",
    iconUrl: "icon.svg",
    title: "PersonalD",
    message: data.message || "Still on track?"
  });
}

chrome.tabs.onActivated.addListener(() => sendActiveTab());
chrome.tabs.onUpdated.addListener((tabId, changeInfo) => {
  if (changeInfo.status === "complete" || changeInfo.title || changeInfo.url) {
    sendActiveTab();
  }
});
chrome.windows.onFocusChanged.addListener(() => sendActiveTab());
chrome.alarms.create("personald-pulse", { periodInMinutes: 1 });
chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === "personald-pulse") {
    lastSentKey = "";
    sendActiveTab();
  }
});

sendActiveTab();
