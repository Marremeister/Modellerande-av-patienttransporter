import pandas as pd

import time
from plotters import Plot


class HourlyWorkloadAnalysis:
    def __init__(self, df, plotter):
        self.df = df
        self.plotter = plotter
        # These will be computed once:
        self.hourly_data = None  # Dictionary: key = hour, value = expanded DataFrame for that hour.
        self.overall_transporter_workload = None  # Series: index = transporter ID, value = overall average workload per instance.

    def _expand_hours(self, df):
        """
        Expand each task (row) into hourly intervals and calculate the exact number
        of effective transport minutes that fall into each hourly slot.
        For example, if a task starts at 9:50 and ends at 10:10 (20 minutes total),
        10 minutes will be allocated to the 9:00-10:00 slot and 10 minutes to the 10:00-11:00 slot.
        """
        df = df.copy()
        start_time = time.perf_counter()

        print("Step 1: Computing start_hour and adjusted_end columns...")
        df['start_hour'] = df['Real Start Time'].dt.floor('h')
        df['adjusted_end'] = df['Uppdrag Sluttid']
        mask = (df['Uppdrag Sluttid'].dt.minute == 0) & \
               (df['Uppdrag Sluttid'].dt.second == 0) & \
               (df['Uppdrag Sluttid'].dt.microsecond == 0)
        df.loc[mask, 'adjusted_end'] = df.loc[mask, 'Uppdrag Sluttid'] - pd.Timedelta(microseconds=1)
        df['end_hour'] = df['adjusted_end'].dt.floor('h')
        step1_time = time.perf_counter()
        print(f"Step 1 completed in {step1_time - start_time:.2f} seconds.")

        print("Step 2: Generating hour_range using apply (no parallel processing)...")
        df['hour_range'] = df.apply(
            lambda row: pd.date_range(row['start_hour'], row['end_hour'], freq='h'),
            axis=1
        )
        step2_time = time.perf_counter()
        print(f"Step 2 completed in {step2_time - step1_time:.2f} seconds.")

        print("Step 3: Exploding hour_range...")
        df_expanded = df.explode('hour_range')
        step3_time = time.perf_counter()
        print(f"Step 3 completed in {step3_time - step2_time:.2f} seconds.")

        print("Step 4: Setting Active_Hour and Active_Date...")
        df_expanded['Active_Hour'] = df_expanded['hour_range'].dt.hour
        df_expanded['Active_Date'] = df_expanded['hour_range'].dt.date
        step4_time = time.perf_counter()
        print(f"Step 4 completed in {step4_time - step3_time:.2f} seconds.")

        print("Step 5: Calculating next_hour column...")
        df_expanded['next_hour'] = df_expanded['hour_range'] + pd.Timedelta(hours=1)
        step5_time = time.perf_counter()
        print(f"Step 5 completed in {step5_time - step4_time:.2f} seconds.")

        print("Step 6: Computing interval_start and interval_end...")
        df_expanded['interval_start'] = df_expanded[['Real Start Time', 'hour_range']].max(axis=1)
        df_expanded['interval_end'] = df_expanded[['adjusted_end', 'next_hour']].min(axis=1)
        step6_time = time.perf_counter()
        print(f"Step 6 completed in {step6_time - step5_time:.2f} seconds.")

        print("Step 7: Calculating Effective_Time_Per_Hour...")
        df_expanded['Effective_Time_Per_Hour'] = (
                (df_expanded['interval_end'] - df_expanded['interval_start']).dt.total_seconds() / 60
        )
        step7_time = time.perf_counter()
        print(f"Step 7 completed in {step7_time - step6_time:.2f} seconds.")

        total_time = time.perf_counter() - start_time
        print(f"Total expansion completed in {total_time:.2f} seconds.")

        return df_expanded

    def calculate_workload_data(self):
        """
        Calculate workload data once for the selected hours.
        Returns:
          - hourly_data: dict with key = hour, value = expanded DataFrame for that hour.
          - overall_transporter_workload: Series with index = transporter ID and value = overall average workload per instance.
        """
        required_columns = ['Skapad Tid', 'Real Start Time', 'Uppdrag Sluttid']
        for col in required_columns:
            if col not in self.df.columns:
                print(f"Missing column: {col}")
                return None, None

        # Filter for January based on 'Skapad Tid'
        january_df = self.df[self.df['Skapad Tid'].dt.month == 1]
        print(f"January dataframe has {len(january_df)} rows (out of {len(self.df)} total).")
        # Define the selected hours (e.g., 2, 8, 12, 14, 16, 20)
        selected_hours = [2, 8, 12, 14, 16, 20]

        hourly_data = {}
        expanded_list = []
        for hour in selected_hours:
            trial_df = january_df[(january_df['Real Start Time'].dt.hour == hour) |
                                  (january_df['Uppdrag Sluttid'].dt.hour == hour)]
            print(f"Dataframe for hour {hour} has {len(trial_df)} rows.")
            if trial_df.empty:
                continue
            expanded_df = self._expand_hours(trial_df)
            # Retain only rows corresponding to the active hour being analyzed
            hour_df = expanded_df[expanded_df['Active_Hour'] == hour]
            if hour_df.empty:
                print(f"No expanded data for hour {hour}")
                continue
            hourly_data[hour] = hour_df
            expanded_list.append(hour_df)

        if expanded_list:
            combined_df = pd.concat(expanded_list)
            grouped = combined_df.groupby('Sekundär Servicepersonal Id')
            total_workload = grouped['Effective_Time_Per_Hour'].sum()
            count_instances = grouped.size()
            overall_avg_workload = total_workload / count_instances
        else:
            overall_avg_workload = None

        self.hourly_data = hourly_data
        self.overall_transporter_workload = overall_avg_workload

        return hourly_data, overall_avg_workload

    def plot_hourly_workload(self, plotter=None):
        """
        Plot a histogram for each selected hour using the pre-calculated hourly_data.
        Each histogram shows the distribution of average workload per instance (in minutes) for that hour.
        """
        if plotter is None:
            plotter = self.plotter
        if self.hourly_data is None or self.overall_transporter_workload is None:
            self.calculate_workload_data()

        for hour, df_hour in self.hourly_data.items():
            grouped = df_hour.groupby('Sekundär Servicepersonal Id')
            total_workload = grouped['Effective_Time_Per_Hour'].sum()
            instance_count = grouped.size()
            average_workload = total_workload / instance_count
            median_workload = average_workload.median()

            title = f"Workload at {hour}:00\nMedian: {median_workload:.1f} min per instance"
            plot = Plot(
                xlabel='Average Workload (min per instance)',
                ylabel='Number of Transporters',
                title=title,
                plot_type='hist',
                x=average_workload,
                bins=20,
                median=median_workload
            )
            plotter.add_plot(plot)

    def plot_transporter_workload_by_hour(self, plotter=None):
        """
        For each selected hour, plot a bar chart with transporters on the x-axis and
        their average workload (min per instance) for that hour on the y-axis.
        This creates 6 separate graphs (one per selected hour) using the pre-calculated hourly_data.
        """
        if plotter is None:
            plotter = self.plotter
        if self.hourly_data is None:
            self.calculate_workload_data()

        for hour, df_hour in self.hourly_data.items():
            grouped = df_hour.groupby('Sekundär Servicepersonal Id')
            total_workload = grouped['Effective_Time_Per_Hour'].sum()
            instance_count = grouped.size()
            average_workload = total_workload / instance_count
            title = f"Transporter Workload at {hour}:00 (January)"
            plot = Plot(
                xlabel='Transporter ID',
                ylabel='Average Workload (min per instance)',
                title=title,
                plot_type='bar',
                x=average_workload.index,
                y=average_workload.values
            )
            plotter.add_plot(plot)