# Model/data_processor/transport_data_analyzer.py
"""
Class for analyzing hospital transport data from Excel files.
"""
import pandas as pd
import numpy as np
from datetime import datetime
import logging


class TransportDataAnalyzer:
    """
    Analyzes transport data from Excel files to extract patterns, clean data,
    and prepare for graph building.
    """

    def __init__(self, file_path):
        """
        Initialize the TransportDataAnalyzer with a file path.

        Args:
            file_path (str): Path to the Excel file containing transport data
        """
        self.file_path = file_path
        self.data = None
        self.cleaned_data = None
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Set up a logger for the TransportDataAnalyzer."""
        logger = logging.getLogger("TransportDataAnalyzer")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        return logger

    def load_data(self):
        """
        Load data from the file, using semicolon delimiter for CSV.
        """
        self.logger.info(f"Loading data from {self.file_path}")
        try:
            # Check file extension
            if self.file_path.lower().endswith('.csv'):
                # Use semicolon as delimiter with newer pandas parameter name
                self.data = pd.read_csv(
                    self.file_path,
                    delimiter=';',
                    on_bad_lines='warn',  # For newer pandas versions
                    low_memory=False  # Better for inconsistent data
                )
            else:
                # Excel file
                self.data = pd.read_excel(self.file_path)

            self.logger.info(f"Loaded {len(self.data)} rows of data with {len(self.data.columns)} columns")
            self.logger.info(f"Columns: {list(self.data.columns)}")
            return True
        except Exception as e:
            self.logger.error(f"Error loading data: {str(e)}")
            return False

    def clean_data(self):
        """
        Clean the data by removing invalid entries, such as:
        - Negative transport times
        - Missing origin/destination
        - Extremely long transport times (outliers)

        Returns:
            pd.DataFrame: Cleaned DataFrame
        """
        if self.data is None:
            self.logger.error("No data loaded. Call load_data() first.")
            return None

        self.logger.info("Cleaning data...")
        df = self.data.copy()

        # Record initial size
        initial_size = len(df)

        # Map Swedish column names to expected ones
        # Based on the columns we saw in the logs
        column_mapping = {
            'origin': 'Startplats',  # Origin location
            'destination': 'Slutplats',  # Destination location
            'start': 'Starttid',  # Start time
            'end': 'Uppdrag Sluttid'  # End time
        }

        # Log the identified columns
        self.logger.info(f"Using columns: Origin={column_mapping['origin']}, "
                         f"Destination={column_mapping['destination']}, "
                         f"Start Time={column_mapping['start']}, "
                         f"End Time={column_mapping['end']}")

        # Remove rows with missing origin or destination
        if column_mapping['origin'] in df.columns and column_mapping['destination'] in df.columns:
            df.dropna(subset=[column_mapping['origin'], column_mapping['destination']], inplace=True)
            self.logger.info(f"Removed {initial_size - len(df)} rows with missing origin/destination")
            initial_size = len(df)
        else:
            self.logger.warning(f"Could not find expected origin/destination columns")
            self.logger.info(f"Available columns: {', '.join(df.columns[:10])}... (and more)")

        # Calculate transport times if start and end times exist
        if column_mapping['start'] in df.columns and column_mapping['end'] in df.columns:
            # Try to convert to datetime with explicit European format
            for col in [column_mapping['start'], column_mapping['end']]:
                if not pd.api.types.is_datetime64_any_dtype(df[col]):
                    try:
                        # Use explicit format: DD-MM-YYYY HH:MM:SS
                        df[col] = pd.to_datetime(df[col], format='%d-%m-%Y %H:%M:%S')
                    except Exception as e:
                        self.logger.warning(f"Could not convert {col} to datetime: {str(e)}")

                        # Try with dayfirst=True as a fallback
                        try:
                            df[col] = pd.to_datetime(df[col], dayfirst=True)
                        except Exception as e2:
                            self.logger.error(f"Fallback datetime conversion also failed: {str(e2)}")

            # Calculate transport time in seconds
            try:
                df['transport_time'] = (df[column_mapping['end']] - df[column_mapping['start']]).dt.total_seconds()

                # Remove negative transport times
                negative_count = len(df[df['transport_time'] < 0])
                df = df[df['transport_time'] >= 0]
                self.logger.info(f"Removed {negative_count} rows with negative transport times")

                # Remove extreme outliers (transport times more than 3 hours)
                outlier_count = len(df[df['transport_time'] > 3 * 60 * 60])
                df = df[df['transport_time'] <= 3 * 60 * 60]
                self.logger.info(f"Removed {outlier_count} rows with transport times > 3 hours")
            except Exception as e:
                self.logger.error(f"Error calculating transport times: {str(e)}")
                # If transport_time calculation fails, create a default one
                try:
                    # Add a placeholder transport_time column
                    df['transport_time'] = 300  # Default 5 minutes
                    self.logger.warning("Created placeholder transport_time column with default values")
                except Exception as e2:
                    self.logger.error(f"Could not create placeholder transport_time: {str(e2)}")
        else:
            self.logger.warning(f"Could not find expected start/end time columns")

        self.cleaned_data = df
        self.logger.info(f"Data cleaning complete. Remaining rows: {len(df)}")

        # Store column mapping for other methods to use
        self._column_mapping = column_mapping

        return df

    def _find_column_containing(self, keyword, columns):
        """Find a column matching a given keyword or use predefined mapping."""
        # First check if we have a mapping
        if hasattr(self, '_column_mapping') and keyword in self._column_mapping:
            mapped_col = self._column_mapping[keyword]
            if mapped_col in columns:
                return mapped_col

        # Fall back to the original method
        matches = [col for col in columns if keyword.lower() in col.lower()]
        return matches[0] if matches else None

    def get_origin_destination_pairs(self):
        """
        Get all unique origin-destination pairs from the cleaned data.

        Returns:
            list: List of (origin, destination) tuples
        """
        if self.cleaned_data is None:
            self.logger.error("No cleaned data available. Call clean_data() first.")
            return []

        # Use the mapping from clean_data if available
        if hasattr(self, '_column_mapping'):
            origin_col = self._column_mapping.get('origin')
            dest_col = self._column_mapping.get('destination')
        else:
            origin_col = self._find_column_containing('origin', self.cleaned_data.columns)
            dest_col = self._find_column_containing('destination', self.cleaned_data.columns)

        if not origin_col or not dest_col:
            self.logger.error("Could not identify origin or destination columns.")
            return []

        if origin_col not in self.cleaned_data.columns or dest_col not in self.cleaned_data.columns:
            self.logger.error(f"Columns {origin_col} or {dest_col} not found in DataFrame.")
            self.logger.info(f"Available columns: {', '.join(self.cleaned_data.columns[:10])}... (and more)")
            return []

        pairs = self.cleaned_data[[origin_col, dest_col]].drop_duplicates()
        return list(zip(pairs[origin_col], pairs[dest_col]))

    def get_median_transport_times(self):
        """
        Calculate median transport times for each origin-destination pair.

        Returns:
            dict: Dictionary mapping (origin, destination) tuples to median transport times in seconds
        """
        if self.cleaned_data is None:
            self.logger.error("No cleaned data available. Call clean_data() first.")
            return {}

        origin_col = self._find_column_containing('origin', self.cleaned_data.columns)
        dest_col = self._find_column_containing('destination', self.cleaned_data.columns)

        if not origin_col or not dest_col:
            self.logger.error("Could not identify origin or destination columns.")
            return {}

        # Check if transport_time column exists
        if 'transport_time' not in self.cleaned_data.columns:
            self.logger.warning("Transport_time column not found. Generating placeholder transport times.")
            # Create a placeholder with fixed times
            result = {}
            for origin, dest in self.get_origin_destination_pairs():
                result[(origin, dest)] = 300  # 5 minutes in seconds
            return result

        # Group by origin-destination and calculate median
        try:
            grouped = self.cleaned_data.groupby([origin_col, dest_col])['transport_time'].median()
            return grouped.to_dict()
        except Exception as e:
            self.logger.error(f"Error calculating median transport times: {str(e)}")
            # Fallback to placeholder values
            result = {}
            for origin, dest in self.get_origin_destination_pairs():
                result[(origin, dest)] = 300  # 5 minutes in seconds
            return result

    def get_fastest_times(self, percentile=10):
        """
        Get the fastest times for each origin-destination pair (based on a percentile).
        This helps identify the most realistic travel times by focusing on the fastest transports.

        Args:
            percentile (int): Percentile to use (e.g., 10 for the 10% fastest transports)

        Returns:
            dict: Dictionary mapping (origin, destination) tuples to fast transport times
        """
        if self.cleaned_data is None:
            self.logger.error("No cleaned data available. Call clean_data() first.")
            return {}

        origin_col = self._find_column_containing('origin', self.cleaned_data.columns)
        dest_col = self._find_column_containing('destination', self.cleaned_data.columns)

        if not origin_col or not dest_col:
            self.logger.error("Could not identify origin or destination columns.")
            return {}

        # Group by origin-destination and calculate the specified percentile
        # Using np.percentile instead of pandas quantile for more flexibility
        result = {}
        for (origin, dest), group in self.cleaned_data.groupby([origin_col, dest_col]):
            transport_times = group['transport_time'].values
            if len(transport_times) > 3:  # Only consider pairs with sufficient data
                fast_time = np.percentile(transport_times, percentile)
                result[(origin, dest)] = fast_time

        return result

    def get_hourly_request_distribution(self):
        """
        Get the distribution of requests by hour of the day.

        Returns:
            dict: Dictionary mapping hour (0-23) to number of requests
        """
        if self.cleaned_data is None:
            self.logger.error("No cleaned data available. Call clean_data() first.")
            return {}

        start_time_col = self._find_column_containing('start', self.cleaned_data.columns)
        if not start_time_col:
            self.logger.error("Could not identify start time column.")
            return {}

        try:
            # Check if the column is already in datetime format
            if pd.api.types.is_datetime64_any_dtype(self.cleaned_data[start_time_col]):
                # Extract hour from start time
                hours = self.cleaned_data[start_time_col].dt.hour
                distribution = hours.value_counts().sort_index().to_dict()
                return distribution
            else:
                # Try to convert to datetime first
                try:
                    datetime_col = pd.to_datetime(self.cleaned_data[start_time_col], format='%d-%m-%Y %H:%M:%S')
                    hours = datetime_col.dt.hour
                    distribution = hours.value_counts().sort_index().to_dict()
                    return distribution
                except Exception as e:
                    # If that fails, extract hour manually from string
                    self.logger.warning(f"Could not convert to datetime for hourly distribution: {str(e)}")

                    # Try to extract hour from string format "DD-MM-YYYY HH:MM:SS"
                    try:
                        # Use string extraction
                        hour_strings = self.cleaned_data[start_time_col].str.extract(r'\d+-\d+-\d+ (\d+):\d+:\d+')[0]
                        hours = pd.to_numeric(hour_strings, errors='coerce')
                        distribution = hours.value_counts().sort_index().to_dict()
                        return distribution
                    except Exception as e2:
                        self.logger.error(f"Manual hour extraction failed: {str(e2)}")

                        # Return a default distribution if all else fails
                        return {h: 100 for h in range(24)}
        except Exception as e:
            self.logger.error(f"Error calculating hourly distribution: {str(e)}")
            return {h: 100 for h in range(24)}  # Default fallback

    def get_all_departments(self):
        """
        Get all unique departments (nodes) in the data.

        Returns:
            list: List of department names
        """
        if self.cleaned_data is None:
            self.logger.error("No cleaned data available. Call clean_data() first.")
            return []

        origin_col = self._find_column_containing('origin', self.cleaned_data.columns)
        dest_col = self._find_column_containing('destination', self.cleaned_data.columns)

        if not origin_col or not dest_col:
            self.logger.error("Could not identify origin or destination columns.")
            return []

        origins = set(self.cleaned_data[origin_col].unique())
        destinations = set(self.cleaned_data[dest_col].unique())

        return list(origins.union(destinations))

    def get_frequency_matrix(self):
        """
        Create a frequency matrix showing how often each origin-destination pair occurs.

        Returns:
            pd.DataFrame: Matrix of transport frequencies
        """
        if self.cleaned_data is None:
            self.logger.error("No cleaned data available. Call clean_data() first.")
            return None

        origin_col = self._find_column_containing('origin', self.cleaned_data.columns)
        dest_col = self._find_column_containing('destination', self.cleaned_data.columns)

        if not origin_col or not dest_col:
            self.logger.error("Could not identify origin or destination columns.")
            return None

        # Count occurrences of each origin-destination pair
        frequency = self.cleaned_data.groupby([origin_col, dest_col]).size().reset_index()
        frequency.columns = [origin_col, dest_col, 'frequency']

        # Convert to a pivot table for better visualization
        pivot = frequency.pivot(index=origin_col, columns=dest_col, values='frequency')

        # Fill NaN with 0
        pivot = pivot.fillna(0)

        return pivot