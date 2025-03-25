// Establish socket connection
const socket = io("http://127.0.0.1:5001");

// Global state
let benchmarkRunning = false;
let benchmarkResults = {
  random: [],
  ilpMakespan: [],
  ilpEqual: [],
  ilpUrgency: []
};
let workloadData = {
  random: {},
  ilpMakespan: {},
  ilpEqual: {},
  ilpUrgency: {}
};
let charts = {};

// DOM Elements
const transporterCountSlider = document.getElementById('transporterCountSlider');
const transporterCountValue = document.getElementById('transporterCountValue');
const randomRunsSlider = document.getElementById('randomRunsSlider');
const randomRunsValue = document.getElementById('randomRunsValue');
const runBenchmarkBtn = document.getElementById('run-benchmark-btn');

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
  // Initialize sliders
  initializeSliders();

  // Initialize tabs
  initializeTabs();

  // Set up modal triggers
  setupModals();

  // Load departments for scenario builder
  loadDepartmentOptions();

  // Create placeholder charts
  createPlaceholderCharts();

  // Initialize event listeners
  initializeEventListeners();

  // Socket event listeners
  setupSocketListeners();
});

// INITIALIZATION FUNCTIONS

function initializeSliders() {
  // Transporter count slider
  transporterCountSlider.addEventListener('input', function() {
    transporterCountValue.textContent = this.value;
  });

  // Random runs slider
  randomRunsSlider.addEventListener('input', function() {
    randomRunsValue.textContent = this.value;
  });
}

function initializeTabs() {
  const tabButtons = document.querySelectorAll('.tab-btn');
  const tabPanes = document.querySelectorAll('.tab-pane');

  tabButtons.forEach(button => {
    button.addEventListener('click', function() {
      // Remove active class from all buttons and panes
      tabButtons.forEach(btn => btn.classList.remove('active'));
      tabPanes.forEach(pane => pane.classList.remove('active'));

      // Add active class to current button and corresponding pane
      this.classList.add('active');
      const tabId = this.getAttribute('data-tab');
      document.getElementById(tabId).classList.add('active');

      // Redraw charts if any
      if (charts[tabId]) {
        charts[tabId].update();
      }
    });
  });
}

function setupModals() {
  // Add scenario modal
  const addScenarioBtn = document.getElementById('add-scenario-btn');
  const addScenarioModal = document.getElementById('add-scenario-modal');
  const closeButtons = document.querySelectorAll('.close-modal');

  addScenarioBtn.addEventListener('click', function() {
    addScenarioModal.style.display = 'block';
  });

  closeButtons.forEach(button => {
    button.addEventListener('click', function() {
      // Find the parent modal
      const modal = this.closest('.modal');
      modal.style.display = 'none';
    });
  });

  // Close modals when clicking outside content
  window.addEventListener('click', function(event) {
    if (event.target.classList.contains('modal')) {
      event.target.style.display = 'none';
    }
  });

  // Add request button in scenario modal
  document.getElementById('add-request-btn').addEventListener('click', addRequestRow);

  // Save scenario button
  document.getElementById('save-scenario-btn').addEventListener('click', saveScenario);
}

function loadDepartmentOptions() {
  // Fetch departments from the server
  fetch('/get_hospital_graph')
    .then(response => response.json())
    .then(graph => {
      const departments = graph.nodes.map(node => node.id);
      populateDepartmentDropdowns(departments);
    })
    .catch(error => console.error('Error loading departments:', error));
}

function populateDepartmentDropdowns(departments) {
  // Get all origin and destination selects in the modal
  const originSelects = document.querySelectorAll('.origin-select');
  const destinationSelects = document.querySelectorAll('.destination-select');

  // Create options HTML
  const optionsHTML = departments.map(dept =>
    `<option value="${dept}">${dept}</option>`
  ).join('');

  // Populate dropdowns
  originSelects.forEach(select => select.innerHTML = optionsHTML);
  destinationSelects.forEach(select => select.innerHTML = optionsHTML);
}

