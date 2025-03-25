// Core globals
const socket = io("http://127.0.0.1:5001");
let simulationRunning = false;
let transporterNodes = {};
let svg = null;

window.onload = function() {
    svg = d3.select("#hospitalMap");

    // Initialize the simulator view
    loadHospitalGraph();
    loadAvailableStrategies();
    loadTransportTable();

    // Hide stop button initially
    document.getElementById("stopSimulationBtn").style.display = "none";

    // Setup event listeners for simulation stats updates - reduced frequency
    setInterval(updateSimulationStats, 5000);

    // Add socket reconnection handler
    socket.on('connect', function() {
        console.log('✅ Socket reconnected');
        // Refresh all data on reconnect
        loadTransporters();
        loadTransportTable();
    });

    socket.on('disconnect', function() {
        console.log('❌ Socket disconnected');
        logEvent("Socket disconnected from server. Waiting for reconnection...", "error");
    });
};

// Fetch available assignment strategies for dropdown
function loadAvailableStrategies() {
    console.log("📡 Fetching strategies...");
    fetch("/get_available_strategies")
        .then(res => res.json())
        .then(strategies => {
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

// Load and draw the hospital graph
function loadHospitalGraph() {
    fetch("http://127.0.0.1:5001/get_hospital_graph")
        .then(response => response.json())
        .then(graph => {
            let nodesMap = new Map(graph.nodes.map(n => [n.id, { id: n.id, x: n.x, y: n.y }]));

            let edges = graph.edges.map(e => ({
                source: nodesMap.get(e.source),
                target: nodesMap.get(e.target),
                weight: e.distance
            }));

            // Create separate layers
            let edgeLayer = svg.append("g").attr("class", "edge-layer");
            let nodeLayer = svg.append("g").attr("class", "node-layer");
            let labelLayer = svg.append("g").attr("class", "label-layer");
            let controlLayer = svg.append("g").attr("class", "control-layer");

            // Add a simulation clock to the map
            controlLayer.append("rect")
                .attr("x", 20)
                .attr("y", 20)
                .attr("width", 140)
                .attr("height", 30)
                .attr("rx", 5)
                .attr("fill", "rgba(44, 62, 80, 0.8)");

            controlLayer.append("text")
                .attr("id", "map-clock")
                .attr("x", 35)
                .attr("y", 40)
                .attr("fill", "white")
                .attr("font-family", "monospace")
                .attr("font-size", "14px")
                .text("⏱️ 00:00:00");

            // Draw edges
            edgeLayer.selectAll("line")
                .data(edges)
                .enter()
                .append("line")
                .attr("class", "link")
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);

            // Draw edge weights
            edgeLayer.selectAll("text.edge-label")
                .data(edges)
                .enter()
                .append("text")
                .attr("class", "edge-label")
                .attr("x", d => (d.source.x + d.target.x) / 2)
                .attr("y", d => (d.source.y + d.target.y) / 2 - 5)
                .attr("text-anchor", "middle")
                .attr("fill", "black")
                .attr("font-size", "12px")
                .attr("font-weight", "bold")
                .text(d => d.weight);

            // Draw nodes
            nodeLayer.selectAll("circle")
                .data([...nodesMap.values()])
                .enter()
                .append("circle")
                .attr("class", "node")
                .attr("r", 20)
                .attr("cx", d => d.x)
                .attr("cy", d => d.y)
                .attr("data-node", d => d.id);

            // Draw node labels
            labelLayer.selectAll("text")
                .data([...nodesMap.values()])
                .enter()
                .append("text")
                .attr("class", "node-label")
                .attr("x", d => d.x)
                .attr("y", d => d.y + 5)
                .attr("text-anchor", "middle")
                .text(d => d.id.substring(0, 3)); // Show shorter department names

            // Create a separate layer for transporters to ensure they're on top
            svg.append("g").attr("id", "transporterLayer");
        });
}

// Apply simulator configuration
function applySimulatorConfig() {
    const numTransporters = parseInt(document.getElementById("numTransporters").value);
    const requestInterval = parseInt(document.getElementById("requestInterval").value);
    const strategy = document.getElementById("strategySelect").value;

    fetch("/update_simulator_config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            num_transporters: numTransporters,
            request_interval: requestInterval,
            strategy
        })
    })
    .then(res => {
        if (!res.ok) {
            throw new Error(`Server error: ${res.status}`);
        }
        return res.json();
    })
    .then(data => {
        logEvent(data.status || "✅ Configuration updated");
        // Refresh transporter visual display
        loadTransporters();
    })
    .catch(err => logEvent("❌ Failed to update config: " + err, "error"));
}

