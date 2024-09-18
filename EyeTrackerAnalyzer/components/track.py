import argparse
import sys
import datetime
import os
import json
import time

from typing import Optional
from mne_lsl import lsl
import EyeTrackerAnalyzer.components.mock as eta_mock
import EyeTrackerAnalyzer.components.utils as eta_utils
try:
    import tobii_research as tr
except ModuleNotFoundError:
    print("Without tobii_research library, Tobii eye-tracker won't work.")
import numpy as np


class Tracker:
    def __init__(
            self,
            data_rate=600,
            use_mock=False,
            fixation=False,
            screen_nans=True,
            verbose=False,
            push_stream=False,
            save_data=False
        ):
        self.screen_width, self.screen_height = eta_utils.get_current_screen_size()
        self.data_rate = data_rate
        self.screen_nans = screen_nans
        self.verbose = verbose
        self.save_data = save_data
        self.use_mock = use_mock
        self.fixation = fixation
        self.push_stream = push_stream
        self.gaze_data = []
        self.gaze_id = None
        self.lsl_gaze_outlet = None
        
        try:
            if self.use_mock:
                print("Using a mock service.")
                self.gaze_id = eta_mock.EYETRACKER_GAZE_DATA
                
                self.eyetracker = eta_mock.MockEyeTracker(data_rate=self.data_rate, verbose=self.verbose)
                self.eyetracker.start()
            else:
                print("Using tobii to find eyetrackers.")
                self.gaze_id = tr.EYETRACKER_GAZE_DATA
                self.eyetrackers = tr.find_all_eyetrackers()
                self.eyetracker = self.eyetrackers[0] if self.eyetrackers else None
                if self.eyetracker:
                    print(f"Screen Resolution: {self.screen_width}x{self.screen_height}")
                    print(f"Address: {self.eyetracker.address}")
                    print(f"Model: {self.eyetracker.model}")
                    print(f"Name: {self.eyetracker.device_name}")
                    print(f"Serial number: {self.eyetracker.serial_number}")
                else:
                    raise ValueError("No eye tracker device found.")
        except Exception as e:
            raise ValueError(f"Error initializing the eye tracker: {e}")

        if self.push_stream:
            n_channels = 10
            min_cutoff = 0.004
            beta = 0.7
            if self.fixation:
                self.__fixation_elapsed = 0.0
                self.__one_euro_filter_x = eta_utils.OneEuroFilter(
                    initial_time=eta_utils.get_timestamp(),
                    initial_value=0.0,
                    min_cutoff = min_cutoff,
                    beta = beta)
                self.__one_euro_filter_y = eta_utils.OneEuroFilter(
                    initial_time=eta_utils.get_timestamp(),
                    initial_value=0.0,
                    min_cutoff = min_cutoff,
                    beta = beta)

            info = lsl.StreamInfo(
                name='tobii_gaze',
                stype='Gaze',
                n_channels=n_channels,
                sfreq=self.data_rate,
                dtype='float64',
                source_id='uid001_eyetracker')
            self.lsl_gaze_outlet = lsl.StreamOutlet(info)
            print(f"LSL Stream Info: {self.lsl_gaze_outlet.get_sinfo()}")
        print(f"Member Variables: {vars(self)}")
        print("\n\nPress Ctrl+C to stop tracking...")

    def _check_fixation(self, t, x, y, velocity_threshold=0.5):
        previous_t = self.__one_euro_filter_x.previous_time
        filtered_x = self.__one_euro_filter_x(t, x)
        filtered_y = self.__one_euro_filter_y(t, y)
        velocity = np.sqrt((filtered_x - x)**2 + (filtered_y - y)**2)
        elapsed_time = t - previous_t
        is_fixated = False
        if velocity <= velocity_threshold:
            is_fixated = True
        return is_fixated, velocity, elapsed_time

    def _collect_gaze_data(self, gaze_data):
        data = {
            "timestamp": eta_utils.get_timestamp(),
            "device_time_stamp": gaze_data.get("device_time_stamp"),
            "left_eye": {
                "gaze_point": gaze_data.get("left_gaze_point_on_display_area"),
                "pupil_diameter": gaze_data.get("left_pupil_diameter")
            },
            "right_eye": {
                "gaze_point": gaze_data.get("right_gaze_point_on_display_area"),
                "pupil_diameter": gaze_data.get("right_pupil_diameter")
            }
        }
        stream_data = np.array([
                    data["left_eye"]["gaze_point"][0] if data["left_eye"]["gaze_point"] else 0 if self.screen_nans else np.nan,
                    data["left_eye"]["gaze_point"][1] if data["left_eye"]["gaze_point"] else 0 if self.screen_nans else np.nan,
                    data["left_eye"]["pupil_diameter"] if data["left_eye"]["pupil_diameter"] else 0 if self.screen_nans else np.nan,
                    data["right_eye"]["gaze_point"][0] if data["right_eye"]["gaze_point"] else 0 if self.screen_nans else np.nan,
                    data["right_eye"]["gaze_point"][1] if data["right_eye"]["gaze_point"] else 0 if self.screen_nans else np.nan,
                    data["right_eye"]["pupil_diameter"] if data["right_eye"]["pupil_diameter"] else 0 if self.screen_nans else np.nan,
                    self.screen_width,
                    self.screen_height,
                    data["timestamp"],
                    lsl.local_clock()
                ], dtype=np.float64)
        if self.fixation:
            is_fixated, velocity, elapsed_time = self._check_fixation(
                t=data["timestamp"],
                x=data["left_eye"]["gaze_point"][0],
                y=data["left_eye"]["gaze_point"][1])
            self.__fixation_elapsed = (self.__fixation_elapsed + elapsed_time) if is_fixated else 0.0
            fixation_data = {
                "fixated": is_fixated,
                "velocity": velocity,
                "fixation_elapsed": self.__fixation_elapsed
            }
            data.update(fixation_data)
            stream_data = np.append(stream_data, data["fixation_elapsed"])
        if self.push_stream:
            self.lsl_gaze_outlet.push_sample(stream_data)
        if self.save_data: self.gaze_data.append(data)
        def multiply_tuples(t1, t2=(self.screen_width, self.screen_height)):
            return tuple(x*y for x,y in zip(t1, t2))
        if self.verbose: print(f'L: {multiply_tuples(data["left_eye"]["gaze_point"])}, R: {multiply_tuples(data["right_eye"]["gaze_point"])}, ({data.get("fixated")}, {data.get("velocity")}, {data.get("fixation_elapsed")})')

    def start_tracking(self, duration: Optional[float]=None):
        """Starts tracking continuously and saves the data to a file, if save_data flag is set to True during initialization."""
        end_time = datetime.datetime.now() + datetime.timedelta(seconds=duration) if duration is not None else None
        if self.eyetracker:
            try:
                print("Starting tracking...")
                self.eyetracker.subscribe_to(self.gaze_id, self._collect_gaze_data, as_dictionary=True)
                while True:
                    if end_time and datetime.datetime.now() >= end_time:
                        self.stop_tracking()
                        break
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop_tracking()
            finally:
                if self.save_data:
                    data_path = os.path.join(os.path.dirname(__package__), "data")
                    if not os.path.exists(data_path):
                        os.makedirs(data_path)
                    with open(os.path.join(data_path, f"gaze_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"), "w") as file:
                        json.dump(
                            {
                                "screen_size": (self.screen_width, self.screen_height),
                                "data": self.gaze_data
                            }, file, indent=4)
                    print("Gaze Data saved!")
        else:
            print("No eye tracker found!")

    def stop_tracking(self):
        try:
            if self.eyetracker:
                print("Stopping tracking...")
                self.eyetracker.unsubscribe_from(self.gaze_id, self._collect_gaze_data)
            else:
                print("No eye tracker found!")
        except Exception as e:
            print(f"Error stopping tracking: {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--push_stream", action="store_true",
                        help="Push the data to LSL stream."),
    parser.add_argument("--data_rate", default=600, type=int,
                        help="The rate of the data stream.")
    parser.add_argument("--use_mock", action="store_true",
                        help="Use this to start the mock service")
    parser.add_argument("--fixation", action="store_true",
                        help="Use this to add fixations duration to the data stream")
    parser.add_argument("--dont_screen_nans", action="store_true",
                        help="Use this to avoid correcting for NaNs")
    parser.add_argument("--save_data", action="store_true",
                        help="Save the data to a file")
    parser.add_argument("--verbose", action="store_true",
                        help="Use this to display print statements")
    parser.add_argument("--duration", type=float,
                        help="The duration for which to track the data")
    args = parser.parse_args()

    print("Arguments: ", args)

    tracker = Tracker(
        data_rate=args.data_rate,
        use_mock=args.use_mock,
        fixation=args.fixation,
        screen_nans=not args.dont_screen_nans,
        verbose=args.verbose,
        push_stream=args.push_stream,
        save_data=args.save_data
    )
    if args.duration:
        print(f"Tracking for {args.duration} seconds...")
        tracker.start_tracking(duration=args.duration)
    else:
        tracker.start_tracking()