function createPlaceholderCharts() {
  // Create metrics chart (bar chart)
  const metricsCtx = document.getElementById('metrics-chart').getContext('2d');
  charts.metricsChart = new Chart(metricsCtx, {
    type: 'bar',
    data: {
      labels: ['Mean', 'Median', 'Std Dev', 'Min', 'Max'],
      datasets: [{
        label: 'ILP Optimizer',
        backgroundColor: 'rgba(75, 108, 183, 0.7)',
        borderColor: 'rgba(75, 108, 183, 1)',
        borderWidth: 1,
        data: [0, 0, 0, 0, 0]
      }, {
        label: 'Random Assignment',
        backgroundColor: 'rgba(231, 76, 60, 0.7)',
        borderColor: 'rgba(231, 76, 60, 1)',
        borderWidth: 1,
        data: [0, 0, 0, 0, 0]
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: 'Comparison of Key Metrics'
        },
        legend: {
          position: 'top',
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: 'Time (seconds)'
          }
        }
      }
    }
  });

  // Create histogram chart
  const histogramCtx = document.getElementById('histogram-chart').getContext('2d');
  charts.histogramChart = new Chart(histogramCtx, {
    type: 'bar',
    data: {
      labels: generateHistogramLabels(10),
      datasets: [{
        label: 'Random Assignment Frequency',
        backgroundColor: 'rgba(231, 76, 60, 0.7)',
        borderColor: 'rgba(231, 76, 60, 1)',
        borderWidth: 1,
        data: Array(10).fill(0)
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: 'Distribution of Completion Times'
        },
        legend: {
          position: 'top',
        },
        annotation: {
          annotations: {
            optimalLine: {
              type: 'line',
              yMin: 0,
              yMax: 0,
              borderColor: 'rgba(75, 108, 183, 1)',
              borderWidth: 2,
              label: {
                content: 'Optimal Time',
                enabled: true,
                position: 'top'
              }
            },
            meanLine: {
              type: 'line',
              yMin: 0,
              yMax: 0,
              borderColor: 'rgba(231, 76, 60, 1)',
              borderWidth: 2,
              label: {
                content: 'Mean Time',
                enabled: true,
                position: 'bottom'
              }
            }
          }
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: 'Frequency'
          }
        },
        x: {
          title: {
            display: true,
            text: 'Completion Time (seconds)'
          }
        }
      }
    }
  });

  // Create optimal workload chart
  const optimalWorkloadCtx = document.getElementById('optimal-workload-chart').getContext('2d');
  charts.optimalWorkloadChart = new Chart(optimalWorkloadCtx, {
    type: 'bar',
    data: {
      labels: ['T1', 'T2', 'T3'],
      datasets: [{
        label: 'Total Work Time',
        backgroundColor: 'rgba(75, 108, 183, 0.7)',
        borderColor: 'rgba(75, 108, 183, 1)',
        borderWidth: 1,
        data: [0, 0, 0]
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: 'ILP Optimizer Workload Distribution'
        },
        subtitle: {
          display: true,
          text: 'Standard Deviation: 0'
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: 'Total Time (seconds)'
          }
        },
        x: {
          title: {
            display: true,
            text: 'Transporter'
          }
        }
      }
    }
  });

  // Create random workload chart
  const randomWorkloadCtx = document.getElementById('random-workload-chart').getContext('2d');
  charts.randomWorkloadChart = new Chart(randomWorkloadCtx, {
    type: 'bar',
    data: {
      labels: ['T1', 'T2', 'T3'],
      datasets: [{
        label: 'Total Work Time',
        backgroundColor: 'rgba(231, 76, 60, 0.7)',
        borderColor: 'rgba(231, 76, 60, 1)',
        borderWidth: 1,
        data: [0, 0, 0]
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        title: {
          display: true,
          text: 'Random Assignment Workload Distribution'
        },
        subtitle: {
          display: true,
          text: 'Standard Deviation: 0'
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: 'Total Time (seconds)'
          }
        },
        x: {
          title: {
            display: true,
            text: 'Transporter'
          }
        }
      }
    }
  });
}

function initializeEventListeners() {
  // Run benchmark button
  runBenchmarkBtn.addEventListener('click', startBenchmark);

  // Export data button
  document.getElementById('export-data-btn').addEventListener('click', exportBenchmarkData);

  // Save benchmark button
  document.getElementById('save-benchmark-btn').addEventListener('click', saveBenchmarkResults);

  // Cancel benchmark button
  document.getElementById('cancel-benchmark-btn').addEventListener('click', cancelBenchmark);
}

function setupSocketListeners() {
  // Listen for benchmark progress updates
  socket.on('benchmark_progress', function(data) {
    updateBenchmarkProgress(data);
  });

  // Listen for benchmark results
  socket.on('benchmark_results', function(data) {
    processBenchmarkResults(data);
  });

  // Listen for benchmark completion
  socket.on('benchmark_complete', function(data) {
    finalizeBenchmark(data);
  });

  // Handle connection issues
  socket.on('connect_error', function() {
    notifyUser('Connection error. Please check if the server is running.', 'error');
  });

  socket.on('disconnect', function() {
    notifyUser('Disconnected from server.', 'error');
  });
}

