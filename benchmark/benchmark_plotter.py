import matplotlib.pyplot as plt
import numpy as np
import matplotlib.gridspec as gridspec


class BenchmarkAnalysis:
    def __init__(self, results_dict, optimal_times=None):
        """
        results_dict: Dictionary with scenario labels as keys and list of durations as values.
        optimal_times: Optional dictionary with optimal duration per scenario for visual reference.
        """
        self.results_dict = results_dict
        self.optimal_times = optimal_times or {}

    def plot_main_histogram(self, times, ax, label_prefix=""):
        mean_val = np.mean(times)
        median_val = np.median(times)
        label = label_prefix.strip()

        ax.hist(times, bins=10, edgecolor='black', alpha=0.7)
        ax.axvline(mean_val, color='red', linestyle='dashed', linewidth=2, label=f'{label_prefix}Mean: {mean_val:.1f}')
        ax.axvline(median_val, color='green', linestyle='dashed', linewidth=2,
                   label=f'{label_prefix}Median: {median_val:.1f}')

        # Draw optimal time if available
        if label in self.optimal_times:
            optimal = self.optimal_times[label]
            ax.axvline(optimal, color='blue', linestyle='dotted', linewidth=2, label=f'Optimal: {optimal:.1f}')

        ax.set_xlabel(f'{label_prefix}Completion Time (seconds)')
        ax.set_ylabel('Frequency')
        ax.set_title(f'Histogram of {label_prefix}Completion Times')
        ax.legend()
        ax.grid(axis='y', linestyle='--', alpha=0.7)

    def plot_cdf(self, times, ax, label_prefix=""):
        sorted_times = np.sort(times)
        cdf = np.arange(1, len(sorted_times) + 1) / len(sorted_times)
        ax.plot(sorted_times, cdf, marker='.', linestyle='none')
        ax.set_xlabel(f'{label_prefix}Completion Time (seconds)')
        ax.set_ylabel('CDF')
        ax.set_title(f'CDF of {label_prefix}Completion Times')

    def plot_summary_metrics(self, times, ax, label_prefix=""):
        metrics = ['Mean', 'Median', 'Std', 'Max', '25th', '75th']
        values = [
            np.mean(times),
            np.median(times),
            np.std(times),
            np.max(times),
            np.percentile(times, 25),
            np.percentile(times, 75)
        ]
        ax.bar(metrics, values, color='skyblue')
        ax.set_title(f'Summary Metrics ({label_prefix.strip()})')
        ax.set_ylabel('Seconds')

    def analyze_all(self):
        for label, times in self.results_dict.items():
            times = np.array(times)
            fig = plt.figure(figsize=(14, 10), constrained_layout=True)
            gs = fig.add_gridspec(2, 2)

            ax_main = fig.add_subplot(gs[0, :])
            self.plot_main_histogram(times, ax_main, label_prefix=label + " ")

            ax_cdf = fig.add_subplot(gs[1, 0])
            self.plot_cdf(times, ax_cdf, label_prefix=label + " ")

            ax_summary = fig.add_subplot(gs[1, 1])
            self.plot_summary_metrics(times, ax_summary, label_prefix=label + " ")

            plt.show()
