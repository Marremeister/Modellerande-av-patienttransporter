/**
 * clustered-view.js - Hierarchical cluster visualization for hospital transport system
 */

// Initialize the HospitalTransport library
const transportSystem = HospitalTransport.initialize();

// Global state for cluster view
const clusterView = {
  currentView: "clusters", // "clusters" or "departments"
  currentCluster: null,
  clusterData: null
};

// Initialize when document is ready
window.onload = function() {
  // Load hospital graph
  transportSystem.graph.load(() => {
    // Check if clusters endpoint exists and load clusters
    fetch("/get_hospital_clusters")
      .then(response => {
        if (!response.ok) {
          throw new Error("Clusters API not available");
        }
        return response.json();
      })
      .then(data => {
        // Store cluster data
        clusterView.clusterData = data;
        transportSystem.clusters.data = data;

        // Initialize cluster view
        initializeClusterView();
      })
      .catch(error => {
        console.error("Error loading clusters:", error);
        transportSystem.log.add("Cluster view not available. Falling back to standard view.", "error");

        // Fall back to standard view
        transportSystem.graph.render('svg');
        transportSystem.transporters.render('svg');
      });
  });

  // Setup page UI elements
  setupPageElements();
};

function initializeClusterView() {
  // Render the cluster view
  const svg = d3.select('svg');

  // Clear any existing content
  svg.selectAll("*").remove();

  // Add back button (hidden initially)
  const backButton = d3.select("#visualization-controls")
    .append("button")
    .attr("id", "back-to-clusters-btn")
    .text("◀ Back to Clusters")
    .style("display", "none")
    .on("click", exitCluster);

  // Add view indicator
  d3.select("#visualization-controls")
    .append("div")
    .attr("id", "current-view-indicator")
    .text("Viewing: Hospital Clusters")
    .style("margin-left", "10px")
    .style("font-weight", "bold");

  // Render the cluster view
  renderClusters();

  // Update transport table
  transportSystem.requests.updateTransportTable();

  // Setup refresh interval
  setInterval(() => {
    updateVisualization();
  }, 5000);
}

function renderClusters() {
  // Render clusters view
  transportSystem.clusters.renderClusterView('svg', {
    clear: true,
    onClusterClick: enterCluster
  });

  // Update transporters to position them on clusters
  updateTransportersInClusterView();
}

function enterCluster(clusterId, clusterData) {
  // Update state
  clusterView.currentView = "departments";
  clusterView.currentCluster = clusterId;

  // Show back button
  d3.select("#back-to-clusters-btn").style("display", "block");

  // Update view indicator
  d3.select("#current-view-indicator").text(`Viewing: ${clusterData.name}`);

  // Render departments in this cluster
  transportSystem.clusters.renderClusterDetails(clusterId, 'svg', {
    shortLabels: false,
    showEdgeWeights: true
  });

  // Update transporters to show only those in this cluster
  updateTransportersInDepartmentView(clusterId);
}

function exitCluster() {
  // Update state
  clusterView.currentView = "clusters";
  clusterView.currentCluster = null;

  // Hide back button
  d3.select("#back-to-clusters-btn").style("display", "none");

  // Update view indicator
  d3.select("#current-view-indicator").text("Viewing: Hospital Clusters");

  // Render clusters
  renderClusters();
}

function updateTransportersInClusterView() {
  // Load current transporter data
  transportSystem.transporters.load(() => {
    // Create a map of which cluster each transporter is in
    const transporterClusters = {};

    // For each transporter, determine its cluster
    Object.values(transportSystem.state.transporters).forEach(transporter => {
      const departmentCluster = transportSystem.clusters.getClusterForDepartment(transporter.current_location);
      if (departmentCluster) {
        transporterClusters[transporter.name] = departmentCluster;
      }
    });

    // Get cluster centers
    const clusterCenters = {};
    Object.entries(clusterView.clusterData.clusters).forEach(([id, data]) => {
      clusterCenters[id] = data.center;
    });

    // Create transporter circles at cluster centers
    const svg = d3.select('svg');
    const transporterLayer = svg.select(".transporter-layer");

    // Clear existing transporters
    transporterLayer.selectAll("*").remove();

    // Create new transporters at cluster centers
    Object.entries(transporterClusters).forEach(([name, clusterId]) => {
      const center = clusterCenters[clusterId];
      if (!center) return;

      const transporter = transportSystem.state.transporters[name];
      if (!transporter) return;

      // Create transporter circle
      const color = transporter.status === "active" ? "#FF5252" : "#A9A9A9";

      transporterLayer.append("circle")
        .attr("class", "transporter")
        .attr("r", 12)
        .attr("cx", center[0])
        .attr("cy", center[1])
        .attr("fill", color)
        .attr("stroke", "white")
        .attr("stroke-width", 2)
        .attr("data-transporter", name)
        .attr("data-animating", "false")
        .attr("data-current-location", clusterId)
        .attr("data-cluster", clusterId);

      // Add label
      transporterLayer.append("text")
        .attr("class", "transporter-label")
        .attr("x", center[0])
        .attr("y", center[1] - 18)
        .attr("text-anchor", "middle")
        .attr("font-size", "11px")
        .attr("font-weight", "bold")
        .attr("fill", "#333")
        .attr("stroke", "white")
        .attr("stroke-width", "0.5")
        .attr("data-transporter-label", name)
        .text(name.replace(/^Sim_Transporter_/, "T"));
    });
  });
}