// Start the simulation
function startSimulation() {
    fetch("/toggle_simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ running: true })
    })
    .then(res => res.json())
    .then(data => {
        simulationRunning = true;
        logEvent("▶️ Simulation started");
        document.getElementById("stopSimulationBtn").style.display = "inline-block";
        document.getElementById("startSimulationBtn").style.display = "none";
    });
}

// Stop the simulation
function stopSimulation() {
    fetch("/toggle_simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ running: false })
    })
    .then(res => res.json())
    .then(data => {
        simulationRunning = false;
        logEvent("🛑 Simulation stopped");
        document.getElementById("stopSimulationBtn").style.display = "none";
        document.getElementById("startSimulationBtn").style.display = "inline-block";
    });
}

// Load all transporters
function loadTransporters() {
    // Don't load transporters if any are currently animating
    if (Object.values(transporterNodes).some(node => node && node.attr("data-animating") === "true")) {
        console.log("⏳ Skipping transporter load - animation in progress");
        return;
    }

    fetch("http://127.0.0.1:5001/get_transporters")
        .then(response => response.json())
        .then(data => {
            // Update active transporter count
            const activeCount = data.filter(t => t.status === "active").length;
            document.getElementById("activeTransporters").textContent = activeCount;

            // Create visuals for each transporter that isn't currently animating
            data.forEach(trans => {
                if (!transporterNodes[trans.name] || transporterNodes[trans.name].attr("data-animating") !== "true") {
                    let color = trans.status === "active" ? "red" : "gray";
                    createTransporterVisual(trans.name, trans.current_location, color);
                }
            });
        });
}

// Create visual representation of a transporter - simplified version
function createTransporterVisual(name, location, color = "red") {
    if (!location) return;

    // Try to find the node
    let nodeElement = document.querySelector(`[data-node='${location}']`);
    if (!nodeElement) {
        console.warn(`⚠️ Node '${location}' not found. Retrying in 300ms...`);
        setTimeout(() => createTransporterVisual(name, location, color), 300);
        return;
    }

    // If transporter exists and is animating, don't interrupt
    if (transporterNodes[name] && transporterNodes[name].attr("data-animating") === "true") {
        return;
    }

    // If transporter exists but not animating, remove it
    if (transporterNodes[name]) {
        transporterNodes[name].remove();
    }

    // Get the position from the node
    let x = parseFloat(nodeElement.getAttribute("cx"));
    let y = parseFloat(nodeElement.getAttribute("cy"));

    console.log(`🔹 Creating transporter ${name} at ${location} (${x}, ${y})`);

    // Create a simple circle for the transporter (like in main.js)
    let transporterCircle = svg.select("#transporterLayer").append("circle")
        .attr("class", "transporter")
        .attr("r", 10)
        .attr("cx", x)
        .attr("cy", y)
        .attr("fill", color)
        .attr("data-transporter", name)
        .attr("data-animating", "false");

    // Add a separate label element
    svg.select("#transporterLayer").append("text")
        .attr("class", "transporter-label")
        .attr("x", x)
        .attr("y", y - 15)
        .attr("text-anchor", "middle")
        .attr("font-size", "12px")
        .attr("fill", "#333")
        .attr("data-transporter-label", name)
        .text(name.replace("Sim_Transporter_", "T"));

    // Store only the circle in our tracking object
    transporterNodes[name] = transporterCircle;
}