// BENCHMARK EXECUTION

function startBenchmark() {
  // Get configuration values
  const numTransporters = parseInt(transporterCountSlider.value);
  const randomRuns = parseInt(randomRunsSlider.value);
  const strategies = getSelectedStrategies();
  const scenarios = getSelectedScenarios();

  // Validate configuration
  if (strategies.length === 0) {
    notifyUser('Please select at least one strategy.', 'error');
    return;
  }

  if (scenarios.length === 0) {
    notifyUser('Please select at least one scenario.', 'error');
    return;
  }

  // Clear previous results
  clearBenchmarkResults();

  // Show progress modal
  const progressModal = document.getElementById('benchmark-progress-modal');
  progressModal.style.display = 'block';

  // Update status
  document.getElementById('benchmark-status').textContent = 'Status: Running Benchmark';
  benchmarkRunning = true;
  runBenchmarkBtn.disabled = true;

  // Initialize progress bar
  updateProgressBar(0, 'Initializing benchmark...');

  // Send benchmark request to server
  fetch('/start_benchmark', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      transporters: numTransporters,
      random_runs: randomRuns,
      strategies: strategies,
      scenarios: scenarios
    })
  })
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error ${response.status}`);
    }
    return response.json();
  })
  .then(data => {
    // Benchmark started successfully
    notifyUser('Benchmark started successfully.', 'success');
  })
  .catch(error => {
    notifyUser(`Failed to start benchmark: ${error}`, 'error');
    finalizeBenchmark({ error: error.message });
  });
}

function getSelectedStrategies() {
  const strategies = [];

  if (document.getElementById('strategyOptimal').checked) {
    strategies.push('ILP: Makespan');
  }

  if (document.getElementById('strategyEqual').checked) {
    strategies.push('ILP: Equal Workload');
  }

  if (document.getElementById('strategyUrgency').checked) {
    strategies.push('ILP: Urgency First');
  }

  if (document.getElementById('strategyRandom').checked) {
    strategies.push('Random');
  }

  return strategies;
}

function getSelectedScenarios() {
  const scenarios = [];
  const scenarioItems = document.querySelectorAll('.scenario-item');

  scenarioItems.forEach(item => {
    const checkbox = item.querySelector('input[type="checkbox"]');
    const nameElement = item.querySelector('.scenario-name');

    if (checkbox && checkbox.checked && nameElement) {
      scenarios.push(nameElement.textContent);
    }
  });

  return scenarios;
}

function clearBenchmarkResults() {
  benchmarkResults = {
    random: [],
    ilpMakespan: [],
    ilpEqual: [],
    ilpUrgency: []
  };

  workloadData = {
    random: {},
    ilpMakespan: {},
    ilpEqual: {},
    ilpUrgency: {}
  };

  // Clear result displays
  document.getElementById('optimal-makespan').textContent = '--';
  document.getElementById('random-average').textContent = '--';
  document.getElementById('improvement-percentage').textContent = '--';
  document.getElementById('random-std').textContent = '--';

  // Reset charts
  resetCharts();

  // Clear table
  const tableBody = document.querySelector('#strategy-comparison-table tbody');
  tableBody.innerHTML = `
    <tr>
      <td>ILP: Makespan</td>
      <td>--</td>
      <td>--</td>
      <td>--</td>
      <td>--</td>
      <td>--</td>
    </tr>
    <tr>
      <td>Random</td>
      <td>--</td>
      <td>--</td>
      <td>--</td>
      <td>--</td>
      <td>--</td>
    </tr>
  `;

  // Clear raw data table
  document.querySelector('#raw-data-table tbody').innerHTML = '';
}

function resetCharts() {
  // Reset metrics chart
  charts.metricsChart.data.datasets.forEach((dataset) => {
    dataset.data = [0, 0, 0, 0, 0];
  });
  charts.metricsChart.update();

  // Reset histogram chart
  charts.histogramChart.data.datasets[0].data = Array(10).fill(0);
  charts.histogramChart.update();

  // Reset workload charts
  charts.optimalWorkloadChart.data.labels = ['T1', 'T2', 'T3'];
  charts.optimalWorkloadChart.data.datasets[0].data = [0, 0, 0];
  charts.optimalWorkloadChart.update();

  charts.randomWorkloadChart.data.labels = ['T1', 'T2', 'T3'];
  charts.randomWorkloadChart.data.datasets[0].data = [0, 0, 0];
  charts.randomWorkloadChart.update();
}

function updateBenchmarkProgress(data) {
  const { progress, current_task, elapsed_time, estimated_completion } = data;

  // Update progress bar
  updateProgressBar(progress, current_task);

  // Update progress details
  document.querySelector('.progress-stat:nth-child(1) .stat-value').textContent = formatTime(elapsed_time);
  document.querySelector('.progress-stat:nth-child(2) .stat-value').textContent = formatTime(estimated_completion);
  document.querySelector('.progress-stat:nth-child(3) .stat-value').textContent = current_task;
}

function updateProgressBar(progress, message) {
  const progressFill = document.querySelector('.progress-fill');
  const progressText = document.querySelector('.progress-text');

  progressFill.style.width = `${progress}%`;
  progressText.textContent = `${progress}% - ${message}`;
}

function cancelBenchmark() {
  fetch('/cancel_benchmark', { method: 'POST' })
    .then(response => response.json())
    .then(data => {
      notifyUser('Benchmark cancelled.', 'info');
      finalizeBenchmark({ cancelled: true });
    })
    .catch(error => {
      notifyUser(`Error cancelling benchmark: ${error}`, 'error');
    });
}

// RESULT PROCESSING

function processBenchmarkResults(data) {
  // Store the results
  if (data.strategy === 'Random') {
    benchmarkResults.random = data.times;
    workloadData.random = data.workload || {};
  } else if (data.strategy === 'ILP: Makespan') {
    benchmarkResults.ilpMakespan = data.times;
    workloadData.ilpMakespan = data.workload || {};
  } else if (data.strategy === 'ILP: Equal Workload') {
    benchmarkResults.ilpEqual = data.times;
    workloadData.ilpEqual = data.workload || {};
  } else if (data.strategy === 'ILP: Urgency First') {
    benchmarkResults.ilpUrgency = data.times;
    workloadData.ilpUrgency = data.workload || {};
  }

  // Update the UI with partial results if possible
  if (benchmarkResults.random.length > 0 && benchmarkResults.ilpMakespan.length > 0) {
    updateSummaryResults();
  }
}

function finalizeBenchmark(data) {
  // Hide progress modal
  const progressModal = document.getElementById('benchmark-progress-modal');
  progressModal.style.display = 'none';

  // Update status
  document.getElementById('benchmark-status').textContent = 'Status: Ready';
  benchmarkRunning = false;
  runBenchmarkBtn.disabled = false;

  // Check for errors
  if (data.error) {
    notifyUser(`Benchmark error: ${data.error}`, 'error');
    return;
  }

  // Check if cancelled
  if (data.cancelled) {
    notifyUser('Benchmark was cancelled.', 'info');
    return;
  }

  // Final update of results
  updateAllResults();

  // Add to recent runs
  addToRecentRuns();

  notifyUser('Benchmark completed successfully!', 'success');
}

function updateAllResults() {
  updateSummaryResults();
  updateHistogram();
  updateWorkloadCharts();
  updateRawDataTable();
}

function updateSummaryResults() {
  if (benchmarkResults.random.length === 0 || benchmarkResults.ilpMakespan.length === 0) {
    return;
  }

  // Calculate metrics
  const optimalTime = benchmarkResults.ilpMakespan[0];
  const randomMean = calculateMean(benchmarkResults.random);
  const randomMedian = calculateMedian(benchmarkResults.random);
  const randomStd = calculateStandardDeviation(benchmarkResults.random);
  const randomMin = Math.min(...benchmarkResults.random);
  const randomMax = Math.max(...benchmarkResults.random);

  const improvementPercentage = ((randomMean - optimalTime) / randomMean) * 100;

  // Update summary cards
  document.getElementById('optimal-makespan').textContent = optimalTime.toFixed(2);
  document.getElementById('random-average').textContent = randomMean.toFixed(2);
  document.getElementById('improvement-percentage').textContent = improvementPercentage.toFixed(1);
  document.getElementById('random-std').textContent = randomStd.toFixed(2);

  // Update metrics chart
  charts.metricsChart.data.datasets[0].data = [optimalTime, optimalTime, 0, optimalTime, optimalTime];
  charts.metricsChart.data.datasets[1].data = [randomMean, randomMedian, randomStd, randomMin, randomMax];
  charts.metricsChart.update();

  // Update comparison table
  const optimalWorkloadStd = calculateWorkloadStd(workloadData.ilpMakespan);
  const randomWorkloadStd = calculateWorkloadStd(workloadData.random);

  const tableBody = document.querySelector('#strategy-comparison-table tbody');
  tableBody.innerHTML = `
    <tr>
      <td>ILP: Makespan</td>
      <td>${optimalTime.toFixed(2)}s</td>
      <td>${optimalTime.toFixed(2)}s</td>
      <td>0.00</td>
      <td>${optimalTime.toFixed(2)}s</td>
      <td>${optimalWorkloadStd.toFixed(2)}</td>
    </tr>
    <tr>
      <td>Random</td>
      <td>${randomMean.toFixed(2)}s</td>
      <td>${randomMedian.toFixed(2)}s</td>
      <td>${randomStd.toFixed(2)}</td>
      <td>${randomMax.toFixed(2)}s</td>
      <td>${randomWorkloadStd.toFixed(2)}</td>
    </tr>
  `;
}

function updateHistogram() {
  if (benchmarkResults.random.length === 0) {
    return;
  }

  // Calculate bin ranges
  const min = Math.min(...benchmarkResults.random);
  const max = Math.max(...benchmarkResults.random);
  const range = max - min;
  const binCount = 10;
  const binWidth = range / binCount;

  // Create bins
  const bins = Array(binCount).fill(0);

  // Count values in each bin
  benchmarkResults.random.forEach(time => {
    const binIndex = Math.min(Math.floor((time - min) / binWidth), binCount - 1);
    bins[binIndex]++;
  });

  // Create labels
  const labels = [];
  for (let i = 0; i < binCount; i++) {
    const start = min + (i * binWidth);
    const end = min + ((i + 1) * binWidth);
    labels.push(`${start.toFixed(1)}-${end.toFixed(1)}`);
  }

  // Update chart
  charts.histogramChart.data.labels = labels;
  charts.histogramChart.data.datasets[0].data = bins;

  // Update chart annotations for optimal and mean lines
  const optimalTime = benchmarkResults.ilpMakespan[0];
  const randomMean = calculateMean(benchmarkResults.random);
  
  // This updates annotations in Chart.js v3+
  if (!charts.histogramChart.options.plugins.annotation) {
    charts.histogramChart.options.plugins.annotation = {
      annotations: {
        optimalLine: {
          type: 'line',
          xMin: optimalTime,
          xMax: optimalTime,
          borderColor: 'rgba(75, 108, 183, 1)',
          borderWidth: 2,
          label: {
            content: `Optimal: ${optimalTime.toFixed(2)}s`,
            enabled: true
          }
        },
        meanLine: {
          type: 'line',
          xMin: randomMean,
          xMax: randomMean,
          borderColor: 'rgba(231, 76, 60, 1)',
          borderWidth: 2,
          label: {
            content: `Mean: ${randomMean.toFixed(2)}s`,
            enabled: true
          }
        }
      }
    };
  } else {
    // Update existing annotations
    const annotations = charts.histogramChart.options.plugins.annotation.annotations;
    annotations.optimalLine.xMin = optimalTime;
    annotations.optimalLine.xMax = optimalTime;
    annotations.optimalLine.label.content = `Optimal: ${optimalTime.toFixed(2)}s`;

    annotations.meanLine.xMin = randomMean;
    annotations.meanLine.xMax = randomMean;
    annotations.meanLine.label.content = `Mean: ${randomMean.toFixed(2)}s`;
  }

  charts.histogramChart.update();
}

function updateWorkloadCharts() {
  // Update optimal workload chart
  if (Object.keys(workloadData.ilpMakespan).length > 0) {
    const transporters = Object.keys(workloadData.ilpMakespan);
    const workloads = transporters.map(t => workloadData.ilpMakespan[t]);
    const std = calculateStandardDeviation(workloads);

    charts.optimalWorkloadChart.data.labels = transporters;
    charts.optimalWorkloadChart.data.datasets[0].data = workloads;
    charts.optimalWorkloadChart.options.plugins.subtitle.text = `Standard Deviation: ${std.toFixed(2)}`;
    charts.optimalWorkloadChart.update();
  }

  // Update random workload chart
  if (Object.keys(workloadData.random).length > 0) {
    const transporters = Object.keys(workloadData.random);
    const workloads = transporters.map(t => workloadData.random[t]);
    const std = calculateStandardDeviation(workloads);

    charts.randomWorkloadChart.data.labels = transporters;
    charts.randomWorkloadChart.data.datasets[0].data = workloads;
    charts.randomWorkloadChart.options.plugins.subtitle.text = `Standard Deviation: ${std.toFixed(2)}`;
    charts.randomWorkloadChart.update();
  }
}

function updateRawDataTable() {
  const tableBody = document.querySelector('#raw-data-table tbody');
  tableBody.innerHTML = '';

  // Add optimal results
  if (benchmarkResults.ilpMakespan.length > 0) {
    const optimalWorkloadStd = calculateWorkloadStd(workloadData.ilpMakespan);
    const optimalWorkloadValues = Object.values(workloadData.ilpMakespan);
    const maxLoad = Math.max(...optimalWorkloadValues);
    const minLoad = Math.min(...optimalWorkloadValues);

    const row = document.createElement('tr');
    row.innerHTML = `
      <td>1</td>
      <td>ILP: Makespan</td>
      <td>${benchmarkResults.ilpMakespan[0].toFixed(2)}s</td>
      <td>${optimalWorkloadStd.toFixed(2)}</td>
      <td>${maxLoad.toFixed(2)}s</td>
      <td>${minLoad.toFixed(2)}s</td>
    `;
    tableBody.appendChild(row);
  }

  // Add random results
  benchmarkResults.random.forEach((time, index) => {
    // For random workload, we only have one sample for now
    let workloadStd = '–';
    let maxLoad = '–';
    let minLoad = '–';

    if (index === 0 && Object.keys(workloadData.random).length > 0) {
      const values = Object.values(workloadData.random);
      workloadStd = calculateStandardDeviation(values).toFixed(2);
      maxLoad = Math.max(...values).toFixed(2) + 's';
      minLoad = Math.min(...values).toFixed(2) + 's';
    }

    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${index + 1}</td>
      <td>Random</td>
      <td>${time.toFixed(2)}s</td>
      <td>${workloadStd}</td>
      <td>${maxLoad}</td>
      <td>${minLoad}</td>
    `;
    tableBody.appendChild(row);
  });
}

