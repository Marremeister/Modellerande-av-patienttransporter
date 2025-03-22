# benchmark_controller.py
import numpy as np
from benchmark_model import BenchmarkModel
from benchmark.benchmark_plotter import BenchmarkAnalysis

class BenchmarkController:
    def __init__(self, system):
        self.model = BenchmarkModel(system)

    def run_and_plot(self, scenario_label, transporter_names, requests):
        # Run both strategies
        optimal = self.model.run_benchmark("ilp", 1, transporter_names, requests)
        random = self.model.run_benchmark("random", 1000, transporter_names, requests)

        # Print metrics
        print(f"\n🔬 {scenario_label}")
        print(f"✅ Optimal: {optimal[0]:.2f} sec")
        print(f"🎲 Random Avg: {np.mean(random):.2f} sec")
        print(f"   Median: {np.median(random):.2f} sec")
        print(f"   25th Percentile: {np.percentile(random, 25):.2f} sec")
        print(f"   75th Percentile: {np.percentile(random, 75):.2f} sec")

        # Build results dict
        results = {scenario_label: random}
        optimal_dict = {scenario_label: optimal[0]}  # ✅ So the view knows what to show

        # Pass to view
        view = BenchmarkAnalysis(results_dict=results, optimal_times=optimal_dict)
        view.analyze_all()