// Update transporter path animation - more like main.js
function updateTransporterPath(name, path, durations) {
    if (!path || path.length < 2) {
        console.warn(`⚠️ Invalid path for ${name}:`, path);
        return;
    }

    // If transporter doesn't exist, create it
    if (!transporterNodes[name]) {
        console.log(`🔄 Creating missing transporter: ${name} at ${path[0]}`);
        createTransporterVisual(name, path[0], "red");
        transporterNodes[name].attr("data-current-location", path[0]);

        // Short delay before starting animation
        setTimeout(() => updateTransporterPath(name, path, durations), 100);
        return;
    }

    // Find the transporter circle
    let transporterCircle = transporterNodes[name];

    // Find the label for this transporter
    let transporterLabel = d3.select(`[data-transporter-label='${name}']`);

    if (!transporterCircle.node()) {
        console.error(`❌ Transporter circle for '${name}' not found in DOM`);
        return;
    }

    console.log(`🚶 Starting path animation for ${name}: ${path.join(" → ")}`);

    // Mark as currently animating
    transporterCircle.attr("data-animating", "true");
    transporterCircle.attr("data-current-location", path[0]);

    let step = 1;
    function moveStep() {
        if (step >= path.length) {
            transporterCircle.attr("data-animating", "false");
            transporterCircle.attr("data-current-location", path[path.length - 1]);
            return;
        }

        let nextNode = document.querySelector(`[data-node='${path[step]}']`);
        if (!nextNode) {
            console.error(`❌ Node '${path[step]}' not found`);
            transporterCircle.attr("data-animating", "false");
            return;
        }

        let x = parseFloat(nextNode.getAttribute("cx"));
        let y = parseFloat(nextNode.getAttribute("cy"));
        let duration = durations?.[step - 1] || 1000;

        // Animate the circle
        transporterCircle
            .transition()
            .duration(duration)
            .attr("cx", x)
            .attr("cy", y);

        // Animate the label if it exists
        if (transporterLabel.node()) {
            transporterLabel
                .transition()
                .duration(duration)
                .attr("x", x)
                .attr("y", y - 15);
        }

        // When circle completes (which should be at same time as label)
        transporterCircle
            .transition()
            .duration(duration)
            .on("end", () => {
                console.log(`✅ '${name}' moved to '${path[step]}' in ${duration}ms`);
                transporterCircle.attr("data-current-location", path[step]);
                step++;
                moveStep();
            });
    }

    moveStep();
}

// Log events to the UI
function logEvent(message, type = "info") {
    let logList = document.getElementById("logList");
    let logEntry = document.createElement("li");

    // Add timestamp for better tracking
    let timestamp = new Date().toLocaleTimeString();
    logEntry.textContent = `[${timestamp}] ${message}`;

    // Different styles for different log types
    if (type === "error") logEntry.style.color = "red";
    else if (type === "success") logEntry.style.color = "green";

    logList.appendChild(logEntry);
    logList.scrollTop = logList.scrollHeight;
}

// Format simulation time for display
function formatSimulationClock(simTime) {
    const simSeconds = Math.floor(simTime);
    const hours = Math.floor(simSeconds / 3600).toString().padStart(2, '0');
    const minutes = Math.floor((simSeconds % 3600) / 60).toString().padStart(2, '0');
    const seconds = (simSeconds % 60).toString().padStart(2, '0');
    return `⏱️ ${hours}:${minutes}:${seconds}`;
}

// Load transport table with all transport requests
function loadTransportTable() {
    fetch("/get_all_transports")
        .then(response => response.json())
        .then(data => {
            const tbody = document.querySelector("#transportTable tbody");
            tbody.innerHTML = "";

            data.forEach(req => {
                const row = document.createElement("tr");
                row.innerHTML = `
                    <td>${req.origin}</td>
                    <td>${req.destination}</td>
                    <td>${req.transport_type}</td>
                    <td>${req.urgent ? "Yes" : "No"}</td>
                    <td>${req.assigned_transporter}</td>
                    <td class="status-${req.status}">${req.status}</td>
                `;
                tbody.appendChild(row);
            });

            // Update request counts
            updateRequestCounts(data);
        });
}

