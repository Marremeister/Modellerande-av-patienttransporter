/**
 * hospital-transport-utils.js
 * Shared utilities for hospital transport visualization system
 */

// Namespace for our utilities
const HospitalTransport = {
  /**
   * Configuration and state
   */
  config: {
    socketUrl: "http://127.0.0.1:5001",
    defaultMapWidth: 1400,
    defaultMapHeight: 1000,
    animationDuration: 1000, // Default animation duration in ms
    logMaxEntries: 100, // Maximum number of log entries to keep
    refreshInterval: 5000, // Interval for auto-refresh in ms
  },

  state: {
    socket: null,
    graph: null,
    transporters: {},
    requests: {},
    simulationRunning: false,
    currentView: "full", // "full", "cluster", or "department"
    currentCluster: null,
    animatingTransporters: new Set(), // Track which transporters are currently animating
    logBuffer: []
  },

  /**
   * Socket connection and event handling
   */
  socket: {
    initialize: function(url = null) {
      if (HospitalTransport.state.socket) {
        console.warn("Socket already initialized");
        return HospitalTransport.state.socket;
      }

      const socketUrl = url || HospitalTransport.config.socketUrl;
      HospitalTransport.state.socket = io(socketUrl);

      // Setup core event listeners
      HospitalTransport._setupSocketListeners();

      console.log("Socket initialized to:", socketUrl);
      return HospitalTransport.state.socket;
    },

    emit: function(event, data) {
      if (!HospitalTransport.state.socket) {
        console.error("Socket not initialized. Call HospitalTransport.socket.initialize() first");
        return;
      }

      HospitalTransport.state.socket.emit(event, data);
    },

    onEvent: function(event, callback) {
      if (!HospitalTransport.state.socket) {
        console.error("Socket not initialized. Call HospitalTransport.socket.initialize() first");
        return;
      }

      HospitalTransport.state.socket.on(event, callback);
    }
  },

  /**
   * Graph visualization utilities
   */
  graph: {
    load: function(callback) {
      fetch(`${HospitalTransport.config.socketUrl}/get_hospital_graph`)
        .then(response => response.json())
        .then(graph => {
          HospitalTransport.state.graph = graph;
          if (callback) callback(graph);
        })
        .catch(error => {
          console.error("Error loading hospital graph:", error);
          HospitalTransport.log.add("Error loading hospital graph", "error");
        });
    },

    render: function(svgSelector, options = {}) {
      const svg = d3.select(svgSelector);

      if (!HospitalTransport.state.graph) {
        console.error("Graph not loaded. Call HospitalTransport.graph.load() first");
        return;
      }

      // Clear existing elements if specified
      if (options.clear !== false) {
        svg.selectAll("*").remove();
      }

      const graph = HospitalTransport.state.graph;
      const nodesMap = new Map(graph.nodes.map(n => [n.id, { id: n.id, x: n.x, y: n.y }]));

      const edges = graph.edges.map(e => ({
        source: nodesMap.get(e.source),
        target: nodesMap.get(e.target),
        weight: e.distance
      }));

      // Default options
      const defaults = {
        showEdgeWeights: true,
        nodeRadius: 20,
        nodeColor: "#90CAF9",
        edgeColor: "#bbb",
        labelOffset: { x: 10, y: -10 },
        groups: null // Optional grouping info for nodes
      };

      // Merge options with defaults
      const settings = {...defaults, ...options};

      // Create layer groups
      const edgeLayer = svg.append("g").attr("class", "edge-layer");
      const nodeLayer = svg.append("g").attr("class", "node-layer");
      const labelLayer = svg.append("g").attr("class", "label-layer");
      const transporterLayer = svg.append("g").attr("class", "transporter-layer");

      // Draw edges (connections)
      edgeLayer.selectAll("line")
        .data(edges)
        .enter()
        .append("line")
        .attr("class", "link")
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y)
        .style("stroke", settings.edgeColor)
        .style("stroke-width", "2px");

      // Draw edge weights if enabled
      if (settings.showEdgeWeights) {
        edgeLayer.selectAll("text.edge-label")
          .data(edges)
          .enter()
          .append("text")
          .attr("class", "edge-label")
          .attr("x", d => (d.source.x + d.target.x) / 2)
          .attr("y", d => (d.source.y + d.target.y) / 2 - 5)
          .attr("text-anchor", "middle")
          .attr("fill", "#777")
          .attr("font-size", "12px")
          .attr("font-weight", "bold")
          .text(d => d.weight);
      }

      // Draw nodes (departments)
      const nodes = nodeLayer.selectAll("circle")
        .data([...nodesMap.values()])
        .enter()
        .append("circle")
        .attr("class", "node")
        .attr("r", settings.nodeRadius)
        .attr("cx", d => d.x)
        .attr("cy", d => d.y)
        .attr("data-node", d => d.id)
        .style("fill", d => {
          // If groups are specified, color by group
          if (settings.groups && settings.groups[d.id]) {
            return settings.groups[d.id].color || settings.nodeColor;
          }
          return settings.nodeColor;
        })
        .style("stroke", "#2c3e50")
        .style("stroke-width", "2px");

      // Add node interactions if any
      if (options.onNodeClick) {
        nodes.style("cursor", "pointer")
          .on("click", (event, d) => options.onNodeClick(d));
      }

      // Draw node labels
      labelLayer.selectAll("text")
        .data([...nodesMap.values()])
        .enter()
        .append("text")
        .attr("class", "node-label")
        .attr("x", d => d.x + settings.labelOffset.x)
        .attr("y", d => d.y + settings.labelOffset.y)
        .text(d => {
          // Show short or full node name based on settings
          if (settings.shortLabels) {
            return d.id.substring(0, 3);
          }
          return d.id;
        })
        .style("font-size", "12px")
        .style("font-weight", "bold")
        .style("fill", "#333");

      // Return created layers for future reference
      return {
        edgeLayer,
        nodeLayer,
        labelLayer,
        transporterLayer,
        nodesMap
      };
    },

    getNodePosition: function(nodeId) {
      if (!HospitalTransport.state.graph) {
        console.error("Graph not loaded. Call HospitalTransport.graph.load() first");
        return null;
      }

      const node = HospitalTransport.state.graph.nodes.find(n => n.id === nodeId);
      if (!node) {
        console.warn(`Node ${nodeId} not found in graph`);
        return null;
      }

      return { x: node.x, y: node.y };
    }
  },

  /**
   * Transporter visualization and management
   */
  transporters: {
    load: function(callback) {
      fetch(`${HospitalTransport.config.socketUrl}/get_transporters`)
        .then(response => response.json())
        .then(transporters => {
          // Update state with transporters
          transporters.forEach(t => {
            HospitalTransport.state.transporters[t.name] = t;
          });

          if (callback) callback(transporters);
        })
        .catch(error => {
          console.error("Error loading transporters:", error);
          HospitalTransport.log.add("Error loading transporters", "error");
        });
    },

    render: function(svgSelector, options = {}) {
      const svg = d3.select(svgSelector);
      const transporterLayer = svg.select(".transporter-layer");

      if (!transporterLayer.empty()) {
        // Clear existing transporters if requested
        if (options.clear) {
          transporterLayer.selectAll("*").remove();
        }
      }

      // Create transporters in the SVG
      const transporters = Object.values(HospitalTransport.state.transporters);

      transporters.forEach(transporter => {
        // Skip if transporter is animating
        if (HospitalTransport.state.animatingTransporters.has(transporter.name)) {
          return;
        }

        const nodePosition = HospitalTransport.graph.getNodePosition(transporter.current_location);
        if (!nodePosition) return;

        // Remove existing transporter if any
        transporterLayer.selectAll(`[data-transporter="${transporter.name}"]`).remove();
        transporterLayer.selectAll(`[data-transporter-label="${transporter.name}"]`).remove();

        // Create transporter circle
        const color = transporter.status === "active" ? "#FF5252" : "#A9A9A9";
        const radius = options.radius || 15;

        const transporterCircle = transporterLayer.append("circle")
          .attr("class", "transporter")
          .attr("r", radius)
          .attr("cx", nodePosition.x)
          .attr("cy", nodePosition.y)
          .attr("fill", color)
          .attr("stroke", "white")
          .attr("stroke-width", 2)
          .attr("data-transporter", transporter.name)
          .attr("data-animating", "false")
          .attr("data-current-location", transporter.current_location);

        // Add label if enabled
        if (options.showLabels !== false) {
          transporterLayer.append("text")
            .attr("class", "transporter-label")
            .attr("x", nodePosition.x)
            .attr("y", nodePosition.y - 20)
            .attr("text-anchor", "middle")
            .attr("font-size", "14px")
            .attr("font-weight", "bold")
            .attr("fill", "#333")
            .attr("stroke", "white")
            .attr("stroke-width", "0.5")
            .attr("data-transporter-label", transporter.name)
            .text(transporter.name.replace(/^Sim_Transporter_/, "T"));
        }
      });

      return transporterLayer;
    },

    animatePath: function(transporterName, path, durations, svgSelector = null) {
      // If no SVG selector provided, try to find SVG by default
      const svg = svgSelector ? d3.select(svgSelector) : d3.select("svg");

      if (svg.empty()) {
        console.error("SVG element not found for transporter animation");
        return;
      }

      // Validate path
      if (!path || path.length < 2) {
        console.warn(`Invalid path for ${transporterName}:`, path);
        return;
      }

      // Mark transporter as animating
      HospitalTransport.state.animatingTransporters.add(transporterName);

      // Get transporter elements
      const transporterCircle = svg.select(`[data-transporter="${transporterName}"]`);
      const transporterLabel = svg.select(`[data-transporter-label="${transporterName}"]`);

      if (transporterCircle.empty()) {
        console.error(`Transporter ${transporterName} not found in SVG`);
        HospitalTransport.state.animatingTransporters.delete(transporterName);
        return;
      }

      // Mark as animating
      transporterCircle.attr("data-animating", "true");
      transporterCircle.attr("data-current-location", path[0]);

      // Animation function for each step
      let step = 1;
      function moveStep() {
        if (step >= path.length) {
          // Animation complete
          transporterCircle.attr("data-animating", "false");
          transporterCircle.attr("data-current-location", path[path.length - 1]);
          HospitalTransport.state.animatingTransporters.delete(transporterName);
          return;
        }

        // Get position of next node
        const nextNodePosition = HospitalTransport.graph.getNodePosition(path[step]);
        if (!nextNodePosition) {
          console.error(`Node ${path[step]} not found for transporter animation`);
          transporterCircle.attr("data-animating", "false");
          HospitalTransport.state.animatingTransporters.delete(transporterName);
          return;
        }

        // Duration for this step (default to 1000ms if not provided)
        const duration = (durations && durations[step - 1]) || 1000;

        // Animate circle
        transporterCircle
          .transition()
          .duration(duration)
          .attr("cx", nextNodePosition.x)
          .attr("cy", nextNodePosition.y);

        // Animate label if it exists
        if (!transporterLabel.empty()) {
          transporterLabel
            .transition()
            .duration(duration)
            .attr("x", nextNodePosition.x)
            .attr("y", nextNodePosition.y - 20);
        }

        // Move to next step after animation completes
        transporterCircle
          .transition()
          .duration(duration)
          .on("end", () => {
            transporterCircle.attr("data-current-location", path[step]);
            step++;
            moveStep();
          });
      }

      // Start animation
      moveStep();
    }
  },

  /**
   * Transport request handling
   */
  requests: {
    load: function(callback) {
      fetch(`${HospitalTransport.config.socketUrl}/get_transport_requests`)
        .then(response => response.json())
        .then(requests => {
          // Update state with requests
          HospitalTransport.state.requests = requests;
          if (callback) callback(requests);
        })
        .catch(error => {
          console.error("Error loading transport requests:", error);
          HospitalTransport.log.add("Error loading transport requests", "error");
        });
    },

    loadAll: function(callback) {
      fetch(`${HospitalTransport.config.socketUrl}/get_all_transports`)
        .then(response => response.json())
        .then(transports => {
          if (callback) callback(transports);
        })
        .catch(error => {
          console.error("Error loading all transports:", error);
          HospitalTransport.log.add("Error loading all transports", "error");
        });
    },

    updateTransportTable: function(tableId = "transportTable") {
      const table = document.getElementById(tableId);
      if (!table) {
        console.warn(`Transport table with ID ${tableId} not found`);
        return;
      }

      HospitalTransport.requests.loadAll(transports => {
        const tbody = table.querySelector("tbody");
        if (!tbody) return;

        tbody.innerHTML = "";

        transports.forEach(req => {
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

        // Update counters if they exist
        HospitalTransport.requests.updateCounters(transports);
      });
    },

    updateCounters: function(transports) {
      // Update pending counter
      const pendingCounter = document.getElementById("pendingRequests");
      if (pendingCounter) {
        const pendingCount = transports.filter(r => r.status === "pending").length;
        pendingCounter.textContent = pendingCount;
      }

      // Update completed counter
      const completedCounter = document.getElementById("completedRequests");
      if (completedCounter) {
        const completedCount = transports.filter(r => r.status === "completed").length;
        completedCounter.textContent = completedCount;
      }

      // Update active transporters counter
      const activeCounter = document.getElementById("activeTransporters");
      if (activeCounter) {
        HospitalTransport.transporters.load(transporters => {
          const activeCount = transporters.filter(t => t.status === "active").length;
          activeCounter.textContent = activeCount;
        });
      }
    },

    createRequest: function(origin, destination, transportType = "stretcher", urgent = false, callback) {
      fetch(`${HospitalTransport.config.socketUrl}/frontend_transport_request`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          origin: origin,
          destination: destination,
          transport_type: transportType,
          urgent: urgent
        })
      })
      .then(response => response.json())
      .then(data => {
        if (data.error) {
          HospitalTransport.log.add(`Error creating request: ${data.error}`, "error");
        } else {
          HospitalTransport.log.add(`Created transport request: ${origin} → ${destination}`, "success");
        }

        if (callback) callback(data);
      })
      .catch(error => {
        console.error("Error creating request:", error);
        HospitalTransport.log.add("Error creating transport request", "error");
      });
    }
  },

  /**
   * Simulation control
   */
  simulation: {
    start: function(callback) {
      fetch(`${HospitalTransport.config.socketUrl}/toggle_simulation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ running: true })
      })
      .then(response => response.json())
      .then(data => {
        HospitalTransport.state.simulationRunning = true;
        HospitalTransport.log.add("▶️ Simulation started", "success");

        // Update UI elements if they exist
        const startBtn = document.getElementById("startSimulationBtn");
        const stopBtn = document.getElementById("stopSimulationBtn");

        if (startBtn) startBtn.style.display = "none";
        if (stopBtn) stopBtn.style.display = "inline-block";

        // Update simulation status
        const statusEl = document.getElementById("simulationStatus");
        if (statusEl) {
          statusEl.textContent = "Running";
          statusEl.className = "status-running";
        }

        if (callback) callback(data);
      })
      .catch(error => {
        console.error("Error starting simulation:", error);
        HospitalTransport.log.add("Error starting simulation", "error");
      });
    },

    stop: function(callback) {
      fetch(`${HospitalTransport.config.socketUrl}/toggle_simulation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ running: false })
      })
      .then(response => response.json())
      .then(data => {
        HospitalTransport.state.simulationRunning = false;
        HospitalTransport.log.add("🛑 Simulation stopped", "success");

        // Update UI elements if they exist
        const startBtn = document.getElementById("startSimulationBtn");
        const stopBtn = document.getElementById("stopSimulationBtn");

        if (startBtn) startBtn.style.display = "inline-block";
        if (stopBtn) stopBtn.style.display = "none";

        // Update simulation status
        const statusEl = document.getElementById("simulationStatus");
        if (statusEl) {
          statusEl.textContent = "Stopped";
          statusEl.className = "status-stopped";
        }

        if (callback) callback(data);
      })
      .catch(error => {
        console.error("Error stopping simulation:", error);
        HospitalTransport.log.add("Error stopping simulation", "error");
      });
    },

    setStrategy: function(strategyName, callback) {
      fetch(`${HospitalTransport.config.socketUrl}/set_strategy_by_name`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy: strategyName })
      })
      .then(response => response.json())
      .then(data => {
        HospitalTransport.log.add(`Strategy set to ${strategyName}`, "success");
        if (callback) callback(data);
      })
      .catch(error => {
        console.error("Error setting strategy:", error);
        HospitalTransport.log.add("Error setting strategy", "error");
      });
    },

    deployStrategy: function(callback) {
      fetch(`${HospitalTransport.config.socketUrl}/deploy_strategy_assignment`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({})
      })
      .then(response => response.json())
      .then(data => {
        HospitalTransport.log.add("Strategy deployment initiated", "success");
        if (callback) callback(data);
      })
      .catch(error => {
        console.error("Error deploying strategy:", error);
        HospitalTransport.log.add("Error deploying strategy", "error");
      });
    },

    updateConfig: function(config, callback) {
      fetch(`${HospitalTransport.config.socketUrl}/update_simulator_config`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config)
      })
      .then(response => response.json())
      .then(data => {
        HospitalTransport.log.add("Simulator configuration updated", "success");
        if (callback) callback(data);
      })
      .catch(error => {
        console.error("Error updating simulator config:", error);
        HospitalTransport.log.add("Error updating simulator configuration", "error");
      });
    }
  },

  /**
   * UI utilities
   */
  ui: {
    populateDepartmentDropdowns: function(selectorOrigin, selectorDestination) {
      if (!HospitalTransport.state.graph) {
        console.error("Graph not loaded. Call HospitalTransport.graph.load() first");
        return;
      }

      const originDropdown = document.querySelector(selectorOrigin);
      const destDropdown = document.querySelector(selectorDestination);

      if (!originDropdown || !destDropdown) {
        console.warn("Dropdown elements not found");
        return;
      }

      // Clear existing options
      originDropdown.innerHTML = "";
      destDropdown.innerHTML = "";

      // Get departments from graph
      const departments = HospitalTransport.state.graph.nodes.map(node => node.id);

      // Create HTML for options
      const optionsHtml = departments.map(dept =>
        `<option value="${dept}">${dept}</option>`
      ).join("");

      // Set options to dropdowns
      originDropdown.innerHTML = optionsHtml;
      destDropdown.innerHTML = optionsHtml;
    },

    populateStrategyDropdown: function(selector, callback) {
      fetch(`${HospitalTransport.config.socketUrl}/get_available_strategies`)
        .then(response => response.json())
        .then(strategies => {
          const dropdown = document.querySelector(selector);
          if (!dropdown) {
            console.warn("Strategy dropdown element not found");
            return;
          }

          // Clear existing options
          dropdown.innerHTML = "";

          // Create and add options
          strategies.forEach(strategy => {
            const option = document.createElement("option");
            option.value = strategy;
            option.textContent = strategy;
            dropdown.appendChild(option);
          });

          if (callback) callback(strategies);
        })
        .catch(error => {
          console.error("Error loading strategies:", error);
          HospitalTransport.log.add("Error loading available strategies", "error");
        });
    },

    formatTime: function(seconds) {
      if (!seconds) return '00:00:00';

      const hrs = Math.floor(seconds / 3600);
      const mins = Math.floor((seconds % 3600) / 60);
      const secs = Math.floor(seconds % 60);

      return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    },

    updateClock: function(simTime, selector = "#sim-clock") {
      const clockElement = document.querySelector(selector);
      if (!clockElement) return;

      const formattedTime = HospitalTransport.ui.formatTime(simTime);
      clockElement.textContent = `⏱️ ${formattedTime}`;
    }
  },

  /**
   * Logging utilities
   */
  log: {
    buffer: [],

    add: function(message, type = "info") {
      // Create log entry
      const entry = {
        message,
        type,
        timestamp: new Date().toLocaleTimeString()
      };

      // Add to buffer
      HospitalTransport.state.logBuffer.push(entry);

      // Trim buffer if needed
      if (HospitalTransport.state.logBuffer.length > HospitalTransport.config.logMaxEntries) {
        HospitalTransport.state.logBuffer.shift();
      }

      // Update log display if exists
      HospitalTransport.log.updateDisplay();

      return entry;
    },

    updateDisplay: function(selector = "#logList") {
      const logElement = document.querySelector(selector);
      if (!logElement) return;

      // Add new entries
      HospitalTransport.state.logBuffer.forEach(entry => {
        // Check if entry already exists
        const existingEntries = Array.from(logElement.children);
        const exists = existingEntries.some(el =>
          el.textContent.includes(entry.message) &&
          el.textContent.includes(entry.timestamp)
        );

        if (!exists) {
          const logItem = document.createElement("li");
          logItem.textContent = `[${entry.timestamp}] ${entry.message}`;

          // Apply styles based on type
          if (entry.type === "error") {
            logItem.style.color = "red";
          } else if (entry.type === "success") {
            logItem.style.color = "green";
          }

          logElement.appendChild(logItem);

          // Scroll to bottom
          logElement.scrollTop = logElement.scrollHeight;
        }
      });

      // Trim log display if too long
      while (logElement.children.length > HospitalTransport.config.logMaxEntries) {
        logElement.removeChild(logElement.firstChild);
      }
    },

    clear: function(selector = "#logList") {
      const logElement = document.querySelector(selector);
      if (logElement) {
        logElement.innerHTML = "";
      }

      HospitalTransport.state.logBuffer = [];
    }
  },

  /**
   * Clustering visualization support
   */
  clusters: {
    data: null,

    load: function(callback) {
      fetch(`${HospitalTransport.config.socketUrl}/get_hospital_clusters`)
        .then(response => response.json())
        .then(clusters => {
          HospitalTransport.clusters.data = clusters;
          if (callback) callback(clusters);
        })
        .catch(error => {
          console.error("Error loading hospital clusters:", error);
          HospitalTransport.log.add("Error loading hospital clusters", "error");
        });
    },

    getClusterForDepartment: function(departmentId) {
      if (!HospitalTransport.clusters.data || !HospitalTransport.clusters.data.department_to_cluster) {
        return null;
      }

      return HospitalTransport.clusters.data.department_to_cluster[departmentId];
    },

    renderClusterView: function(svgSelector, options = {}) {
      if (!HospitalTransport.clusters.data) {
        console.error("Cluster data not loaded. Call HospitalTransport.clusters.load() first");
        return null;
      }

      const svg = d3.select(svgSelector);

      // Clear existing content if specified
      if (options.clear !== false) {
        svg.selectAll("*").remove();
      }

      const clusters = HospitalTransport.clusters.data.clusters;
      const clusterEntries = Object.entries(clusters);

      // Create layer groups
      const linkLayer = svg.append("g").attr("class", "cluster-link-layer");
      const clusterLayer = svg.append("g").attr("class", "cluster-node-layer");
      const labelLayer = svg.append("g").attr("class", "cluster-label-layer");
      const transporterLayer = svg.append("g").attr("class", "transporter-layer");

      // Draw inter-cluster connections if available
      if (HospitalTransport.clusters.data.connections) {
        linkLayer.selectAll("line")
          .data(HospitalTransport.clusters.data.connections)
          .enter()
          .append("line")
          .attr("class", "cluster-link")
          .attr("x1", d => clusters[d.source].center[0])
          .attr("y1", d => clusters[d.source].center[1])
          .attr("x2", d => clusters[d.target].center[0])
          .attr("y2", d => clusters[d.target].center[1])
          .style("stroke", "#bbb")
          .style("stroke-width", d => Math.max(1, Math.min(8, d.strength / 5)))
          .style("stroke-opacity", 0.6);
      }

      // Draw cluster nodes
      const clusterNodes = clusterLayer.selectAll(".cluster-node")
        .data(clusterEntries)
        .enter()
        .append("circle")
        .attr("class", "cluster-node node")
        .attr("cx", d => d[1].center[0])
        .attr("cy", d => d[1].center[1])
        .attr("r", d => Math.sqrt(d[1].size) * 5)  // Size based on number of departments
        .attr("fill", d => this._getClusterColor(d[1].dominant_type))
        .attr("stroke", "#2c3e50")
        .attr("stroke-width", "2px")
        .attr("data-cluster-id", d => d[0]);

      // Add click handler if provided
      if (options.onClusterClick) {
        clusterNodes
          .style("cursor", "pointer")
          .on("click", (event, d) => options.onClusterClick(d[0], d[1]));
      }

      // Draw cluster labels
      labelLayer.selectAll(".cluster-label")
        .data(clusterEntries)
        .enter()
        .append("text")
        .attr("class", "cluster-label")
        .attr("x", d => d[1].center[0])
        .attr("y", d => d[1].center[1] + Math.sqrt(d[1].size) * 5 + 15)
        .attr("text-anchor", "middle")
        .attr("font-size", "14px")
        .attr("fill", "#333")
        .text(d => d[1].name);

      return {
        linkLayer,
        clusterLayer,
        labelLayer,
        transporterLayer
      };
    },

    _getClusterColor: function(dominantType) {
      // Color scheme for different department types
      const colorMap = {
        "Emergency": "#e74c3c",
        "Surgery": "#9b59b6",
        "Inpatient": "#3498db",
        "Diagnostic": "#2ecc71",
        "Outpatient": "#f39c12",
        "Support": "#7f8c8d",
        "Other": "#95a5a6"
      };

      return colorMap[dominantType] || colorMap.Other;
    },

    getDepartmentsInCluster: function(clusterId) {
      if (!HospitalTransport.clusters.data || !HospitalTransport.clusters.data.clusters) {
        return [];
      }

      const cluster = HospitalTransport.clusters.data.clusters[clusterId];
      return cluster ? cluster.departments : [];
    },

    renderClusterDetails: function(clusterId, svgSelector, options = {}) {
      const departments = this.getDepartmentsInCluster(clusterId);
      if (!departments || departments.length === 0) {
        console.error(`No departments found in cluster ${clusterId}`);
        return null;
      }

      // Create a subgraph with only the departments in this cluster
      const subgraph = {
        nodes: HospitalTransport.state.graph.nodes.filter(n => departments.includes(n.id)),
        edges: HospitalTransport.state.graph.edges.filter(e =>
          departments.includes(e.source) && departments.includes(e.target)
        )
      };

      // Store the original graph temporarily
      const originalGraph = HospitalTransport.state.graph;
      HospitalTransport.state.graph = subgraph;

      // Render the subgraph
      const layers = HospitalTransport.graph.render(svgSelector, {
        ...options,
        clear: true
      });

      // Restore the original graph
      HospitalTransport.state.graph = originalGraph;

      return layers;
    }
  },

  /**
   * Private methods
   */
  _setupSocketListeners: function() {
    const socket = HospitalTransport.state.socket;
    if (!socket) {
      console.error("Socket not initialized");
      return;
    }

    // Transport log events
    socket.on("transport_log", function(data) {
      HospitalTransport.log.add(data.message);
    });

    // Clock tick events
    socket.on("clock_tick", function(data) {
      HospitalTransport.ui.updateClock(data.simTime);
    });

    // Transporter update events
    socket.on("transporter_update", function(data) {
      console.log("Transporter update:", data);
      HospitalTransport.transporters.animatePath(data.name, data.path, data.durations);
    });

    // New transporter events
    socket.on("new_transporter", function(data) {
      console.log("New transporter:", data);
      HospitalTransport.state.transporters[data.name] = data;

      // Refresh transporter visualization
      const svg = d3.select("svg");
      if (!svg.empty()) {
        HospitalTransport.transporters.render(svg.node());
      }
    });

    // Transport status update events
    socket.on("transport_status_update", function(data) {
      console.log("Transport status update:", data);
      HospitalTransport.requests.load();
      HospitalTransport.requests.updateTransportTable();
    });

    // Transport completed events
    socket.on("transport_completed", function(data) {
      console.log("Transport completed:", data);
      HospitalTransport.requests.load();
      HospitalTransport.requests.updateTransportTable();
    });

    // Connection events
    socket.on("connect", function() {
      console.log("Connected to server");
      HospitalTransport.log.add("Connected to server", "success");
    });

    socket.on("disconnect", function() {
      console.log("Disconnected from server");
      HospitalTransport.log.add("Disconnected from server", "error");
    });
  },

  /**
   * Initialization
   */
  initialize: function(options = {}) {
    // Apply configuration
    if (options.config) {
      HospitalTransport.config = {...HospitalTransport.config, ...options.config};
    }

    // Initialize socket
    HospitalTransport.socket.initialize(options.socketUrl);

    // Load graph
    HospitalTransport.graph.load(() => {
      console.log("Hospital graph loaded");

      // Load transporters
      HospitalTransport.transporters.load(() => {
        console.log("Transporters loaded");
      });

      // Load transport requests
      HospitalTransport.requests.load(() => {
        console.log("Transport requests loaded");
      });

      // Try to load clusters if endpoint exists
      fetch(`${HospitalTransport.config.socketUrl}/get_hospital_clusters`)
        .then(response => {
          if (response.ok) {
            return response.json();
          }
          throw new Error("Clusters endpoint not available");
        })
        .then(clusters => {
          HospitalTransport.clusters.data = clusters;
          console.log("Hospital clusters loaded");
        })
        .catch(error => {
          console.log("Clusters not available:", error.message);
        });
    });

    return HospitalTransport;
  }
};

// Export for module use
if (typeof module !== 'undefined' && module.exports) {
  module.exports = HospitalTransport;
}