function updateTransportersInDepartmentView(clusterId) {
  // Load current transporter data
  transportSystem.transporters.load(() => {
    // Get departments in this cluster
    const departments = transportSystem.clusters.getDepartmentsInCluster(clusterId);
    if (!departments || departments.length === 0) return;

    // Filter transporters to those in this cluster
    const clusterTransporters = Object.values(transportSystem.state.transporters)
      .filter(t => departments.includes(t.current_location));

    // Create transporters
    const svg = d3.select('svg');
    const transporterLayer = svg.select(".transporter-layer");

    // Clear existing transporters
    transporterLayer.selectAll("*").remove();

    // Create new transporters at department locations
    clusterTransporters.forEach(transporter => {
      const nodePosition = transportSystem.graph.getNodePosition(transporter.current_location);
      if (!nodePosition) return;

      // Create transporter circle
      const color = transporter.status === "active" ? "#FF5252" : "#A9A9A9";

      transporterLayer.append("circle")
        .attr("class", "transporter")
        .attr("r", 12)
        .attr("cx", nodePosition.x)
        .attr("cy", nodePosition.y)
        .attr("fill", color)
        .attr("stroke", "white")
        .attr("stroke-width", 2)
        .attr("data-transporter", transporter.name)
        .attr("data-animating", "false")
        .attr("data-current-location", transporter.current_location);

      // Add label
      transporterLayer.append("text")
        .attr("class", "transporter-label")
        .attr("x", nodePosition.x)
        .attr("y", nodePosition.y - 18)
        .attr("text-anchor", "middle")
        .attr("font-size", "11px")
        .attr("font-weight", "bold")
        .attr("fill", "#333")
        .attr("stroke", "white")
        .attr("stroke-width", "0.5")
        .attr("data-transporter-label", transporter.name)
        .text(transporter.name.replace(/^Sim_Transporter_/, "T"));
    });
  });
}

function updateVisualization() {
  // Update visualization based on current view
  if (clusterView.currentView === "clusters") {
    updateTransportersInClusterView();
  } else if (clusterView.currentView === "departments" && clusterView.currentCluster) {
    updateTransportersInDepartmentView(clusterView.currentCluster);
  }
}

function setupPageElements() {
  // Add event listeners to page elements

  // Create Request button
  document.getElementById("createRequestBtn")?.addEventListener("click", function() {
    const origin = document.getElementById("originDropdown").value;
    const destination = document.getElementById("destinationDropdown").value;
    const transportType = document.getElementById("typeDropdown").value;
    const urgent = document.getElementById("urgentDropdown").value === "true";

    if (!origin || !destination || origin === destination) {
      transportSystem.log.add("Please select a valid origin and destination.", "error");
      return;
    }

    transportSystem.requests.createRequest(origin, destination, transportType, urgent, () => {
      transportSystem.requests.load();
    });
  });

  // Setup other page-specific buttons
  // ...
}

// Handle transporter animations at both cluster and department level
transportSystem.socket.onEvent("transporter_update", function(data) {
  if (!data || !data.name || !data.path || data.path.length < 2) return;

  // Custom handling based on current view
  if (clusterView.currentView === "clusters") {
    // Handle cluster-level movement
    animateTransporterBetweenClusters(data.name, data.path, data.durations);
  } else if (clusterView.currentView === "departments" &&
             clusterView.currentCluster !== null) {
    // Only animate if the transporter's path includes departments in the current cluster
    const departments = transportSystem.clusters.getDepartmentsInCluster(clusterView.currentCluster);

    // Filter path to only include departments in this cluster
    const relevantPathIndices = [];
    data.path.forEach((dept, index) => {
      if (departments.includes(dept)) {
        relevantPathIndices.push(index);
      }
    });

    if (relevantPathIndices.length >= 2) {
      // Create subpath that's relevant to this cluster
      const subPath = relevantPathIndices.map(idx => data.path[idx]);

      // Create corresponding durations
      const subDurations = [];
      for (let i = 0; i < relevantPathIndices.length - 1; i++) {
        const durationIndex = relevantPathIndices[i];
        if (durationIndex < data.durations.length) {
          subDurations.push(data.durations[durationIndex]);
        } else {
          subDurations.push(1000); // Default duration
        }
      }

      // Animate the transporter within the cluster
      transportSystem.transporters.animatePath(data.name, subPath, subDurations, 'svg');
    }
  }
});

