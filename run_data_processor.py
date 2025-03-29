# run_data_processor.py
"""
Script to analyze transport data from Excel file and build a hospital graph.
"""
import os
import sys
import logging
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from Model.Data_processor import TransportDataAnalyzer, HospitalGraphBuilder, CoordinateGenerator
from Model.hospital_model import Hospital

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TransportDataAnalysis")


def analyze_data(file_path, output_dir='analysis_output'):
    """
    Analyze transport data from Excel file and generate a hospital graph.

    Args:
        file_path: Path to Excel file with transport data
        output_dir: Directory to save analysis results

    Returns:
        tuple: (hospital_graph, analyzer, builder) for further use
    """
    # Create output directory if needed
    os.makedirs(output_dir, exist_ok=True)

    # Initialize analyzer
    logger.info(f"Initializing data analyzer for {file_path}")
    analyzer = TransportDataAnalyzer(file_path)

    # Load and clean the data
    if not analyzer.load_data():
        logger.error("Failed to load data. Exiting.")
        return None, None, None

    cleaned_data = analyzer.clean_data()
    if cleaned_data is None or cleaned_data.empty:
        logger.error("Failed to clean data. Exiting.")
        return None, None, None

    # Generate analysis visualizations
    logger.info("Generating analysis visualizations...")

    # 1. Hourly request distribution
    hourly_dist = analyzer.get_hourly_request_distribution()
    _plot_hourly_distribution(hourly_dist, os.path.join(output_dir, 'hourly_distribution.png'))

    # 2. Transport frequency matrix
    freq_matrix = analyzer.get_frequency_matrix()
    if freq_matrix is not None:
        _plot_frequency_matrix(freq_matrix, os.path.join(output_dir, 'transport_frequency.png'))

    # 3. Create origin-destination frequency file
    _export_origin_destination_pairs(analyzer, os.path.join(output_dir, 'od_pairs.csv'))

    # Build hospital graph
    logger.info("Building hospital graph...")
    builder = HospitalGraphBuilder(analyzer, time_factor=0.1)  # Scale times to make simulation faster
    graph = builder.build_graph(path_threshold=1.25)

    # Ensure graph is connected
    builder.validate_graph_connectivity()

    # Generate coordinates
    logger.info("Generating coordinates for graph nodes...")
    coord_generator = CoordinateGenerator(graph, canvas_width=1400, canvas_height=1000)

    # Try force-directed layout first
    try:
        coord_generator.generate_coordinates(iterations=500)
    except Exception as e:
        logger.warning(f"Force-directed layout failed: {str(e)}")
        logger.info("Falling back to simple layout...")
        coord_generator.generate_simple_coordinates()

    # Adjust coordinates by department type
    coord_generator.adjust_coordinates_by_department_type()

    # Apply jitter to avoid perfect overlaps
    coord_generator.apply_jitter()

    # Export coordinates
    coord_generator.export_coordinates(os.path.join(output_dir, 'node_coordinates.json'))

    # Create a Hospital instance with the graph
    hospital = Hospital()
    hospital.graph = graph

    logger.info(f"Analysis complete. Results saved to {output_dir}")

    return hospital, analyzer, builder


def _plot_hourly_distribution(hourly_dist, output_file):
    """Plot hourly distribution of transport requests."""
    plt.figure(figsize=(12, 6))

    # Sort by hour
    hours = sorted(hourly_dist.keys())
    counts = [hourly_dist[h] for h in hours]

    # Plot
    plt.bar(hours, counts, color='#3498db')
    plt.xlabel('Hour of Day')
    plt.ylabel('Number of Requests')
    plt.title('Transport Requests by Hour')
    plt.xticks(range(0, 24))
    plt.grid(axis='y', linestyle='--', alpha=0.7)

    # Save
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()


def _plot_frequency_matrix(freq_matrix, output_file):
    """Plot heatmap of transport frequencies between departments."""
    plt.figure(figsize=(14, 12))

    # Use seaborn for better heatmap
    mask = freq_matrix == 0  # Mask cells with zero frequency
    ax = sns.heatmap(freq_matrix, cmap="YlGnBu", linewidths=0.5,
                     cbar_kws={"shrink": 0.8}, mask=mask)

    plt.title('Transport Frequency Between Departments')
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()


def _export_origin_destination_pairs(analyzer, output_file):
    """Export origin-destination pairs with frequencies and median times."""
    median_times = analyzer.get_median_transport_times()

    # Convert to DataFrame for easier manipulation
    data = []
    for (origin, dest), time in median_times.items():
        data.append({
            'Origin': origin,
            'Destination': dest,
            'MedianTimeSeconds': time
        })

    df = pd.DataFrame(data)

    # Count occurrences from cleaned data
    origin_col = analyzer._find_column_containing('origin', analyzer.cleaned_data.columns)
    dest_col = analyzer._find_column_containing('destination', analyzer.cleaned_data.columns)

    if origin_col and dest_col:
        count_df = analyzer.cleaned_data.groupby([origin_col, dest_col]).size().reset_index()
        count_df.columns = ['Origin', 'Destination', 'Frequency']

        # Merge with median times
        result = pd.merge(df, count_df, on=['Origin', 'Destination'], how='left')
        result['Frequency'] = result['Frequency'].fillna(0)
    else:
        # No frequency data available
        result = df
        result['Frequency'] = 0

    # Sort by frequency (descending)
    result = result.sort_values('Frequency', ascending=False)

    # Save to CSV
    result.to_csv(output_file, index=False)


def initialize_hospital_from_data(file_path, output_dir='analysis_output'):
    """
    Initialize a hospital from transport data file.

    Args:
        file_path: Path to Excel file with transport data
        output_dir: Directory to save analysis results

    Returns:
        Hospital: Hospital instance with graph populated from data
    """
    hospital, _, _ = analyze_data(file_path, output_dir)
    return hospital


if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) < 2:
        print("Usage: python run_data_processor.py <path_to_excel_file> [output_directory]")
        sys.exit(1)

    file_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'analysis_output'

    # Run analysis
    hospital, analyzer, builder = analyze_data(file_path, output_dir)

    # Print summary
    if hospital and hospital.graph:
        print("\nGraph Summary:")
        print(f"  Nodes: {len(hospital.graph.get_nodes())}")
        print(
            f"  Edges: {sum(len(edges) for edges in hospital.graph.adjacency_list.values()) // 2}")  # Divide by 2 for undirected graph

        # Print some sample paths
        nodes = hospital.graph.get_nodes()
        if len(nodes) >= 2:
            from Model.model_pathfinder import Pathfinder

            pathfinder = Pathfinder(hospital)

            print("\nSample Paths:")
            for _ in range(3):
                source = nodes[0]
                target = nodes[-1]

                try:
                    path, distance = pathfinder.dijkstra(source, target)
                    print(f"  Path from {source} to {target}:")
                    print(f"    Distance: {distance:.2f} seconds")
                    print(f"    Path: {' -> '.join(path)}")
                except Exception as e:
                    print(f"  Error finding path: {str(e)}")