const $ = (id) => document.getElementById(id);

const apiBaseInput = $("apiBase");
const adminKeyInput = $("adminKey");
const modelInput = $("model");
const systemInput = $("system");
const promptInput = $("prompt");
const showPayloadInput = $("showPayload");
const sendBtn = $("sendBtn");
const statusEl = $("status");
const responseText = $("responseText");
const responseBox = $("responseBox");
const headersBox = $("headersBox");
const payloadBox = $("payloadBox");
const statsBox = $("statsBox");
const checkHealth = $("checkHealth");
const apiStatus = $("apiStatus");
const refreshStats = $("refreshStats");
const runtimeConfig = window.RUNTIME_CONFIG || {};

function normalizedBaseUrl() {
  return apiBaseInput.value.trim().replace(/\/$/, "");
}

function setStatus(message, isError) {
  statusEl.textContent = message;
  statusEl.className = `hint status${isError ? " error" : ""}`;
}

function safeParse(text) {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function extractAssistantReply(json) {
  if (!json || typeof json !== "object") return null;
  if (json.message && typeof json.message.content === "string") {
    return json.message.content;
  }
  if (Array.isArray(json.choices) && json.choices[0]?.message?.content) {
    return json.choices[0].message.content;
  }
  return null;
}

async function checkApiHealth() {
  const base = normalizedBaseUrl();
  if (!base) {
    apiStatus.textContent = "Missing base URL";
    return;
  }
  apiStatus.textContent = "Checking...";
  try {
    const response = await fetch(`${base}/healthz`);
    if (!response.ok) {
      throw new Error("API unreachable");
    }
    const payload = await response.json();
    apiStatus.textContent = payload.status ? `OK (${payload.status})` : "OK";
  } catch {
    apiStatus.textContent = "Not reachable";
  }
}

async function sendRequest() {
  const base = normalizedBaseUrl();
  const model = modelInput.value.trim();
  const system = systemInput.value.trim();
  const prompt = promptInput.value.trim();

  if (!base) return setStatus("Base URL required", true);
  if (!model) return setStatus("Model is required", true);
  if (!prompt) return setStatus("User message is required", true);

  const messages = [];
  if (system) messages.push({ role: "system", content: system });
  messages.push({ role: "user", content: prompt });

  const payload = { model, messages };

  sendBtn.disabled = true;
  sendBtn.textContent = "Sending...";
  setStatus("Sending...", false);
  responseBox.textContent = "Waiting for response...";
  headersBox.textContent = "Waiting for response...";
  payloadBox.textContent = "Waiting for response...";
  responseText.textContent = "Waiting for response...";

  try {
    const res = await fetch(`${base}/v1/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const text = await res.text();
    const json = safeParse(text);

    responseBox.textContent = json ? JSON.stringify(json, null, 2) : text;
    responseText.textContent = extractAssistantReply(json) || text;

    const headerMap = {};
    res.headers.forEach((value, key) => {
      headerMap[key] = value;
    });

    headersBox.textContent = JSON.stringify(
      {
        status: res.status,
        "x-pii-redacted": headerMap["x-pii-redacted"],
        "x-original-length": headerMap["x-original-length"],
        "x-masked-length": headerMap["x-masked-length"],
        "x-request-id": headerMap["x-request-id"],
        "x-latency-seconds": headerMap["x-latency-seconds"],
        all: headerMap,
      },
      null,
      2
    );

    payloadBox.textContent = showPayloadInput.checked
      ? JSON.stringify(payload, null, 2)
      : "hidden";

    setStatus(res.ok ? "Success" : "Upstream error", !res.ok);
    fetchStats();
  } catch (error) {
    setStatus(`Error: ${error}`, true);
    responseBox.textContent = "Request failed.";
    headersBox.textContent = "Request failed.";
    payloadBox.textContent = "";
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = "Send request";
  }
}

async function fetchStats() {
  const base = normalizedBaseUrl();
  if (!base) return;

  const adminKey = adminKeyInput.value.trim();
  statsBox.textContent = "Loading...";

  try {
    const headers = adminKey ? { "X-Admin-Key": adminKey } : {};
    const res = await fetch(`${base}/admin/stats`, { headers });
    const text = await res.text();
    const json = safeParse(text);
    statsBox.textContent = json ? JSON.stringify(json, null, 2) : text;
  } catch (error) {
    statsBox.textContent = `Failed to load stats: ${error}`;
  }
}

(() => {
  if (!apiBaseInput.value) {
    try {
      apiBaseInput.value = runtimeConfig.API_BASE_URL || window.location.origin;
    } catch {
      apiBaseInput.value = runtimeConfig.API_BASE_URL || "http://127.0.0.1:8000";
    }
  }

  if (runtimeConfig.DEFAULT_MODEL) {
    modelInput.value = runtimeConfig.DEFAULT_MODEL;
  }

  if (runtimeConfig.ADMIN_KEY) {
    adminKeyInput.value = runtimeConfig.ADMIN_KEY;
  }
})();

checkHealth.addEventListener("click", checkApiHealth);
sendBtn.addEventListener("click", sendRequest);
refreshStats.addEventListener("click", fetchStats);
