const state = {
  gpsStatus: "No fix",
  driveStatus: "Idle",
  hermesStatus: "Offline",
  speed: 0,
  location: "Waiting for GPS",
  trip: "Not started",
  lastUpdate: "Never",
  audioBusy: false,
};

function render() {
  document.querySelector("#gps-status").textContent = state.gpsStatus;
  document.querySelector("#drive-status").textContent = state.driveStatus;
  document.querySelector("#hermes-status").textContent = state.hermesStatus;
  document.querySelector("#speed").textContent = String(Math.round(state.speed));
  document.querySelector("#location").textContent = state.location;
  document.querySelector("#trip").textContent = state.trip;
  document.querySelector("#last-update").textContent = state.lastUpdate;
  document.querySelector("#audio-test").disabled = state.audioBusy;
  document.querySelector("#play-audio").disabled = state.audioBusy;
}

function markUpdated() {
  state.lastUpdate = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

async function postJson(url) {
  const response = await fetch(url, { method: "POST" });
  const body = await response.json().catch(() => ({}));
  if (!response.ok || body.ok === false) {
    const message = body.error || body.stderr || `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return body;
}

async function runAudioLoopback() {
  state.audioBusy = true;
  state.hermesStatus = "Recording";
  state.location = "Audio test: speak now";
  markUpdated();
  render();

  try {
    await postJson("/api/audio/loopback");
    state.hermesStatus = "Played back";
    state.location = "Audio test completed";
  } catch (error) {
    state.hermesStatus = "Audio error";
    state.location = error.message;
  } finally {
    state.audioBusy = false;
    markUpdated();
    render();
  }
}

async function playLastRecording() {
  state.audioBusy = true;
  state.hermesStatus = "Playing";
  state.location = "Playing last audio test";
  markUpdated();
  render();

  try {
    await postJson("/api/audio/play");
    state.hermesStatus = "Played back";
    state.location = "Last audio test replayed";
  } catch (error) {
    state.hermesStatus = "Audio error";
    state.location = error.message;
  } finally {
    state.audioBusy = false;
    markUpdated();
    render();
  }
}

function handleAction(action) {
  markUpdated();

  if (action === "push-to-talk") {
    state.hermesStatus = "Listening";
  } else if (action === "audio-test") {
    runAudioLoopback();
    return;
  } else if (action === "play-audio") {
    playLastRecording();
    return;
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