function addToRecentRuns() {
  // Create new run entry
  const numTransporters = parseInt(transporterCountSlider.value);
  const randomRuns = parseInt(randomRunsSlider.value);
  const optimalTime = benchmarkResults.ilpMakespan[0];
  const randomMean = calculateMean(benchmarkResults.random);
  const improvement = ((randomMean - optimalTime) / randomMean) * 100;

  const timestamp = new Date().toLocaleTimeString();

  const recentRunsContainer = document.querySelector('.recent-runs');
  const runItem = document.createElement('div');
  runItem.className = 'benchmark-run-item';
  runItem.innerHTML = `
    <div class="benchmark-run-header">
      <span class="benchmark-time">Today, ${timestamp}</span>
      <span class="benchmark-label">${numTransporters} Transporters, ${randomRuns} Runs</span>
    </div>
    <div class="benchmark-stats">
      <div>Optimal: <span class="stat-highlight">${optimalTime.toFixed(1)}s</span></div>
      <div>Random Avg: <span class="stat-highlight">${randomMean.toFixed(1)}s</span></div>
      <div>Improvement: <span class="stat-highlight">${improvement.toFixed(1)}%</span></div>
    </div>
    <button class="btn small secondary load-run-btn">Load Results</button>
  `;

  // Add event listener to the load button
  const loadButton = runItem.querySelector('.load-run-btn');
  loadButton.addEventListener('click', function() {
    // Store the current benchmark results to localStorage
    const runData = {
      timestamp: new Date().toISOString(),
      config: {
        transporters: numTransporters,
        randomRuns: randomRuns
      },
      results: {
        optimal: benchmarkResults.ilpMakespan[0],
        random: benchmarkResults.random,
        ilpEqual: benchmarkResults.ilpEqual,
        ilpUrgency: benchmarkResults.ilpUrgency
      },
      workload: workloadData
    };

    localStorage.setItem('current_benchmark', JSON.stringify(runData));

    // Reload the current benchmark
    loadBenchmarkRun(runData);
  });

  // Add to the container (at the beginning)
  recentRunsContainer.insertBefore(runItem, recentRunsContainer.firstChild);

  // Limit to 5 recent runs
  const runItems = recentRunsContainer.querySelectorAll('.benchmark-run-item');
  if (runItems.length > 5) {
    recentRunsContainer.removeChild(runItems[runItems.length - 1]);
  }
}

