"""
Controller component for benchmark functionality.
Handles application logic and workflow for running benchmarks.
"""

import time
import threading
from Model.Assignment_strategies.ILP.ilp_mode import ILPMode


class BenchmarkController:
    """
    Controller for managing benchmark operations.
    Coordinates between the model and view components.
    """

    def __init__(self, benchmark_model, socketio):
        """
        Initialize the benchmark controller.

        Args:
            benchmark_model: The benchmark model instance
            socketio: SocketIO instance for real-time communication
        """
        self.model = benchmark_model
        self.socketio = socketio
        self.benchmark_thread = None
        self.cancel_flag = False
        self.progress = 0
        self.start_time = 0

    def start_benchmark(self, config):
        """
        Start a benchmark with the given configuration.

        Args:
            config (dict): Benchmark configuration including:
                - transporters: Number of transporters to use
                - random_runs: Number of random simulations to run
                - strategies: List of strategies to benchmark
                - scenarios: List of scenarios to use

        Returns:
            dict: Status message
        """
        # Extract configuration
        num_transporters = config.get("transporters", 3)
        random_runs = config.get("random_runs", 100)
        strategies = config.get("strategies", ["ILP: Makespan", "Random"])
        scenarios = config.get("scenarios", ["Default Scenario"])

        # Cancel existing benchmark if running
        if self.benchmark_thread and self.benchmark_thread.is_alive():
            self.cancel_flag = True
            self.benchmark_thread.join(timeout=1.0)

        # Reset benchmark state
        self.cancel_flag = False
        self.progress = 0
        self.start_time = time.time()

        # Create and start the benchmark thread
        self.benchmark_thread = threading.Thread(
            target=self._run_benchmark_thread,
            args=(num_transporters, random_runs, strategies, scenarios)
        )
        self.benchmark_thread.daemon = True
        self.benchmark_thread.start()

        return {"status": "Benchmark started"}

    def cancel_benchmark(self):
        """
        Cancel a running benchmark.

        Returns:
            dict: Status message
        """
        if self.benchmark_thread and self.benchmark_thread.is_alive():
            self.cancel_flag = True
            return {"status": "Cancelling benchmark"}
        else:
            return {"status": "No benchmark running"}

    def _run_benchmark_thread(self, num_transporters, random_runs, strategies, scenarios):
        """
        Run the benchmark in a background thread.

        Args:
            num_transporters (int): Number of transporters to use
            random_runs (int): Number of random simulations to run
            strategies (list): List of strategy names to benchmark
            scenarios (list): List of scenario names to use
        """
        try:
            # Loop through all scenarios
            for scenario_name in scenarios:
                if self.cancel_flag:
                    self.socketio.emit("benchmark_complete", {"cancelled": True})
                    return

                # Get the scenario requests
                requests = self.model.get_scenario(scenario_name)

                # Run ILP Makespan benchmark (always run this as baseline)
                if "ILP: Makespan" in strategies:
                    self._update_progress(5, f"Running ILP Makespan optimization for {scenario_name}")
                    ilp_results = self.model.run_ilp_benchmark(
                        num_transporters, requests, ILPMode.MAKESPAN
                    )

                    # Emit results
                    self.socketio.emit("benchmark_results", {
                        "strategy": "ILP: Makespan",
                        "times": [ilp_results["makespan"]],
                        "workload": ilp_results["workload"]
                    })

                # Run ILP Equal Workload benchmark
                if "ILP: Equal Workload" in strategies:
                    self._update_progress(15, f"Running ILP Equal Workload optimization for {scenario_name}")
                    ilp_equal_results = self.model.run_ilp_benchmark(
                        num_transporters, requests, ILPMode.EQUAL_WORKLOAD
                    )

                    # Emit results
                    self.socketio.emit("benchmark_results", {
                        "strategy": "ILP: Equal Workload",
                        "times": [ilp_equal_results["makespan"]],
                        "workload": ilp_equal_results["workload"]
                    })

                # Run ILP Urgency First benchmark
                if "ILP: Urgency First" in strategies:
                    self._update_progress(25, f"Running ILP Urgency First optimization for {scenario_name}")
                    ilp_urgency_results = self.model.run_ilp_benchmark(
                        num_transporters, requests, ILPMode.URGENCY_FIRST
                    )

                    # Emit results
                    self.socketio.emit("benchmark_results", {
                        "strategy": "ILP: Urgency First",
                        "times": [ilp_urgency_results["makespan"]],
                        "workload": ilp_urgency_results["workload"]
                    })

                # Run Random benchmark with multiple iterations
                if "Random" in strategies:
                    self._update_progress(30, f"Starting Random simulations for {scenario_name}")

                    # Run all random simulations in one go
                    random_results = self.model.run_random_benchmark(
                        num_transporters, requests, random_runs
                    )

                    # Extract just the makespan times
                    random_times = [r["makespan"] for r in random_results]

                    # Get workload from first run
                    random_workload = random_results[0]["workload"] if random_results else {}

                    # Update progress incrementally during random runs
                    for i in range(random_runs):
                        if self.cancel_flag:
                            self.socketio.emit("benchmark_complete", {"cancelled": True})
                            return

                        # Update progress every 10 runs or for each run if fewer than 10
                        if i % max(1, random_runs // 10) == 0:
                            progress = 30 + int((i / random_runs) * 70)
                            self._update_progress(
                                progress, f"Processed Random simulation ({i + 1}/{random_runs})"
                            )

                    # Emit random results
                    self.socketio.emit("benchmark_results", {
                        "strategy": "Random",
                        "times": random_times,
                        "workload": random_workload
                    })

            # Emit benchmark complete
            self._update_progress(100, "Benchmark complete")
            time.sleep(0.5)  # Give a moment for final progress update
            self.socketio.emit("benchmark_complete", {"success": True})

        except Exception as e:
            print(f"Error in benchmark: {str(e)}")
            self.socketio.emit("benchmark_complete", {"error": str(e)})

    def _update_progress(self, progress, current_task):
        """
        Update the benchmark progress and emit a progress event.

        Args:
            progress (int): Progress percentage (0-100)
            current_task (str): Description of current task
        """
        self.progress = progress
        elapsed = time.time() - self.start_time

        # Estimate completion time
        if progress > 0:
            estimated_total = elapsed * 100 / progress
            estimated_remaining = estimated_total - elapsed
        else:
            estimated_remaining = 0

        # Emit progress event
        self.socketio.emit("benchmark_progress", {
            "progress": progress,
            "current_task": current_task,
            "elapsed_time": elapsed,
            "estimated_completion": estimated_remaining
        })

    def get_available_scenarios(self):
        """
        Get the list of available benchmark scenarios.

        Returns:
            list: List of scenario names
        """
        return list(self.model.scenarios.keys())

    def add_custom_scenario(self, name, requests):
        """
        Add a custom scenario for benchmarking.

        Args:
            name (str): Scenario name
            requests (list): List of request tuples (origin, destination, urgent)

        Returns:
            list: Updated list of scenario names
        """
        self.model.add_scenario(name, requests)
        return self.get_available_scenarios()