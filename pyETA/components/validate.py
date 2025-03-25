import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import json
import os
import sys
import click
import re
import datetime
import pyETA.components.utils as eta_utils
from pyETA import LOGGER, __datapath__
from dataclasses import dataclass

@dataclass
class ValidateData:
    screen: Tuple[int, int]
    window: Tuple[int, int]


def convert_window_to_screen_coordinates(point: Tuple[float, float], dtype="int") -> Tuple[float, float]:
    x = (point[0] / ValidateData.window[0]) * ValidateData.screen[0]
    y = (point[1] / ValidateData.window[1]) * ValidateData.screen[1]
    return (x, y) if dtype == "float" else (int(x), int(y))

def convert_screen_to_window_coordinates(point: Tuple[float, float], dtype="int") -> Tuple[float, float]:
    x = (point[0] / ValidateData.screen[0]) * ValidateData.window[0]
    y = (point[1] / ValidateData.screen[1]) * ValidateData.window[1]
    return (x, y) if dtype == "float" else (int(x), int(y))

def calculate_statistics(df: pd.DataFrame) -> pd.DataFrame:
    target = df.screen_position_recalibrated.iloc[0]
    mean_data_x= int((df["left_eye_x"].mean() + df["right_eye_x"].mean())/2)
    mean_data_y= int((df["left_eye_y"].mean() + df["right_eye_y"].mean())/2)
    result = {
        "group": df.group.iloc[0],
        "target position": target,
        "distance (target to gaze points)": (df["distance_left_from_target"].mean() + df["distance_right_from_target"].mean())/2,
        "spread (target to gaze points)": (df["distance_left_from_target"].std() + df["distance_right_from_target"].std())/2,
        "mean gaze point": (mean_data_x, mean_data_y),
        "distance (mean to target)": eta_utils.get_distance((mean_data_x, mean_data_y), target),
        "distance (mean to gaze points)": (df["distance_left_from_mean"].mean() + df["distance_right_from_mean"].mean())/2,
        "spread (mean to gaze points)": (df["distance_left_from_mean"].std() + df["distance_right_from_mean"].std())/2,
    }
    return pd.DataFrame(data = [result])

