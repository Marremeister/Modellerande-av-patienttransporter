import { logEvent, formatSimulationClock } from "./frontend_utils.js";
const socket = io("http://127.0.0.1:5001");


window.onload = () => {
  loadAvailableStrategies(); // now it uses the correct function
  document.getElementById("stopSimulationBtn").style.display = "none"; // if this element exists
};



// 🎮 Apply simulator config
function applySimulatorConfig() {
  const numTransporters = parseInt(document.getElementById("numTransporters").value);
  const requestInterval = parseInt(document.getElementById("requestInterval").value);
  const strategy = document.getElementById("strategySelect").value;

  fetch("/update_simulator_config", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ num_transporters: numTransporters, request_interval: requestInterval, strategy })
  })
    .then(res => {
      if (!res.ok) {
        throw new Error(`Server error: ${res.status}`);
      }
      return res.json();
    })
    .then(data => logEvent(data.status || "✅ Config updated"))
    .catch(err => logEvent("❌ Failed to update config: " + err, "error"));
}


// ▶️ Start
function startSimulation() {
  fetch("/toggle_simulation", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ running: true })
  })
  .then(res => res.json())
  .then(data => {
    logEvent("▶️ Simulation started");
    document.getElementById("stopSimulationBtn").style.display = "inline-block";
  });
}

// ⏹️ Stop
function stopSimulation() {
  fetch("/toggle_simulation", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ running: false })
  })
  .then(res => res.json())
  .then(data => {
    logEvent("🛑 Simulation stopped");
    document.getElementById("stopSimulationBtn").style.display = "none";
  });
}

// 🧠 Handle real-time logs
socket.on("transport_log", function (data) {
  logEvent(data.message);
});

// ⏱️ Handle simulation clock
socket.on("clock_tick", function (data) {
    document.getElementById("sim-clock").textContent = formatSimulationClock(data.simTime);
});



function loadAvailableStrategies() {
    console.log("📡 Fetching strategies...");
    fetch("/get_available_strategies")
        .then(res => res.json())
        .then(strategies => {  // ⬅️ No `.strategies` here
            console.log("📥 Received strategies:", strategies);
            const dropdown = document.getElementById("strategySelect");
            dropdown.innerHTML = "";

            strategies.forEach(strategy => {
                const option = document.createElement("option");
                option.value = strategy;
                option.textContent = strategy;
                dropdown.appendChild(option);
            });
        })
        .catch(error => console.error("❌ Error loading strategies:", error));
}


// 👇 Add this to make buttons work from HTML
window.applySimulatorConfig = applySimulatorConfig;
window.startSimulation = startSimulation;
window.stopSimulation = stopSimulation;
