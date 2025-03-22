# benchmark_controller.py
import numpy as np
from benchmark_model import BenchmarkModel
from benchmark.benchmark_plotter import BenchmarkAnalysis

class BenchmarkController:
    def __init__(self, system):
        self.model = BenchmarkModel(system)

    # benchmark_controller.py
    def run_and_plot(self, scenario_label, transporter_names, requests):
        optimal_times = self.model.run_benchmark("ilp", 1, transporter_names, requests)
        random_times = self.model.run_benchmark("random", 1000, transporter_names, requests)

        opt_workload = self.model.get_workload_distribution("ilp", transporter_names, requests)
        rand_workload = self.model.get_workload_distribution("random", transporter_names, requests)

        print(f"\n🔬 {scenario_label}")
        print(f"✅ Optimal Time: {optimal_times[0]:.2f} sec")
        print(f"🎲 Random Avg:  {np.mean(random_times):.2f} sec")

        opt_std = self.model.calculate_workload_std(opt_workload)
        rand_std = self.model.calculate_workload_std(rand_workload)

        results = {scenario_label: random_times}
        optimal_ref = {scenario_label: optimal_times[0]}
        view = BenchmarkAnalysis(results, optimal_ref)

        view.analyze_all()
        view.plot_side_by_side_workload(opt_workload, rand_workload)
        view.print_workload_stats(opt_workload, "Optimal")
        view.print_workload_stats(rand_workload, "Random")

