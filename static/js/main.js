var svg = d3.select("svg"), width = 1400, height = 1000;
        var transporters = {}, transportRequests = {}, transporterNodes = {};
        var socket = io("http://127.0.0.1:5001");

        function loadHospitalGraph() {
    fetch("http://127.0.0.1:5001/get_hospital_graph")
        .then(response => response.json())
        .then(graph => {
            let nodesMap = new Map(graph.nodes.map(n => [n.id, { id: n.id, x: n.x, y: n.y }]));

            let edges = graph.edges.map(e => ({
                source: nodesMap.get(e.source),
                target: nodesMap.get(e.target),
                weight: e.distance  // 🔹 Store weight for display
            }));

            // Draw edges (lines)
            svg.append("g").selectAll("line").data(edges).enter().append("line")
                .attr("class", "link")
                .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x).attr("y2", d => d.target.y);

            // Draw edge weights (text)
            svg.append("g").selectAll("text.edge-label").data(edges).enter().append("text")
                .attr("class", "edge-label")
                .attr("x", d => (d.source.x + d.target.x) / 2)  // 🔹 Middle of the edge
                .attr("y", d => (d.source.y + d.target.y) / 2 - 5)  // 🔹 Slightly above
                .attr("text-anchor", "middle")
                .attr("fill", "black")
                .attr("font-size", "12px")
                .attr("font-weight", "bold")
                .text(d => d.weight);  // 🔹 Display weight

            // Draw nodes (circles)
            svg.append("g").selectAll("circle").data([...nodesMap.values()]).enter().append("circle")
                .attr("class", "node").attr("r", 20)
                .attr("cx", d => d.x).attr("cy", d => d.y)
                .attr("data-node", d => d.id);

            // Draw node labels (text)
            svg.append("g").selectAll("text").data([...nodesMap.values()]).enter().append("text")
                .attr("x", d => d.x + 10).attr("y", d => d.y - 10).text(d => d.id);
        });
}
        function deployOptimization() {
    fetch("http://127.0.0.1:5001/set_strategy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy: "ilp" })
    })
    .then(() => {
        return fetch("http://127.0.0.1:5001/deploy_strategy_assignment", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
    })
    .then(response => response.json())
    .then(data => {
        logEvent("✅ Optimization Strategy Deployed! Transporters are moving.", "success");
        loadTransportRequests();
    })
    .catch(error => logEvent(`❌ Optimization Error: ${error}`, "error"));
}

function deployRandomness() {
    fetch("http://127.0.0.1:5001/set_strategy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy: "random" })
    })
    .then(() => {
        return fetch("http://127.0.0.1:5001/deploy_strategy_assignment", {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
    })
    .then(response => response.json())
    .then(data => {
        logEvent("🎲 Random Assignment Strategy Deployed!", "success");
        loadTransportRequests();
    })
    .catch(error => logEvent(`❌ Randomization Error: ${error}`, "error"));
}


        function addTransporter() {
    let transporterName = document.getElementById("transporterName").value.trim();
    if (!transporterName) {
        logEvent("❌ Please enter a transporter name.", "error");
        return;
    }

    fetch("http://127.0.0.1:5001/add_transporter", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: transporterName })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            logEvent(`❌ Error: ${data.error}`, "error");
        } else {
            logEvent(`✅ Transporter ${transporterName} added successfully!`, "success");
            document.getElementById("transporterName").value = ""; // Clear the input

            // ❌ DO NOT call loadTransporters()
            // ✅ The socket listener will handle visuals!
        }
    })
    .catch(error => logEvent(`❌ Error: ${error}`, "error"));
}

        function returnHome() {
    const selectedTransporter = document.getElementById("transporterSelect").value;
    if (!selectedTransporter) {
        logEvent("❌ Please select a transporter first.", "error");
        return;
    }

    fetch("/return_home", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transporter: selectedTransporter })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            logEvent(`❌ Error: ${data.error}`, "error");
        }
    })
    .catch(error => logEvent(`❌ Error: ${error}`, "error"));
}

