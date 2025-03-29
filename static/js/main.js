// Initialize the HospitalTransport library
const transportSystem = HospitalTransport.initialize();

// Set up page-specific functionality when document is ready
window.onload = function() {
  // Render hospital graph
  transportSystem.graph.render('svg');
  
  // Update transporters and requests
  transportSystem.transporters.render('svg');
  transportSystem.requests.updateTransportTable();
  
  // Populate department dropdowns
  transportSystem.ui.populateDepartmentDropdowns('#originDropdown', '#destinationDropdown');
  
  // Setup button event handlers
  setupEventHandlers();
};

function setupEventHandlers() {
  // Add Transporter button
  document.getElementById("addTransporterBtn").addEventListener("click", function() {
    const transporterName = document.getElementById("transporterName").value.trim();
    if (!transporterName) {
      transportSystem.log.add("Please enter a transporter name.", "error");
      return;
    }
    
    fetch("/add_transporter", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: transporterName })
    })
    .then(response => response.json())
    .then(data => {
      if (data.error) {
        transportSystem.log.add(`Error: ${data.error}`, "error");
      } else {
        transportSystem.log.add(`Transporter ${transporterName} added successfully!`, "success");
        document.getElementById("transporterName").value = "";
      }
    });
  });
  
  // Set Transporter Status button
  document.getElementById("setStatusBtn").addEventListener("click", function() {
    const transporterName = document.getElementById("transporterSelect").value;
    const status = document.getElementById("statusDropdown").value;
    
    if (!transporterName) {
      transportSystem.log.add("Please select a transporter.", "error");
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
        transportSystem.log.add(`Error: ${data.error}`, "error");
      } else {
        transportSystem.transporters.load();
      }
    });
  });
  
  // Create Request button
  document.getElementById("createRequestBtn").addEventListener("click", function() {
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
  
  // Initiate Transport button
  document.getElementById("initiateTransportBtn").addEventListener("click", function() {
    const transporterName = document.getElementById("transporterSelect").value;
    const requestKey = document.getElementById("requestSelect").value;
    const requestObj = transportSystem.state.requests[requestKey];
    
    if (!transporterName || !requestObj) {
      transportSystem.log.add("Please select both a transporter and a request.", "error");
      return;
    }
    
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
        transportSystem.log.add(`Error: ${data.error}`, "error");
      } else {
        transportSystem.requests.load();
      }
    });
  });
  
  // Optimization buttons
  document.getElementById("optimizeBtn").addEventListener("click", function() {
    transportSystem.simulation.setStrategy("ILP: Makespan", () => {
      transportSystem.simulation.deployStrategy();
    });
  });
  
  document.getElementById("randomizeBtn").addEventListener("click", function() {
    transportSystem.simulation.setStrategy("Random", () => {
      transportSystem.simulation.deployStrategy();
    });
  });
  
  // Simulation buttons
  document.getElementById("simulateOptimallyBtn").addEventListener("click", function() {
    transportSystem.simulation.setStrategy("ILP: Makespan", () => {
      transportSystem.simulation.start();
    });
  });
  
  document.getElementById("simulateRandomlyBtn").addEventListener("click", function() {
    transportSystem.simulation.setStrategy("Random", () => {
      transportSystem.simulation.start();
    });
  });
  
  document.getElementById("stopSimulationBtn").addEventListener("click", function() {
    transportSystem.simulation.stop();
  });
  
  // Toggle table button
  document.getElementById("toggleTableBtn").addEventListener("click", function() {
    const container = document.getElementById("transportTableContainer");
    container.style.display = container.style.display === "none" ? "block" : "none";
  });
}

// Set up auto-refresh for transport table
setInterval(() => {
  if (document.getElementById("transportTableContainer").style.display !== "none") {
    transportSystem.requests.updateTransportTable();
  }
}, 5000);