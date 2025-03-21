import seaborn as sns
import matplotlib.pyplot as plt

class Plot:
    def __init__(self, xlabel, ylabel, title, plot_type, **kwargs):
        self.xlabel = xlabel
        self.ylabel = ylabel
        self.title = title
        self.plot_type = plot_type
        self.kwargs = kwargs

    def render(self, ax):
        if self.plot_type == 'bar':
            sns.barplot(ax=ax, **self.kwargs)
        elif self.plot_type == 'hist':
            data = self.kwargs.get('x')
            bins = self.kwargs.get('bins', 20)
            ax.hist(data, bins=bins, edgecolor='black', alpha=0.7)
            # Om medianvärde skickas med, rita ut en vertikal linje
            if 'median' in self.kwargs:
                median_val = self.kwargs['median']
                ax.axvline(median_val, color='red', linestyle='dashed', linewidth=2,
                           label=f'Median: {median_val:.1f}')
                ax.legend()
        ax.set_xlabel(self.xlabel)
        ax.set_ylabel(self.ylabel)
        ax.set_title(self.title)
        ax.grid(axis='y', linestyle='--', alpha=0.7)


class Plotter:
    def __init__(self):
        self.plots = []

    def add_plot(self, plot):
        self.plots.append(plot)

    def show_plots(self):
        num_plots = len(self.plots)
        rows = (num_plots + 2) // 3  # Ensure 3 per row
        fig, axes = plt.subplots(rows, 3, figsize=(18, 6 * rows))
        axes = axes.flatten()

        for i, plot in enumerate(self.plots):
            plot.render(axes[i])

        for j in range(i + 1, len(axes)):
            fig.delaxes(axes[j])  # Remove unused axes

        plt.tight_layout()
        plt.show(block=True)

