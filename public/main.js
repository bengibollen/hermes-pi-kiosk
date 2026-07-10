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
    state.driveStatus = "Trip active";
    state.trip = "Started locally";
  } else if (action === "mark-stop") {
    state.driveStatus = "Stopped";
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
