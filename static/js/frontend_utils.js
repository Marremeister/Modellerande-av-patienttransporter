// frontend_utils.js

export function logEvent(message, type = "info") {
    const logList = document.getElementById("logList");
    const entry = document.createElement("li");

    const timestamp = new Date().toLocaleTimeString();
    entry.textContent = `[${timestamp}] ${message}`;

    if (type === "error") entry.style.color = "red";
    else if (type === "success") entry.style.color = "green";

    logList.appendChild(entry);
    logList.scrollTop = logList.scrollHeight;
}

export function formatSimulationClock(simTime) {
    const simSeconds = Math.floor(simTime);
    const hours = Math.floor(simSeconds / 3600).toString().padStart(2, '0');
    const minutes = Math.floor((simSeconds % 3600) / 60).toString().padStart(2, '0');
    const seconds = (simSeconds % 60).toString().padStart(2, '0');
    return `⏱️ Simulation Time: ${hours}:${minutes}:${seconds}`;
}