function loadBenchmarkRun(runData) {
  // Load the saved benchmark data
  benchmarkResults = {
    random: runData.results.random || [],
    ilpMakespan: [runData.results.optimal] || [],
    ilpEqual: runData.results.ilpEqual || [],
    ilpUrgency: runData.results.ilpUrgency || []
  };

  workloadData = runData.workload || {
    random: {},
    ilpMakespan: {},
    ilpEqual: {},
    ilpUrgency: {}
  };

  // Update UI with loaded data
  updateAllResults();
  notifyUser('Benchmark results loaded from saved run.', 'success');
}

// UTILITY FUNCTIONS

function notifyUser(message, type = 'info') {
  // Simple toast notification
  console.log(`[${type.toUpperCase()}] ${message}`);

  // In a real implementation, this would show a toast notification
  // You can add a toast notification library here
}

function exportBenchmarkData() {
  // Create benchmark data object
  const benchmarkData = {
    config: {
      transporters: parseInt(transporterCountSlider.value),
      randomRuns: parseInt(randomRunsSlider.value),
      strategies: getSelectedStrategies(),
      scenarios: getSelectedScenarios()
    },
    results: {
      ilpMakespan: benchmarkResults.ilpMakespan,
      ilpEqual: benchmarkResults.ilpEqual,
      ilpUrgency: benchmarkResults.ilpUrgency,
      random: benchmarkResults.random
    },
    workload: workloadData,
    timestamp: new Date().toISOString()
  };

  // Convert to JSON string
  const jsonStr = JSON.stringify(benchmarkData, null, 2);

  // Create download link
  const blob = new Blob([jsonStr], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `benchmark_${new Date().toISOString().replace(/:/g, '-')}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  notifyUser('Benchmark data exported successfully!', 'success');
}

function saveBenchmarkResults() {
  const benchmarkData = {
    config: {
      transporters: parseInt(transporterCountSlider.value),
      randomRuns: parseInt(randomRunsSlider.value)
    },
    results: {
      optimal: benchmarkResults.ilpMakespan[0],
      random: benchmarkResults.random,
      ilpEqual: benchmarkResults.ilpEqual,
      ilpUrgency: benchmarkResults.ilpUrgency
    },
    workload: workloadData,
    timestamp: new Date().toISOString()
  };

  // Save to localStorage
  const savedRuns = JSON.parse(localStorage.getItem('benchmark_runs') || '[]');
  savedRuns.unshift(benchmarkData);

  // Limit to 10 saved runs
  if (savedRuns.length > 10) {
    savedRuns.pop();
  }

  localStorage.setItem('benchmark_runs', JSON.stringify(savedRuns));
  localStorage.setItem('current_benchmark', JSON.stringify(benchmarkData));

  notifyUser('Benchmark results saved successfully!', 'success');
}

// MODAL FUNCTIONS

function addRequestRow() {
  const requestBuilder = document.getElementById('request-builder');
  const newRow = document.createElement('div');
  newRow.className = 'request-row';

  // Get existing options from the first row to reuse
  const originOptions = document.querySelector('.origin-select').innerHTML;
  const destinationOptions = document.querySelector('.destination-select').innerHTML;

  newRow.innerHTML = `
    <div class="request-cell">
      <select class="origin-select">${originOptions}</select>
    </div>
    <div class="request-cell">
      <select class="destination-select">${destinationOptions}</select>
    </div>
    <div class="request-cell">
      <select class="urgent-select">
        <option value="false">No</option>
        <option value="true">Yes</option>
      </select>
    </div>
    <div class="request-cell">
      <button class="btn small danger remove-request-btn">Remove</button>
    </div>
  `;

  // Add event listener to remove button
  const removeButton = newRow.querySelector('.remove-request-btn');
  removeButton.addEventListener('click', function() {
    requestBuilder.removeChild(newRow);
  });

  requestBuilder.appendChild(newRow);
}

function saveScenario() {
  const scenarioName = document.getElementById('scenario-name').value.trim();
  const requestCount = parseInt(document.getElementById('request-count').value);

  if (!scenarioName) {
    notifyUser('Please enter a scenario name.', 'error');
    return;
  }

  // Collect requests from the builder
  const requests = [];
  const requestRows = document.querySelectorAll('#request-builder .request-row:not(.header)');

  requestRows.forEach(row => {
    const origin = row.querySelector('.origin-select').value;
    const destination = row.querySelector('.destination-select').value;
    const urgent = row.querySelector('.urgent-select').value === 'true';

    if (origin && destination && origin !== destination) {
      requests.push({ origin, destination, urgent });
    }
  });

  if (requests.length === 0) {
    notifyUser('Please add at least one valid request.', 'error');
    return;
  }

  // Create new scenario item
  const scenarioList = document.getElementById('scenario-list');
  const newScenario = document.createElement('div');
  newScenario.className = 'scenario-item';
  newScenario.innerHTML = `
    <div class="scenario-info">
      <div class="scenario-name">${scenarioName}</div>
      <div class="scenario-details">${requests.length} requests, ${requests.filter(r => r.urgent).length} urgent</div>
    </div>
    <label class="switch">
      <input type="checkbox" checked>
      <span class="slider round"></span>
    </label>
  `;

  // Insert before the add button
  const addButton = document.getElementById('add-scenario-btn');
  scenarioList.insertBefore(newScenario, addButton);

  // Close the modal
  document.getElementById('add-scenario-modal').style.display = 'none';

  // Reset the form
  document.getElementById('scenario-name').value = '';
  document.getElementById('request-count').value = '10';

  // Clear the request builder except for the first row
const requestBuilder = document.getElementById('request-builder');
const rowsToRemove = document.querySelectorAll('#request-builder .request-row:not(.header)');
for (let i = 1; i < rowsToRemove.length; i++) {
  requestBuilder.removeChild(rowsToRemove[i]);
}

  notifyUser(`Scenario "${scenarioName}" added successfully.`, 'success');
}

// CALCULATION FUNCTIONS

function calculateMean(values) {
  if (values.length === 0) return 0;
  return values.reduce((sum, val) => sum + val, 0) / values.length;
}

function calculateMedian(values) {
  if (values.length === 0) return 0;

  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);

  return sorted.length % 2 === 0
    ? (sorted[mid - 1] + sorted[mid]) / 2
    : sorted[mid];
}

function calculateStandardDeviation(values) {
  if (values.length <= 1) return 0;

  const mean = calculateMean(values);
  const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length;

  return Math.sqrt(variance);
}

function calculateWorkloadStd(workloadData) {
  const values = Object.values(workloadData);
  return calculateStandardDeviation(values);
}

function generateHistogramLabels(count) {
  return Array.from({ length: count }, (_, i) => `Bin ${i + 1}`);
}

function formatTime(seconds) {
  if (!seconds) return '00:00:00';

  const hrs = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  return `${hrs.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// Initialize benchmark page when script loads
function initializeBenchmarkPage() {
  // Try to load previous benchmark if available
  const savedBenchmark = localStorage.getItem('current_benchmark');
  if (savedBenchmark) {
    try {
      const benchmarkData = JSON.parse(savedBenchmark);
      loadBenchmarkRun(benchmarkData);
    } catch (error) {
      console.error('Error loading saved benchmark:', error);
    }
  }

  // Try to load saved runs
  const savedRuns = localStorage.getItem('benchmark_runs');
  if (savedRuns) {
    try {
      const runs = JSON.parse(savedRuns);

      // Clear existing entries
      const recentRunsContainer = document.querySelector('.recent-runs');
      recentRunsContainer.innerHTML = '';

      // Add each saved run
      runs.forEach(run => {
        const timestamp = new Date(run.timestamp).toLocaleTimeString();
        const numTransporters = run.config.transporters;
        const randomRuns = run.config.randomRuns;
        const optimalTime = run.results.optimal;
        const randomMean = calculateMean(run.results.random);
        const improvement = ((randomMean - optimalTime) / randomMean) * 100;

        const runItem = document.createElement('div');
        runItem.className = 'benchmark-run-item';
        runItem.innerHTML = `
          <div class="benchmark-run-header">
            <span class="benchmark-time">Today, ${timestamp}</span>
            <span class="benchmark-label">${numTransporters} Transporters, ${randomRuns || '100'} Runs</span>
          </div>
          <div class="benchmark-stats">
            <div>Optimal: <span class="stat-highlight">${optimalTime.toFixed(1)}s</span></div>
            <div>Random Avg: <span class="stat-highlight">${randomMean.toFixed(1)}s</span></div>
            <div>Improvement: <span class="stat-highlight">${improvement.toFixed(1)}%</span></div>
          </div>
          <button class="btn small secondary load-run-btn">Load Results</button>
        `;

        // Add event listener to the load button
        const loadButton = runItem.querySelector('.load-run-btn');
        loadButton.addEventListener('click', function() {
          loadBenchmarkRun(run);
        });

        recentRunsContainer.appendChild(runItem);
      });
    } catch (error) {
      console.error('Error loading saved runs:', error);
    }
  }
}

// Call initialization after DOM is loaded (redundant with DOMContentLoaded, but added for clarity)
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeBenchmarkPage);
} else {
  initializeBenchmarkPage();
}