const state = {
  gpsStatus: "No fix",
  driveStatus: "Idle",
  hermesStatus: "Offline",
  speed: 0,
  location: "Waiting for GPS",
  trip: "Not started",
  lastUpdate: "Never",
};

function render() {
  document.querySelector("#gps-status").textContent = state.gpsStatus;
  document.querySelector("#drive-status").textContent = state.driveStatus;
  document.querySelector("#hermes-status").textContent = state.hermesStatus;
  document.querySelector("#speed").textContent = String(Math.round(state.speed));
  document.querySelector("#location").textContent = state.location;
  document.querySelector("#trip").textContent = state.trip;
  document.querySelector("#last-update").textContent = state.lastUpdate;
}

function markUpdated() {
  state.lastUpdate = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

async function getJson(url) {
  const response = await fetch(url);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const message = body.error || body.stderr || `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return body;
}

async function postJson(url) {
  const response = await fetch(url, { method: "POST" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok || body.ok === false) {
    const message = body.message || body.error || body.stderr || `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return body;
}

async function refreshGps() {
  try {
    const gps = await getJson("/api/gps/status");
    state.gpsStatus = gps.status || "Unknown";
    state.speed = gps.speedKmh || 0;
    state.location = formatLocation(gps);
    state.lastUpdate = formatGpsTime(gps.time);
  } catch (error) {
    state.gpsStatus = "Offline";
    state.speed = 0;
    state.location = error.message;
    markUpdated();
  }
  render();
}

async function runDriveAction(action) {
  state.hermesStatus = "Sending";
  markUpdated();
  render();

  try {
    const result = await postJson(`/api/drive/action?action=${encodeURIComponent(action)}`);
    applyDriveResult(action, result);
  } catch (error) {
    state.hermesStatus = "Drive error";
    state.trip = error.message;
  }

  markUpdated();
  render();
}

function applyDriveResult(action, result) {
  const response = result.response || {};
  const message = result.message || response.message || "Done";
  state.hermesStatus = message;

  if (action === "start-trip") {
    state.driveStatus = "Trip active";
    state.trip = response.activeTripId || "Started";
  } else if (action === "stop-trip") {
    state.driveStatus = "Idle";
    state.trip = "Stopped";
  } else if (action === "food") {
    state.trip = "Food requested";
  } else if (action === "parking") {
    state.trip = "Parking requested";
  }
}

function formatLocation(gps) {
  if (typeof gps.lat !== "number" || typeof gps.lon !== "number") {
    return gps.error || "Waiting for GPS";
  }

  const sats = Number.isInteger(gps.satellitesUsed) ? ` ${gps.satellitesUsed} sat` : "";
  return `${gps.lat.toFixed(5)}, ${gps.lon.toFixed(5)}${sats}`;
}

function formatGpsTime(value) {
  if (!value) {
    return "No GPS time";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function handleAction(action) {
  markUpdated();

  if (action === "push-to-talk") {
    state.hermesStatus = "Listening";
  } else if (action === "start-trip") {
    runDriveAction(action);
    return;
  } else if (action === "stop-trip") {
    runDriveAction(action);
    return;
  } else if (action === "food" || action === "parking") {
    runDriveAction(action);
    return;
  } else if (action === "overnight") {
    runDriveAction("parking");
    return;
  } else {
    state.hermesStatus = action;
  }

  render();
}

document.querySelectorAll("[data-action]").forEach((button) => {
  button.addEventListener("click", () => {
    handleAction(button.dataset.action);
  });
});

render();
refreshGps();
window.setInterval(refreshGps, 1000);
