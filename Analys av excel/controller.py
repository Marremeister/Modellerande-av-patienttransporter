from analysverktyg import DataLoader, RouteTransportTable
from queue import QueueingAnalysis
from workload import HourlyWorkloadAnalysis
from plotters import Plotter
from scrollable_table import ScrollableTable


def run():
    file_path = "Columna Sahlgrenska 2024 Anomymiserad data.csv"

    # Load and process data using the 10% fastest per route
    data_loader = DataLoader(file_path)
    data_loader.load_and_process_data(route_percentage=10)

    # Calculate workload data once (for hourly workload plots)
    workload_analysis = HourlyWorkloadAnalysis(data_loader.df, None)
    workload_analysis.calculate_workload_data()

    # First set: Hourly workload histograms (6 separate histograms)
    plotter1 = Plotter()
    workload_analysis.plot_hourly_workload(plotter=plotter1)
    plotter1.show_plots()  # Displays the 6 histograms in one window

    # Second set: Transporter workload bar charts (one per selected hour)
    plotter2 = Plotter()
    workload_analysis.plot_transporter_workload_by_hour(plotter=plotter2)
    plotter2.show_plots()  # Displays 6 bar charts in a separate window

    # Queueing analysis (both recalculated and raw waiting times)
    queueing_analysis = QueueingAnalysis(data_loader.df)
    queueing_analysis.queueing_analysis()  # Recalculated waiting time analysis
    queueing_analysis.queueing_analysis_raw()  # Raw waiting time analysis

    # Create the route transport table DataFrame and display it in a scrollable window
    route_table = RouteTransportTable(data_loader.df)
    table_df = route_table.get_table_data()
    print("Route table created with", len(table_df), "rows.")
    scroll_table = ScrollableTable(table_df)
    scroll_table.show()


if __name__ == "__main__":
    run()
