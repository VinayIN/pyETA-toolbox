import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import json
from datetime import timedelta
import pyETA.components.utils as eta_utils

def calculate_statistics(df: pd.DataFrame, screen_width: int, screen_height: int) -> pd.DataFrame:
    target = df.screen_position.iloc[0]
    e_target = eta_utils.get_euler_form(target)
    
    target_magnitude = (df.magnitude_left_from_target + df.magnitude_right_from_target) / 2
    target_phase = (df.phase_left_from_target + df.phase_right_from_target) / 2
    spread_magnitude = (df.magnitude_left_from_median + df.magnitude_right_from_median) / 2
    spread_phase = (df.phase_left_from_median + df.phase_right_from_median) / 2

    result = {
        "group": df.group.iloc[0],
        "target_position": target,
        "median_magnitude": np.median(target_magnitude),
        "median_phase": np.median(target_phase)
    }
    
    median_position = eta_utils.get_cartesian(
        euler=(result["median_magnitude"], result["median_phase"]),
        reference=e_target
    )
    median_position = list(map(lambda x: float(x.round(3)), median_position))
    result.update({
        "median_position": median_position,
        "std_spread": np.std(spread_magnitude)
    })
    
    return pd.DataFrame(data = [result])

def load_data(screen_file: str, gaze_file: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    with open(screen_file, 'r') as f:
        screen_data = json.load(f)
    with open(gaze_file, 'r') as f:
        tracker_data = json.load(f)
    
    df_screen_data = pd.DataFrame(data=screen_data["data"]).dropna()
    df_screen_data.index.name = 'group'
    df_screen_data = df_screen_data.reset_index()
    
    df_tracker_data = pd.DataFrame(data=tracker_data["data"]).dropna()
    
    return df_screen_data, df_tracker_data

def preprocess_data(df_screen_data: pd.DataFrame, df_tracker_data: pd.DataFrame, screen_width: int, screen_height: int) -> pd.DataFrame:
    df_screen_data['timestamp_0'] = pd.to_datetime(df_screen_data['timestamp'], unit='s')
    df_screen_data['timestamp_2'] = df_screen_data['timestamp_0'] + timedelta(seconds=2)
    df_tracker_data['timestamp_0'] = pd.to_datetime(df_tracker_data['timestamp'], unit='s')
    
    df_screen_data["target_relative"] = df_screen_data.screen_position.apply(
        lambda x: eta_utils.get_relative_from_actual(x, screen_width, screen_height)
    )
    
    return df_screen_data, df_tracker_data

def filter_and_group_data(df_screen_data: pd.DataFrame, df_tracker_data: pd.DataFrame) -> pd.DataFrame:
    groups = []
    
    for _, row in df_screen_data.iterrows():
        filtered_tracker_data = df_tracker_data[
            (df_tracker_data['timestamp_0'] >= row['timestamp_0']) & 
            (df_tracker_data['timestamp_0'] <= row['timestamp_2'])
        ].copy()
        
        if not filtered_tracker_data.empty:
            filtered_tracker_data["group"] = row["group"]
            groups.append(filtered_tracker_data)
    
    return pd.concat(groups, ignore_index=True)

def calculate_euler(df: pd.DataFrame) -> pd.DataFrame:
    target = df.target_relative.iloc[0]
    e_target = eta_utils.get_euler_form(target)
    
    def apply_euler(eye_data):
        euler = eta_utils.get_euler_form(eye_data["gaze_point"], reference=target)
        return pd.Series({'magnitude': euler[0], 'phase': euler[1]})
    
    left_euler = df.left_eye.apply(apply_euler)
    right_euler = df.right_eye.apply(apply_euler)
    
    df["magnitude_left_from_target"] = left_euler['magnitude']
    df["magnitude_right_from_target"] = right_euler['magnitude']
    df["phase_left_from_target"] = left_euler['phase']
    df["phase_right_from_target"] = right_euler['phase']
    
    magnitude = (df.magnitude_left_from_target + df.magnitude_right_from_target) / 2
    phases = (df.phase_left_from_target + df.phase_right_from_target) / 2
    median_magnitude = np.median(magnitude)
    median_phase = np.median(phases)
    
    median_position = eta_utils.get_cartesian(euler=(median_magnitude, median_phase), reference=e_target)
    
    def apply_euler_median(eye_data):
        euler = eta_utils.get_euler_form(eye_data["gaze_point"], reference=median_position)
        return pd.Series({'magnitude': euler[0], 'phase': euler[1]})
    
    left_euler_median = df.left_eye.apply(apply_euler_median)
    right_euler_median = df.right_eye.apply(apply_euler_median)
    
    df["magnitude_left_from_median"] = left_euler_median['magnitude']
    df["magnitude_right_from_median"] = right_euler_median['magnitude']
    df["phase_left_from_median"] = left_euler_median['phase']
    df["phase_right_from_median"] = right_euler_median['phase']
    
    return df

def get_statistics(gaze_file: str, screen_file: str) -> pd.DataFrame:
    screen_width = 1512
    screen_height = 982
    df_screen_data, df_tracker_data = load_data(screen_file, gaze_file)
    if df_screen_data.empty or df_tracker_data.empty:
        return pd.DataFrame()
    df_screen_data, df_tracker_data = preprocess_data(df_screen_data, df_tracker_data, screen_width, screen_height)
    df_groups = filter_and_group_data(df_screen_data, df_tracker_data)
    
    df_groups = df_groups.join(df_screen_data[["screen_position", "target_relative"]], on=["group"], how="left").dropna()
    
    df_calculated = df_groups.groupby("group").apply(calculate_euler)
    
    statistics = df_calculated.reset_index(drop=True).groupby("group").apply(
        lambda row: calculate_statistics(row, screen_width, screen_height)
    ).reset_index(drop=True)
    
    return statistics.round(3).astype(str)

if __name__ == "__main__":
    gaze_file = "/Users/binay/Desktop/code/EyeTrackerAnalyzer/data/gaze_data_20240919_210344.json"
    screen_file = "/Users/binay/Desktop/code/EyeTrackerAnalyzer/data/system_Binay-MacBook-Pro.local_Darwin_arm64_1512x982.json"
    
    result = get_statistics(gaze_file, screen_file)
    print(result)