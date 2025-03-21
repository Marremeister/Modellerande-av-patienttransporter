import pandas as pd
import matplotlib.pyplot as plt


class DataLoader:
    def __init__(self, file_path):
        self.file_path = file_path
        self.df = None

    def load_and_process_data(self, route_percentage=10):
        """
        Loads the CSV file and processes the data as follows:
          - Converts 'Skapad Tid' and 'Uppdrag Sluttid' to datetime.
          - Drops rows with missing dates.
          - Extracts the hour from 'Uppdrag Sluttid' into a new column 'Hour'.
          - If 'Startplats' and 'Slutplats' exist, groups the data by these columns.
            For each route, it calculates the median of the fastest route_percentage of
            the Uppdrag Sluttid values (this is used as the "Real Transport Duration").
          - Merges this computed duration back into the DataFrame.
          - Computes 'Real Transport Duration (minutes)' as the difference (in minutes)
            between 'Uppdrag Sluttid' and the computed route benchmark.
          - Calculates 'Real Start Time' as Uppdrag Sluttid minus the computed transport duration.
          - Calculates 'Real Waiting Time (minutes)' as the difference between Real Start Time and Skapad Tid.
          - Filters out rows where the waiting time is over 300 minutes.

        Parameters:
          route_percentage (float): Percentage of the fastest tasks to consider per route (default 10).
        """
        try:
            self.df = pd.read_csv(
                self.file_path,
                sep=";",
                on_bad_lines='skip',
                encoding="utf-8",
                low_memory=False
            )
            print("Columns found in the dataset:", self.df.columns)

            if 'Skapad Tid' in self.df.columns and 'Uppdrag Sluttid' in self.df.columns:
                self.df['Skapad Tid'] = pd.to_datetime(self.df['Skapad Tid'], errors='coerce', dayfirst=True)
                self.df['Uppdrag Sluttid'] = pd.to_datetime(self.df['Uppdrag Sluttid'], errors='coerce', dayfirst=True)
                self.df = self.df.dropna(subset=['Skapad Tid', 'Uppdrag Sluttid'])
                self.df['Hour'] = self.df['Uppdrag Sluttid'].dt.hour

                if 'Startplats' in self.df.columns and 'Slutplats' in self.df.columns:
                    # Group by route and compute the median of the fastest route_percentage of tasks.
                    route_times = self.df.groupby(['Startplats', 'Slutplats'])['Uppdrag Sluttid'].apply(
                        lambda x: x.nsmallest(max(1, int(len(x) * (route_percentage / 100)))).median()
                    )
                    self.df = self.df.merge(
                        route_times.rename('Real Transport Duration'),
                        on=['Startplats', 'Slutplats'],
                        how='left'
                    )

                    # Compute the effective transport duration in minutes.
                    self.df['Real Transport Duration (minutes)'] = (
                                                                           self.df['Uppdrag Sluttid'] - self.df[
                                                                       'Real Transport Duration']
                                                                   ).dt.total_seconds() / 60
                    # Ensure positive durations
                    self.df['Real Transport Duration (minutes)'] = self.df['Real Transport Duration (minutes)'].abs()

                    # Compute Real Start Time by subtracting the effective transport duration from Uppdrag Sluttid.
                    self.df['Real Start Time'] = self.df['Uppdrag Sluttid'] - pd.to_timedelta(
                        self.df['Real Transport Duration (minutes)'], unit='m'
                    )
                    # Compute Real Waiting Time as the difference between Real Start Time and Skapad Tid.
                    self.df['Real Waiting Time (minutes)'] = (
                                                                     self.df['Real Start Time'] - self.df['Skapad Tid']
                                                             ).dt.total_seconds() / 60

                    # Filter out rows with waiting times over 300 minutes.
                    self.df = self.df[self.df['Real Waiting Time (minutes)'] <= 300]
        except Exception as e:
            print(f"Error loading data: {e}")


class RouteTransportTable:
    def __init__(self, df):
        self.df = df

    def get_table_data(self):
        """
        Groups the DataFrame by 'Startplats' and 'Slutplats' and computes two metrics for each route:
          - 'Real Transport Duration (10% fastest) (min)': Taken from the pre-computed column,
            using the first row’s value for that route.
          - 'Median Transport Duration (min)': Computed as the median of the raw durations for that route,
            where raw duration is (Uppdrag Sluttid - Skapad Tid) in minutes.
        Returns a new DataFrame with these four columns.
        """
        # Group by route (start and stop locations)
        grouped = self.df.groupby(['Startplats', 'Slutplats'])
        table_rows = []
        for (start, stop), group in grouped:
            # Get the pre-computed real transport duration (from the fastest 10% calculation)
            # This column should have been merged into the DataFrame by DataLoader.
            if 'Real Transport Duration (minutes)' in group.columns:
                fastest_duration = group['Real Transport Duration (minutes)'].iloc[0]
            else:
                fastest_duration = None

            # Compute the median of the raw durations for this route:
            # Raw duration is computed as (Uppdrag Sluttid - Skapad Tid) in minutes.
            raw_duration = (group['Uppdrag Sluttid'] - group['Skapad Tid']).dt.total_seconds() / 60
            median_duration = raw_duration.median()

            table_rows.append([start, stop, fastest_duration, median_duration])

        result_df = pd.DataFrame(
            table_rows,
            columns=[
                'Startplats',
                'Slutplats',
                'Real Transport Duration (10% fastest) (min)',
                'Median Transport Duration (min)'
            ]
        )
        return result_df

    def plot_table(self):
        """
        Uses matplotlib's table functionality to display the route transport table.
        """
        data = self.get_table_data()
        fig, ax = plt.subplots(figsize=(12, max(2, len(data) * 0.3)))
        ax.axis('tight')
        ax.axis('off')
        table = ax.table(cellText=data.values, colLabels=data.columns, loc='center')
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.5)
        plt.title("Route Transport Times", fontsize=14)
        plt.show()