function setTransporterStatus() {
    let transporterName = document.getElementById("transporterSelect").value;
    let status = document.getElementById("statusDropdown").value;

    if (!transporterName) {
        logEvent("❌ Please select a transporter.", "error");
        return;
    }

    fetch("/set_transporter_status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transporter: transporterName, status })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            logEvent(`❌ Error: ${data.error}`, "error");
        }


        loadTransporters();
    })
    .catch(error => logEvent(`❌ Error: ${error}`, "error"));
}

function simulateOptimally() {
        fetch("/set_strategy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ strategy: "ilp" })
        }).then(() => {
            startSimulation("ILP Optimizer");
        });
    }

    function simulateRandomly() {
        fetch("/set_strategy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ strategy: "random" })
        }).then(() => {
            startSimulation("Random Assignment");
        });
    }

    function startSimulation(label) {
        fetch("/toggle_simulation", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ running: true })
        })
        .then(res => res.json())
        .then(data => {
            logEvent(`🎮 Started simulation using: ${label}`);
            document.getElementById("stopSimulationBtn").style.display = "inline-block";
        });
    }

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

function createTransporterVisual(name, location, color = "red") {
    // ✅ Prevent duplicates
    if (transporterNodes[name]) {
        console.warn(`⚠️ Transporter '${name}' already visualized. Skipping duplicate.`);
        return;
    }

    let nodeElement = document.querySelector(`[data-node='${location}']`);
    if (!nodeElement) {
        console.error(`❌ Error: Node '${location}' not found for transporter '${name}'.`);
        return;
    }

    let x = parseFloat(nodeElement.getAttribute("cx"));
    let y = parseFloat(nodeElement.getAttribute("cy"));

    console.log(`🚛 Creating transporter ${name} at (${x}, ${y})`);

    transporterNodes[name] = svg.append("circle")
        .attr("class", "transporter")
        .attr("r", 10)
        .attr("cx", x)
        .attr("cy", y)
        .attr("fill", color)
        .attr("data-transporter", name);
}


       function loadTransporters() {
    // 🔁 Clear previous transporter visuals
    for (let name in transporterNodes) {
        transporterNodes[name].remove();
    }
    transporterNodes = {};

    fetch("http://127.0.0.1:5001/get_transporters")
        .then(response => response.json())
        .then(data => {
            let select = document.getElementById("transporterSelect");
            select.innerHTML = "";

            data.forEach(trans => {
                // Only add active transporters to dropdown
                if (trans.status === "active") {
                    let option = document.createElement("option");
                    option.value = trans.name;
                    option.textContent = trans.name;
                    select.appendChild(option);
                }

                // Update transporter status visually
                let color = trans.status === "active" ? "red" : "gray";
                createTransporterVisual(trans.name, trans.current_location, color);
            });
        });
}


        function loadDepartmentDropdowns() {
    fetch("http://127.0.0.1:5001/get_hospital_graph")
        .then(response => response.json())
        .then(graph => {
            console.log("🏥 Loaded hospital graph:", graph); // 🔹 Debugging

            let originDropdown = document.getElementById("originDropdown");
            let destinationDropdown = document.getElementById("destinationDropdown");

            originDropdown.innerHTML = "";
            destinationDropdown.innerHTML = "";

            if (!graph.nodes || graph.nodes.length === 0) {
                console.error("❌ No nodes found in hospital graph!");
                return;
            }

            graph.nodes.forEach(node => {
                let option1 = document.createElement("option");
                option1.value = node.id;
                option1.textContent = node.id;
                originDropdown.appendChild(option1);

                let option2 = document.createElement("option");
                option2.value = node.id;
                option2.textContent = node.id;
                destinationDropdown.appendChild(option2);
            });

            console.log("✅ Dropdowns populated successfully!");
        })
        .catch(error => console.error("❌ Error fetching departments:", error));
}


        function createRequest() {
    let origin = document.getElementById("originDropdown").value;
    let destination = document.getElementById("destinationDropdown").value;
    let transportType = document.getElementById("typeDropdown").value;
    let urgent = document.getElementById("urgentDropdown").value === "true";

    if (!origin || !destination || origin === destination) {
        logEvent("❌ Please select a valid origin and destination.", "error");
        return;
    }

    fetch("/frontend_transport_request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ origin, destination, transport_type: transportType, urgent })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            logEvent(`❌ Error: ${data.error}`, "error");
        } else {
            loadTransportRequests();
        }
    })
    .catch(error => logEvent(`❌ Error: ${error}`, "error"));
}




