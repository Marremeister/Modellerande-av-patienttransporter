import pandas as pd
import matplotlib.pyplot as plt
import time
from plotters import Plot
import matplotlib.gridspec as gridspec


class QueueingAnalysis:
    def __init__(self, df):
        self.df = df

    def plot_main_histogram(self, waiting_times, ax, label_prefix=""):
        """
        Plot a histogram of waiting times with mean and median lines.
        """
        mean_wait = waiting_times.mean()
        median_wait = waiting_times.median()

        ax.hist(waiting_times, bins=range(0, 310, 10), edgecolor='black', alpha=0.7)
        ax.axvline(mean_wait, color='red', linestyle='dashed', linewidth=2,
                   label=f'{label_prefix}Mean: {mean_wait:.1f}')
        ax.axvline(median_wait, color='green', linestyle='dashed', linewidth=2,
                   label=f'{label_prefix}Median: {median_wait:.1f}')
        ax.set_xlabel(f'{label_prefix}Waiting Time (minutes)')
        ax.set_ylabel('Frequency')
        ax.set_title(f'Histogram of {label_prefix}Waiting Times')
        ax.legend()
        ax.grid(axis='y', linestyle='--', alpha=0.7)

    def plot_cdf(self, waiting_times, ax, label_prefix=""):
        """
        Plot the cumulative distribution function (CDF) of waiting times.
        """
        sorted_wait = waiting_times.sort_values()
        cdf = sorted_wait.rank(method='average', pct=True)
        ax.plot(sorted_wait, cdf, marker='.', linestyle='none')
        ax.set_xlabel(f'{label_prefix}Waiting Time (minutes)')
        ax.set_ylabel('CDF')
        ax.set_title(f'CDF of {label_prefix}Waiting Times')

    def plot_summary_metrics(self, waiting_times, ax, label_prefix=""):
        """
        Plot a bar chart with summary metrics of waiting times.
        """
        mean_wait = waiting_times.mean()
        median_wait = waiting_times.median()
        std_wait = waiting_times.std()
        max_wait = waiting_times.max()
        p90 = waiting_times.quantile(0.90)
        p95 = waiting_times.quantile(0.95)
        p99 = waiting_times.quantile(0.99)

        metrics = ['Mean', 'Median', 'Std', 'Max', '90th', '95th', '99th']
        values = [mean_wait, median_wait, std_wait, max_wait, p90, p95, p99]
        ax.bar(metrics, values, color='skyblue')
        ax.set_title(f'Summary Metrics ({label_prefix.strip()})')
        ax.set_ylabel('Minutes')

    def detailed_queueing_analysis(self):
        """
        Create a detailed analysis figure using recalculated waiting times
        (Real Waiting Time = Real Start Time - Skapad Tid).
        """
        if self.df is None or 'Real Waiting Time (minutes)' not in self.df.columns:
            print("Skipping Recalculated Queueing Analysis due to missing data.")
            return

        waiting_times = self.df['Real Waiting Time (minutes)']
        waiting_times = waiting_times[waiting_times >= 0]

        fig = plt.figure(figsize=(14, 10), constrained_layout=True)
        gs = fig.add_gridspec(2, 2)

        ax_main = fig.add_subplot(gs[0, :])
        self.plot_main_histogram(waiting_times, ax_main, label_prefix="Recalculated ")

        ax_cdf = fig.add_subplot(gs[1, 0])
        self.plot_cdf(waiting_times, ax_cdf, label_prefix="Recalculated ")

        ax_summary = fig.add_subplot(gs[1, 1])
        self.plot_summary_metrics(waiting_times, ax_summary, label_prefix="Recalculated ")

        plt.show()

    def detailed_queueing_analysis_raw(self):
        """
        Create a detailed analysis figure using raw waiting times
        (Raw Waiting Time = Uppdrag Sluttid - Skapad Tid), with values above 300 minutes removed.
        """
        if self.df is None or 'Skapad Tid' not in self.df.columns or 'Uppdrag Sluttid' not in self.df.columns:
            print("Skipping Raw Queueing Analysis due to missing data.")
            return

        raw_waiting_time = (self.df['Uppdrag Sluttid'] - self.df['Skapad Tid']).dt.total_seconds() / 60
        # Filter out negative values and values above 300 minutes
        raw_waiting_time = raw_waiting_time[(raw_waiting_time >= 0) & (raw_waiting_time <= 300)]

        fig = plt.figure(figsize=(14, 10), constrained_layout=True)
        gs = fig.add_gridspec(2, 2)

        ax_main = fig.add_subplot(gs[0, :])
        self.plot_main_histogram(raw_waiting_time, ax_main, label_prefix="Raw ")

        ax_cdf = fig.add_subplot(gs[1, 0])
        self.plot_cdf(raw_waiting_time, ax_cdf, label_prefix="Raw ")

        ax_summary = fig.add_subplot(gs[1, 1])
        self.plot_summary_metrics(raw_waiting_time, ax_summary, label_prefix="Raw ")

        plt.show()

    # Aliases for convenience:
    def queueing_analysis(self):
        self.detailed_queueing_analysis()

    def queueing_analysis_raw(self):
        self.detailed_queueing_analysis_raw()