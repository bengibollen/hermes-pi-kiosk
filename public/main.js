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

function handleAction(action) {
  state.lastUpdate = new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

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