function removeRequest(requestKey) {
    fetch("http://127.0.0.1:5001/remove_transport_request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ requestKey })
    })
    .then(response => response.json())
    .then(data => {
        console.log("✅ Request removed:", data);
        loadTransportRequests();  // 🔹 Refresh dropdown after removal
    })
    .catch(error => console.error("❌ Error:", error));
}

socket.on("transport_completed", function (data) {
    console.log("🚀 Transport completed:", data);
    loadTransportRequests();  // ✅ Only do UI refresh
});

socket.on("transporter_status_update", function (data) {
    console.log("🔄 Transporter status update:", data);
    loadTransporters(); // Refresh transporter list
});

socket.on("transport_log", function (data) {
    logEvent(data.message);
});

socket.on("clock_tick", function (data) {
  const simSeconds = Math.floor(data.simTime);
  const hours = Math.floor(simSeconds / 3600).toString().padStart(2, '0');
  const minutes = Math.floor((simSeconds % 3600) / 60).toString().padStart(2, '0');
  const seconds = (simSeconds % 60).toString().padStart(2, '0');

  document.getElementById("sim-clock").textContent =
    `⏱️ Simulation Time: ${hours}:${minutes}:${seconds}`;
});



socket.on("new_transporter", function (data) {
    console.log("🚑 New transporter added:", data);

    // ✅ Only add the new one visually (no full redraw)
    let color = data.status === "active" ? "red" : "gray";
    createTransporterVisual(data.name, data.current_location, color);

    // ✅ Also update the transporter dropdown
    if (data.status === "active") {
        let select = document.getElementById("transporterSelect");
        let option = document.createElement("option");
        option.value = data.name;
        option.textContent = data.name;
        select.appendChild(option);
    }
});

socket.on("transporter_update", function (data) {
    console.log("🚚 Transporter update received:", data);
    updateTransporterPath(data.name, data.path, data.durations);
});


socket.on("transport_status_update", function (data) {
    console.log("🚀 Transport status update received:", data);

    let requestKey = `${data.request.origin}-${data.request.destination}`;

    // 🔥 Remove from dropdown immediately
    let select = document.getElementById("requestSelect");
    let options = select.options;

    for (let i = 0; i < options.length; i++) {
        if (options[i].value === requestKey) {
            console.log(`❌ Removing request: ${requestKey}`);
            select.remove(i);
            break;
        }
    }

    // 🔄 Auto-refresh dropdowns
    loadTransportRequests();
});



