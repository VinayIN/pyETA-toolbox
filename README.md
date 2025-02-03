# IMPORTANT
In case, this toolbox doesn't works as intended or you find some issues, create an issue in the tracker (https://github.com/VinayIN/EyeTrackerAnalyzer/issues) and I will try to resolve it. (Please attach errors & log)

# EyeTrackerAnalyzer
- This provides a real-time eyetracking metric (especially fixation & Saccades).
- This tool also provides for validation of the eye-tracker performance on a user.
- The tool provides `22 channels`, following table describes the EEG channel information in order:

| No. | Channel Name                | Type           | Unit       |
|-----|-----------------------------|----------------|------------|
|     | **Left Eye**                |                |            |
| 1   | `left_gaze_x`               | gaze           | normalized |
| 2   | `left_gaze_y`               | gaze           | normalized |
| 3   | `left_pupil_diameter`       | pupil          | mm         |
| 4   | `left_fixated`              | fixation       | boolean    |
| 5   | `left_velocity`             | velocity       | px         |
| 6   | `left_fixation_timestamp`   | timestamp      | s          |
| 7   | `left_fixation_elapsed`     | duration       | s          |
| 8   | `left_filtered_gaze_x`      | filtered_gaze  | normalized |
| 9   | `left_filtered_gaze_y`      | filtered_gaze  | normalized |
|     | **Right Eye**               |                |            |
| 10  | `right_gaze_x`              | gaze           | normalized |
| 11  | `right_gaze_y`              | gaze           | normalized |
| 12  | `right_pupil_diameter`      | pupil          | mm         |
| 13  | `right_fixated`             | fixation       | boolean    |
| 14  | `right_velocity`            | velocity       | px         |
| 15  | `right_fixation_timestamp`  | timestamp      | s          |
| 16  | `right_fixation_elapsed`    | duration       | s          |
| 17  | `right_filtered_gaze_x`     | filtered_gaze  | normalized |
| 18  | `right_filtered_gaze_y`     | filtered_gaze  | normalized |
|     | **Screen Data**             |                |            |
| 19  | `screen_width`              | screen         | px         |
| 20  | `screen_height`             | screen         | px         |
| 21  | `timestamp`                 | timestamp      | s          |
| 22  | `local_clock`               | timestamp      | s          |

## Installation
Download the `pyeta-<version>-py3-none-any.whl` file from here: https://github.com/VinayIN/EyeTrackerAnalyzer/releases and install using `pip`
```bash
# move the .whl file to your workspace
# once moved verify using ls bash command, if found
# replace .whl file with the one just downloaded. it should have this format with a different <version> 
pip install pyeta-<version>-py3-none-any.whl
```
or

`CAUTION: This below method installs the developement version and might have bugs`
```bash
pip install git+https://github.com/VinayIN/EyeTrackerAnalyzer.git
```

## Usage
There are 2 ways this tool can be used (CLI - `track/window/validate` & GUI - `browser/application`), both are showed below:

*prerequisite: `pyETA needs to be installed`*

### 1. CLI
#### Command:
```bash
pyETA track
```
#### Parameters:
- `--push_stream:` Pushes the data to an LSL stream.
- `--data_rate:` Specifies the rate of the data stream.
- `--use_mock:` Uses a mock service for the eye tracker.
- `--fixation:` Adds fixation duration to the data stream.
- `--velocity:` Specifies the velocity threshold for fixation.
- `--accept_screen_nans:` Avoids correcting for NaNs.
- `--save_data:` Saves the data to a file.
- `--verbose:` Displays debug statements.
- `--duration:` Specifies the duration for which to track the data.
- `--screen_index:` for multi-screen execution, use the index to capture the data from a specific screen with the resolution

An example with tracker running with fixation and a mock service that runs for a duration of 10sec and stops (if --use_mock is not provided, it searches for the eye tracker)
```bash
pyETA track --fixation --use_mock --duration 10
```
------
##### Command:
```bash
pyETA window
```
#### Parameters:
- `--use_mock:` Use mockup tracker
- `--screen_index:` Screen index to display the validation window
- `--verbose:` Enable verbose logging

Example with parameters to run the validation window
```bash
    pyETA window --use_mock --screen_index=0 
```
_____
##### Command:
```bash
pyETA validate
```
#### Parameters:
- `--csv:` Name of the output CSV file. (example: myfile.csv)

Example with parameters to fetch the metrics
```bash
    pyETA validate --csv=myfile.csv
```
_____

#### 2. GUI
##### Command:
```bash
pyETA browser
```
##### Parameters:
- `--debug:` Enables debug mode.
- `--port:` Specifies the port number for the Dash application.

Example with debug mode and starting at port 8050 (Access it here: http://localhost:8050)
```bash
    pyETA browser --debug --port 8050
```
-------
##### Command:
```bash
pyETA application
```