// Update request counts displayed in the UI
function updateRequestCounts(requests) {
    const pendingCount = requests.filter(r => r.status === "pending").length;
    const completedCount = requests.filter(r => r.status === "completed").length;

    document.getElementById("pendingRequests").textContent = pendingCount;
    document.getElementById("completedRequests").textContent = completedCount;
}

// Update all simulation statistics - but don't interrupt animations
function updateSimulationStats() {
    if (simulationRunning) {
        // Check if any transporters are animating
        const isAnimating = Object.values(transporterNodes).some(node =>
            node && node.attr("data-animating") === "true"
        );

        if (!isAnimating) {
            // Only refresh transporters if no animations are in progress
            loadTransporters();
        }

        // Always update the table - doesn't affect animations
        loadTransportTable();
    }
}

// Socket event listeners setup
socket.on("transport_log", function(data) {
    logEvent(data.message);

    // Auto-update request counts based on log messages
    if (data.message.includes("request created") || data.message.includes("New request created")) {
        setTimeout(loadTransportTable, 300);
    }
});

socket.on("clock_tick", function(data) {
    // Update both clock displays
    const formattedTime = formatSimulationClock(data.simTime);
    document.getElementById("sim-clock").textContent = formattedTime;

    // Update the in-map clock if it exists
    if (document.getElementById("map-clock")) {
        document.getElementById("map-clock").textContent = formattedTime;
    }
});

socket.on("transporter_update", function(data) {
    console.log("🚚 Transporter update received:", data);

    // Check if we have valid data
    if (data && data.name && data.path && data.path.length >= 2) {
        try {
            updateTransporterPath(data.name, data.path, data.durations);
        } catch (err) {
            console.error("Error updating transporter path:", err);
            // Try to recover by recreating the transporter
            if (data.path && data.path.length > 0) {
                setTimeout(() => {
                    createTransporterVisual(data.name, data.path[0], "red");
                }, 500);
            }
        }
    }
});

socket.on("new_transporter", function(data) {
    console.log("🚑 New transporter added:", data);

    // Only create if not animating
    if (data && data.name && data.current_location) {
        if (!transporterNodes[data.name] || transporterNodes[data.name].attr("data-animating") !== "true") {
            createTransporterVisual(
                data.name,
                data.current_location,
                data.status === "active" ? "red" : "gray"
            );
        }
    }
});

socket.on("transport_status_update", function(data) {
    console.log("🚀 Transport status update received:", data);
    loadTransportTable();
});

socket.on("transport_completed", function(data) {
    console.log("🏁 Transport completed:", data);
    loadTransportTable();
});

// Add debugging functions
function debugTransporters() {
    console.log("🔍 Current transporterNodes:", Object.keys(transporterNodes));
    console.log("🔍 DOM transporter circles:", document.querySelectorAll('.transporter').length);

    // Check each transporter in our tracking object
    Object.keys(transporterNodes).forEach(name => {
        const circle = transporterNodes[name].node();
        const animating = transporterNodes[name].attr("data-animating");
        const currentLocation = transporterNodes[name].attr("data-current-location");
        console.log(`🔍 Transporter ${name}:`, {
            inDOM: !!circle,
            animating: animating === "true",
            currentLocation: currentLocation,
            position: circle ? { cx: circle.cx.baseVal.value, cy: circle.cy.baseVal.value } : null
        });
    });
}

function refreshAllTransporters() {
    console.log("🔄 Refreshing all transporters...");

    // Clear existing transporters
    svg.select("#transporterLayer").selectAll("*").remove();
    transporterNodes = {};

    // Reload all transporters
    loadTransporters();

    logEvent("Manually refreshed all transporters", "info");
}

// Export functions to global scope for HTML button access
window.applySimulatorConfig = applySimulatorConfig;
window.startSimulation = startSimulation;
window.stopSimulation = stopSimulation;
window.loadTransportTable = loadTransportTable;
window.debugTransporters = debugTransporters;
window.refreshAllTransporters = refreshAllTransporters;