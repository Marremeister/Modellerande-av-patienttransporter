import time
import numpy as np
import matplotlib.pyplot as plt
from benchmark_plotter import BenchmarkAnalysis

from hospital_controller import HospitalController

# Define standard benchmark requests
benchmark_requests = [
    ("Emergency", "ICU"),
    ("Reception", "Radiology"),
    ("ICU", "General Ward"),
    ("Cardiology", "Surgery"),
    ("Pharmacy", "Neurology"),
    ("Pediatrics", "Orthopedics"),
    ("Admin Office", "Cafeteria"),
    ("Radiology", "Laboratory"),
    ("Emergency", "Surgery"),
    ("Reception", "Cardiology"),
    ("Emergency", "ICU"),
    ("Reception", "Radiology"),
    ("ICU", "General Ward"),
    ("Cardiology", "Surgery"),
    ("Pharmacy", "Neurology"),
    ("Pediatrics", "Orthopedics"),
    ("Admin Office", "Cafeteria"),
    ("Radiology", "Laboratory"),
    ("Emergency", "Surgery"),
    ("Reception", "Cardiology")
]

def run_benchmark(system, strategy_type="ilp", runs=1, transporter_names=None):
    durations = []
    transporter_names = transporter_names or ["Anna", "Bob"]

    for _ in range(runs):
        _reset_system(system)
        _add_transporters(system, transporter_names)

        for origin, dest in benchmark_requests:
            system.create_transport_request(origin, dest)

        if strategy_type == "random":
            system.enable_random_mode()
        else:
            system.enable_optimized_mode()

        # 🎯 Simulate the plan instead of running it
        transporters = system.transport_manager.get_transporter_objects()
        pending = system.transport_manager.pending_requests
        graph = system.hospital.get_graph()

        strategy = system.transport_manager.assignment_strategy
        assignment_plan = strategy.generate_assignment_plan(transporters, pending, graph)

        if not assignment_plan:
            durations.append(float('inf'))
            continue

        # 🔍 Simulate completion time per transporter
        max_duration = 0
        for transporter in transporters:
            total_time = 0
            tasks = assignment_plan.get(transporter.name, [])
            for task in tasks:
                total_time += strategy.estimate_travel_time(transporter, task)
            max_duration = max(max_duration, total_time)

        durations.append(max_duration)

    return durations



def _reset_system(system):
    system.transport_manager.transporters = []
    system.transport_manager.pending_requests = []
    system.transport_manager.ongoing_requests = []
    system.transport_manager.completed_requests = []


def _add_transporters(system, names):
    for name in names:
        system.add_transporter(name)


def main():
    controller = HospitalController()
    system = controller.system
    system.initialize()

    scenarios = {
        "1 Transporter": ["Alpha"],
        "2 Transporters": ["Alpha", "Beta"],
        "5 Transporters": ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"],
        "10 Transporters": ["Alpha", "Beta", "Gamma", "Delta", "Epsilon", "Zeta", "Eta", "Theta", "Iota", "Kappa"]
    }

    for label, transporters in scenarios.items():
        print(f"\n🔬 Benchmarking: {label}")

        optimal = run_benchmark(system, "ilp", runs=1, transporter_names=transporters)
        random = run_benchmark(system, "random", runs=1000, transporter_names=transporters)

        print(f"  ✅ Optimal: {optimal[0]:.2f} sec")
        print(f"  🎲 Random Mean: {np.mean(random):.2f} sec")
        print(f"  📉 Median: {np.median(random):.2f}")
        print(f"  🔢 25th Percentile: {np.percentile(random, 25):.2f}")
        print(f"  🔢 75th Percentile: {np.percentile(random, 75):.2f}")


        # Optional: Plot
        plt.hist(random, bins=10, alpha=0.6, label='Random Strategy')
        plt.axvline(optimal[0], color='red', linestyle='dashed', linewidth=2, label='Optimal Time')
        plt.title(f"Benchmark: {label}")
        plt.xlabel("Completion Time (s)")
        plt.ylabel("Frequency")
        plt.legend()
        plt.show()

        # 🔍 Detailed visual analysis with optimal reference
        fig = plt.figure(figsize=(14, 10), constrained_layout=True)
        gs = fig.add_gridspec(2, 2)

        # Histogram with optimal line
        ax_hist = fig.add_subplot(gs[0, :])
        ax_hist.hist(random, bins=10, edgecolor='black', alpha=0.7, label='Random Times')
        ax_hist.axvline(np.mean(random), color='red', linestyle='dashed', linewidth=2,
                        label=f'Mean: {np.mean(random):.1f}')
        ax_hist.axvline(np.median(random), color='green', linestyle='dashed', linewidth=2,
                        label=f'Median: {np.median(random):.1f}')
        ax_hist.axvline(optimal[0], color='blue', linestyle='dashed', linewidth=2, label=f'Optimal: {optimal[0]:.1f}')
        ax_hist.set_title(f'Histogram of Completion Times ({label})')
        ax_hist.set_xlabel('Completion Time (seconds)')
        ax_hist.set_ylabel('Frequency')
        ax_hist.legend()
        ax_hist.grid(axis='y', linestyle='--', alpha=0.7)

        # CDF with optimal line
        ax_cdf = fig.add_subplot(gs[1, 0])
        sorted_times = np.sort(random)
        cdf = np.arange(1, len(sorted_times) + 1) / len(sorted_times)
        ax_cdf.plot(sorted_times, cdf, marker='.', linestyle='none', label='Random CDF')
        ax_cdf.axvline(optimal[0], color='blue', linestyle='dashed', linewidth=2, label=f'Optimal: {optimal[0]:.1f}')
        ax_cdf.set_title(f'CDF of Completion Times ({label})')
        ax_cdf.set_xlabel('Completion Time (seconds)')
        ax_cdf.set_ylabel('CDF')
        ax_cdf.legend()

        # Summary bar chart with optimal as a horizontal line
        ax_summary = fig.add_subplot(gs[1, 1])
        summary_labels = ['Mean', 'Median', 'Std', 'Max', '25th', '75th']
        summary_vals = [
            np.mean(random),
            np.median(random),
            np.std(random),
            np.max(random),
            np.percentile(random, 25),
            np.percentile(random, 75)
        ]
        ax_summary.bar(summary_labels, summary_vals, color='skyblue')
        ax_summary.axhline(optimal[0], color='blue', linestyle='dashed', linewidth=2,
                           label=f'Optimal: {optimal[0]:.1f}')
        ax_summary.set_title(f'Summary Metrics ({label})')
        ax_summary.set_ylabel('Seconds')
        ax_summary.legend()

        plt.show()


if __name__ == "__main__":
    main()