def load_data(validate_file: str, gaze_file: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    with open(validate_file, 'r') as f:
        validate_data = json.load(f)
    with open(gaze_file, 'r') as f:
        gaze_data = json.load(f)
    
    ValidateData.screen = gaze_data["screen_size"]
    ValidateData.window = validate_data["screen_size"]
    df_gaze_data = pd.DataFrame(data=gaze_data["data"]).fillna(0.0)
    
    df_validate_data = pd.DataFrame(data=validate_data["data"]).fillna(0.0)
    df_validate_data.index.name = 'group'
    df_validate_data = df_validate_data.reset_index()
    data = {"gaze": df_gaze_data, "validate": df_validate_data}
    LOGGER.info(f"Screen resolution: {ValidateData.screen}")
    LOGGER.info(f"Window resolution: {ValidateData.window}")
    return data

def preprocess_data(df_gaze_data: pd.DataFrame, df_validate_data: pd.DataFrame) -> pd.DataFrame:
    df_gaze_data['timestamp_0'] = pd.to_datetime(df_gaze_data['timestamp'], unit='s')
    
    df_validate_data['timestamp_0'] = pd.to_datetime(df_validate_data['timestamp'], unit='s')
    df_validate_data['timestamp_3'] = df_validate_data['timestamp_0'] + datetime.timedelta(seconds=3)

    df_validate_data["screen_position_recalibrated"] = df_validate_data.screen_position.apply(
        lambda x: convert_window_to_screen_coordinates(x))
    
    return df_gaze_data, df_validate_data

def filter_and_group_data(df_gaze_data: pd.DataFrame, df_validate_data: pd.DataFrame) -> pd.DataFrame:
    groups = []
    
    for _, row in df_validate_data.iterrows():
        filtered_gaze_data = df_gaze_data[
            (df_gaze_data['timestamp_0'] >= row['timestamp_0']) & 
            (df_gaze_data['timestamp_0'] <= row['timestamp_3'])
        ].copy()
        
        if not filtered_gaze_data.empty:
            filtered_gaze_data["group"] = row["group"]
            groups.append(filtered_gaze_data)
    
    return pd.concat(groups, ignore_index=True)

def calculate_data(df: pd.DataFrame) -> pd.DataFrame:
    target = df.screen_position_recalibrated.iloc[0]
    
    def extract_distance_target(eye_data):
        if np.isnan(eye_data["gaze_point"][0]):
            return pd.Series({'distance': np.nan, 'x': np.nan, 'y': np.nan})
        point = eta_utils.get_actual_from_relative(eye_data["gaze_point"], ValidateData.screen[0], ValidateData.screen[1])
        distance_pixel = eta_utils.get_distance(point, target)
        return pd.Series({'distance': distance_pixel, 'x': point[0], 'y': point[1]})
    
    left_eye_data = df.left_eye.apply(extract_distance_target)
    right_eye_data = df.right_eye.apply(extract_distance_target)

    df["left_eye_x"] = left_eye_data['x']
    df["left_eye_y"] = left_eye_data['y']
    df["right_eye_x"] = right_eye_data['x']
    df["right_eye_y"] = right_eye_data['y']
    mean_xy = (left_eye_data['x'].mean() + right_eye_data['x'].mean()) / 2, (left_eye_data['y'].mean() + right_eye_data['y'].mean()) / 2
    df["distance_left_from_target"] = left_eye_data['distance']
    df["distance_right_from_target"] = right_eye_data['distance']

    def extract_distance_mean(eye_data, mean_xy):
        if np.isnan(eye_data["gaze_point"][0]):
            return pd.Series({'distance': np.nan, 'x': np.nan, 'y': np.nan})
        point = eta_utils.get_actual_from_relative(eye_data["gaze_point"], ValidateData.screen[0], ValidateData.screen[1])
        distance = eta_utils.get_distance(point, mean_xy)
        return pd.Series({'distance': distance, 'x': point[0], 'y': point[1]})
    
    left_eye_data = df.left_eye.apply(lambda x: extract_distance_mean(x, mean_xy))
    right_eye_data = df.right_eye.apply(lambda x: extract_distance_mean(x, mean_xy))

    df["distance_left_from_mean"] = left_eye_data['distance']
    df["distance_right_from_mean"] = right_eye_data['distance']
    return df

def get_statistics(gaze_file: str, validate_file: str) -> pd.DataFrame:
    data = load_data(validate_file, gaze_file)
    df_gaze_data, df_validate_data = data.get("gaze"), data.get("validate")
    if df_gaze_data.empty or df_validate_data.empty:
        return pd.DataFrame()
    
    df_gaze_data, df_validate_data = preprocess_data(df_gaze_data, df_validate_data)
    df_groups = filter_and_group_data(df_gaze_data, df_validate_data)
    
    df_groups = df_groups.join(df_validate_data[["screen_position", "screen_position_recalibrated"]], on=["group"], how="left").dropna()
    
    df_calculated = df_groups.groupby("group").apply(calculate_data)
    
    statistics = df_calculated.reset_index(drop=True).groupby("group").apply(calculate_statistics).reset_index(drop=True)
    
    result = statistics.round(4)
    described = result.describe(percentiles=[0.25, 0.50, 0.75]).loc[['25%', '50%', '75%', 'mean']].drop(columns=['group'])
    described.index.name= 'group'
    described = described.reset_index().round(4)
    
    separator_row = pd.DataFrame([["---"] * result.shape[1]], columns=result.columns)
    combined = pd.concat([result, separator_row, described], ignore_index=True).fillna("")
    return combined, result, described

def get_gaze_data_timestamp(file: str) -> Optional[datetime.datetime]:
    try:
        timestamp_data = re.search(r"gaze_data_(.*).json", file).group(1)
        return datetime.datetime.strptime(timestamp_data, "%Y%m%d_%H%M%S")
    except AttributeError:
        LOGGER.error(f"Invalid file name: {file}")
        return None

def get_validate_data_timestamp(file: str) -> Optional[datetime.datetime]:
    try:
        info = re.search(r"system_(.*).json", file).group(1)
        info = info.split("_")
        return datetime.datetime.strptime("_".join(info[-2:]), "%Y%m%d_%H%M%S")
    except AttributeError:
        LOGGER.error(f"Invalid file name: {file}")
        return None

@click.command("validate")
@click.option('--csv', help="Name of the output CSV file.")
def main(csv: Optional[str]):
    # List files in __datapath__
    gaze_files = sorted(eta_utils.get_file_names(prefix="gaze_data_"))
    validate_files = sorted(eta_utils.get_file_names(prefix="system_"))

    # Display gaze files
    print("Available Gaze Data:")
    for i, file in enumerate(gaze_files):
        print(f'{i + 1}. {file} (Timestamp: {get_gaze_data_timestamp(file)})')
    try:
        gaze_choice = int(input("Enter a number: ")) - 1
        gaze_file = os.path.join(__datapath__, gaze_files[gaze_choice])
    except (ValueError, IndexError):
        LOGGER.error("Invalid input. Exiting...")
        sys.exit(1)

    # Display validate files
    print("\nAvailable Validate Data:")
    for i, file in enumerate(validate_files):
        print(f'{i + 1}. {file} (Timestamp: {get_validate_data_timestamp(file)})')
    try:
        validate_choice = int(input("Enter a number: ")) - 1
        validate_file = os.path.join(__datapath__, validate_files[validate_choice])
    except (ValueError, IndexError):
        LOGGER.error("Invalid input. Exiting...")
        sys.exit(1)

    # Process and save to CSV
    combined, result, described = get_statistics(gaze_file=gaze_file, validate_file=validate_file)
    if csv is None:
        print(described)
    combined.to_csv(csv, index=False)
    print(f"Results saved to {csv}")

if __name__ == "__main__":
    main()