socket.on("transport_assigned", function (data) {
    console.log("📝 Transport assigned:", data);

    let logList = document.getElementById("logList");
    let logEntry = document.createElement("li");
    logEntry.textContent = `✅ ${data.transporter} assigned to transport ${data.transport_type} from ${data.origin} to ${data.destination}. Urgent: ${data.urgent ? "Yes" : "No"}`;

    logList.appendChild(logEntry);
    logList.scrollTop = logList.scrollHeight; // 🔄 Auto-scroll to latest log
});



        function loadTransportRequests() {
    fetch("http://127.0.0.1:5001/get_transport_requests")
        .then(response => response.json())
        .then(data => {
            let select = document.getElementById("requestSelect");
            select.innerHTML = ""; // Clear existing options

            console.log("🔄 Loading Transport Requests:", data);

            // Only load "pending" requests
            data.pending.forEach(req => {
                let option = document.createElement("option");
                option.value = `${req.origin}-${req.destination}`;
                option.textContent = `${req.transport_type} from ${req.origin} to ${req.destination}`;
                select.appendChild(option);
                transportRequests[option.value] = req;
            });

            console.log("✅ Requests loaded into dropdown.");
        })
        .catch(error => console.error("❌ Error loading transport requests:", error));
}






       function createTransporterVisual(name, location, color = "red") {
    if (!location) return;

    let nodeElement = document.querySelector(`[data-node='${location}']`);
    if (!nodeElement) {
        console.warn(`⚠️ Node '${location}' not found. Retrying in 100ms...`);
        setTimeout(() => createTransporterVisual(name, location, color), 100);
        return;
    }

    if (transporterNodes[name]) return;

    let x = parseFloat(nodeElement.getAttribute("cx"));
    let y = parseFloat(nodeElement.getAttribute("cy"));

    transporterNodes[name] = svg.append("circle")
        .attr("class", "transporter")
        .attr("r", 10)
        .attr("cx", x)
        .attr("cy", y)
        .attr("fill", color)
        .attr("data-transporter", name);
}



        function updateTransporterPath(name, path, durations) {
    if (!path || path.length < 2) return;

    let transporterElement = d3.select(`[data-transporter='${name}']`);
    if (transporterElement.empty()) {
        console.error(`❌ Transporter '${name}' not found in DOM`);
        return;
    }

    let step = 1;
    function moveStep() {
        if (step >= path.length) return;

        let nextNode = document.querySelector(`[data-node='${path[step]}']`);
        if (!nextNode) {
            console.error(`❌ Node '${path[step]}' not found`);
            return;
        }

        let x = parseFloat(nextNode.getAttribute("cx"));
        let y = parseFloat(nextNode.getAttribute("cy"));
        let duration = durations?.[step - 1] || 1000;

        transporterElement
            .transition()
            .duration(duration)
            .attr("cx", x)
            .attr("cy", y)
            .on("end", () => {
                console.log(`✅ '${name}' moved to '${path[step]}' in ${duration}ms`);
                step++;
                moveStep();
            });
    }

    moveStep();
}


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
    logList.scrollTop = logList.scrollHeight;  // Auto-scroll to latest log
}


        function initiateTransport() {
    let transporterName = document.getElementById("transporterSelect").value;
    let requestValue = document.getElementById("requestSelect").value;
    let requestObj = transportRequests[requestValue];

    if (!transporterName || !requestObj) {
        logEvent("❌ Please select both a transporter and a request.", "error");
        return;
    }

    // 🧼 Removed all logEvent calls below
    fetch("/assign_transport", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            transporter: transporterName,
            origin: requestObj.origin,
            destination: requestObj.destination,
            transport_type: requestObj.transport_type,
            urgent: requestObj.urgent
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            logEvent(`❌ Error: ${data.error}`, "error");
        } else {
            loadTransportRequests();
        }
    })
    .catch(error => logEvent(`❌ Error: ${error}`, "error"));
}





        window.onload = function () {
            loadHospitalGraph();
            loadTransporters();
            loadTransportRequests();
            loadDepartmentDropdowns();
        };

        let simulationRunning = false;

document.getElementById("toggleSimulationBtn").addEventListener("click", () => {
    simulationRunning = !simulationRunning;
    fetch("/toggle_simulation", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ running: simulationRunning })
    })
    .then(res => res.json())
    .then(data => {
        console.log("🎮 Simulation:", data.status);
        document.getElementById("toggleSimulationBtn").innerText = simulationRunning ? "Stop Simulation" : "Start Simulation";
    });
});