// Animation between clusters
function animateTransporterBetweenClusters(transporterName, departmentPath, durations) {
  // Convert department path to cluster path
  const clusterPath = [];
  const clusterDurations = [];
  let currentCluster = null;
  let accumulatedDuration = 0;

  // Map each department to its cluster
  for (let i = 0; i < departmentPath.length; i++) {
    const dept = departmentPath[i];
    const cluster = transportSystem.clusters.getClusterForDepartment(dept);

    // If we've moved to a new cluster
    if (cluster !== currentCluster && cluster) {
      if (currentCluster !== null) {
        // Add the previous cluster to the path
        clusterPath.push(currentCluster);
        clusterDurations.push(accumulatedDuration);
        accumulatedDuration = 0;
      }
      currentCluster = cluster;
    }

    // Add this step's duration
    if (i < departmentPath.length - 1 && i < durations.length) {
      accumulatedDuration += durations[i];
    }
  }

  // Add the final cluster if it exists
  if (currentCluster && (clusterPath.length === 0 || clusterPath[clusterPath.length - 1] !== currentCluster)) {
    clusterPath.push(currentCluster);
    clusterDurations.push(accumulatedDuration);
  }

  // If we have a valid cluster path, animate between clusters
  if (clusterPath.length >= 2) {
    // Get the transporter element
    const svg = d3.select('svg');
    const transporterLayer = svg.select(".transporter-layer");

    // Get the transporter circle
    let transporterCircle = transporterLayer.select(`[data-transporter="${transporterName}"]`);
    let transporterLabel = transporterLayer.select(`[data-transporter-label="${transporterName}"]`);

    // If transporter doesn't exist yet, create it at the first cluster
    if (transporterCircle.empty()) {
      const firstCluster = clusterPath[0];
      const clusterCenter = clusterView.clusterData.clusters[firstCluster].center;

      transporterCircle = transporterLayer.append("circle")
        .attr("class", "transporter")
        .attr("r", 12)
        .attr("cx", clusterCenter[0])
        .attr("cy", clusterCenter[1])
        .attr("fill", "#FF5252")
        .attr("stroke", "white")
        .attr("stroke-width", 2)
        .attr("data-transporter", transporterName)
        .attr("data-animating", "true")
        .attr("data-current-location", firstCluster)
        .attr("data-cluster", firstCluster);

      transporterLabel = transporterLayer.append("text")
        .attr("class", "transporter-label")
        .attr("x", clusterCenter[0])
        .attr("y", clusterCenter[1] - 18)
        .attr("text-anchor", "middle")
        .attr("font-size", "11px")
        .attr("font-weight", "bold")
        .attr("fill", "#333")
        .attr("stroke", "white")
        .attr("stroke-width", "0.5")
        .attr("data-transporter-label", transporterName)
        .text(transporterName.replace(/^Sim_Transporter_/, "T"));
    }

    // Animate between clusters
    let step = 1;
    function moveStep() {
      if (step >= clusterPath.length) {
        // Animation complete
        transporterCircle.attr("data-animating", "false");
        transporterCircle.attr("data-current-location", clusterPath[clusterPath.length - 1]);
        transporterCircle.attr("data-cluster", clusterPath[clusterPath.length - 1]);
        return;
      }

      // Get center of next cluster
      const nextCluster = clusterPath[step];
      const nextCenter = clusterView.clusterData.clusters[nextCluster].center;
      if (!nextCenter) {
        console.error(`Cluster ${nextCluster} not found for animation`);
        step++;
        moveStep();
        return;
      }

      // Duration for this step
      const duration = clusterDurations[step - 1] || 1000;

      // Animate circle
      transporterCircle
        .transition()
        .duration(duration)
        .attr("cx", nextCenter[0])
        .attr("cy", nextCenter[1]);

      // Animate label
      if (!transporterLabel.empty()) {
        transporterLabel
          .transition()
          .duration(duration)
          .attr("x", nextCenter[0])
          .attr("y", nextCenter[1] - 18);
      }

      // Move to next step after animation completes
      transporterCircle
        .transition()
        .duration(duration)
        .on("end", () => {
          transporterCircle.attr("data-current-location", nextCluster);
          transporterCircle.attr("data-cluster", nextCluster);
          step++;
          moveStep();
        });
    }

    // Start animation
    moveStep();
  }
}

//hej