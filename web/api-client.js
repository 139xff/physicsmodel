async function parseJsonResponse(response, fallbackMessage) {
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`${fallbackMessage}: ${response.status} ${detail}`);
  }
  return response.json();
}

async function callDesktopBridge(method, payload = null) {
  const bridge = window.emWorkbenchBridgeReady
    ? await window.emWorkbenchBridgeReady
    : window.emWorkbenchBridge;
  if (!bridge || typeof bridge[method] !== "function") {
    return null;
  }

  const rawResult = await bridge[method](payload === null ? "" : JSON.stringify(payload));
  return typeof rawResult === "string" ? JSON.parse(rawResult) : rawResult;
}

export async function getConfig() {
  const bridgeResult = await callDesktopBridge("config");
  if (bridgeResult !== null) {
    return bridgeResult;
  }

  const response = await fetch("/api/config", {
    headers: { Accept: "application/json" },
  });
  return parseJsonResponse(response, "Configuration load failed");
}

export async function listPresets() {
  const bridgeResult = await callDesktopBridge("listPresets");
  if (bridgeResult !== null) {
    return bridgeResult;
  }

  const response = await fetch("/api/presets", {
    headers: { Accept: "application/json" },
  });
  return parseJsonResponse(response, "Preset list load failed");
}

export async function getPreset(presetId) {
  const bridgeResult = await callDesktopBridge("getPreset", { preset_id: presetId });
  if (bridgeResult !== null) {
    return bridgeResult;
  }

  const response = await fetch(`/api/presets/${encodeURIComponent(presetId)}`, {
    headers: { Accept: "application/json" },
  });
  return parseJsonResponse(response, "Preset load failed");
}

export async function evaluateField(request) {
  const bridgeResult = await callDesktopBridge("evaluateField", request);
  if (bridgeResult !== null) {
    return bridgeResult;
  }

  const response = await fetch("/api/field/evaluate", {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return parseJsonResponse(response, "Field evaluation failed");
}
