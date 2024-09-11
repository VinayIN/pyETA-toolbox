import argparse
import sys
import datetime
import os
import json

from mne_lsl import lsl
#import tobii_research as tr
import numpy as np
from EyeTrackerAnalyzer.components.mock import MockEyeTracker
from EyeTrackerAnalyzer.components.utils import get_current_screen_size

class Tracker:
    def __init__(self, data_rate=600, use_mock=False, screen_nans=True, verbose=False, save_data=False):
        self.lsl_gaze_outlet = None
        self.lsl_eye_openness_outlet = None
        self.screen_width, self.screen_height = get_current_screen_size()
        self.data_rate = data_rate
        self.screen_nans = screen_nans
        self.verbose = verbose
        self.save_data = save_data
        self.gaze_data = []
        
        if use_mock:
            print("Using a mock service.")
            self.eyetracker = MockEyeTracker(data_rate=self.data_rate, verbose=self.verbose)
            self.eyetracker.start()
        else:
            print("Using tobii to find eyetrackers.")
            self.eyetrackers = tr.find_all_eyetrackers()
            self.eyetracker = self.eyetrackers[0] if self.eyetrackers else None
        if self.eyetracker:
            print(f"Address: {self.eyetracker.address}")
            print(f"Model: {self.eyetracker.model}")
            print(f"Name: {self.eyetracker.device_name}")
            print(f"Serial number: {self.eyetracker.serial_number}")
        else:
            print("No eye tracker device found.")
        print("\n\nPress Ctrl+C to stop tracking...")

    def get_timestamp(self):
        return datetime.datetime.now().isoformat()
    
    def _collect_gaze_data(self, gaze_data):
        data = {
            "timestamp": self.get_timestamp(),
            "left_eye": {
                "gaze_point": gaze_data.get("left_gaze_point_on_display_area"),
                "pupil_diameter": gaze_data.get("left_pupil_diameter")
            },
            "right_eye": {
                "gaze_point": gaze_data.get("right_gaze_point_on_display_area"),
                "pupil_diameter": gaze_data.get("right_pupil_diameter")
            }
        }
        if self.verbose: print(f'L: {data["left_eye"]["gaze_point"]}, R: {data["right_eye"]["gaze_point"]}')
    
    def _append_gaze_data(self, gaze_data):
        data = {
            "timestamp": self.get_timestamp(),
            "left_eye": {
                "gaze_point": gaze_data.get("left_gaze_point_on_display_area"),
                "pupil_diameter": gaze_data.get("left_pupil_diameter")
            },
            "right_eye": {
                "gaze_point": gaze_data.get("right_gaze_point_on_display_area"),
                "pupil_diameter": gaze_data.get("right_pupil_diameter")
            },
        }
        if self.verbose: print(f'L: {data["left_eye"]["gaze_point"]}, R: {data["right_eye"]["gaze_point"]}')
        self.gaze_data.append(data)

    def setup_streams(self):
        info = lsl.StreamInfo(
            name='tobii_gaze',
            stype='Gaze',
            n_channels=14,
            sfreq=self.data_rate,
            dtype='float64',
            source_id=self.eyetracker.serial_number)
        self.lsl_gaze_outlet = lsl.StreamOutlet(info)

    def start_tracking(self):
        """Starts tracking continuously and saves the data to a file, if save_data flag is set to True during initialization."""
        callback_func = self._append_gaze_data if self.save_data else self._collect_gaze_data
        if self.eyetracker:
            try:
                print("Starting tracking...")
                self.eyetracker.subscribe_to(self.eyetracker.EYETRACKER_GAZE_DATA, callback_func, as_dictionary=True)
                while True:
                    continue
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
        callback_func = self._append_gaze_data if self.save_data else self._collect_gaze_data
        try:
            if self.eyetracker:
                print("Stopping tracking...")
                self.eyetracker.unsubscribe_from(self.eyetracker.EYETRACKER_GAZE_DATA, callback_func)
            else:
                print("No eye tracker found!")
        except Exception as e:
            print(f"Error stopping tracking: {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_rate", default=600, type=int,
                        help="The rate of the data stream.")
    parser.add_argument("--use_mock", action="store_true",
                        help="Use this to start the mock service")
    parser.add_argument("--dont_screen_nans", action="store_true",
                        help="Use this to avoid correcting for NaNs")
    parser.add_argument("--save_data", action="store_true",
                        help="Save the data to a file")
    parser.add_argument("--verbose", action="store_true",
                        help="Use this to display print statements")
    args = parser.parse_args()

    print("Arguments: ", args)

    tracker = Tracker(
        data_rate=args.data_rate,
        use_mock=args.use_mock,
        screen_nans=not args.dont_screen_nans,
        verbose=args.verbose,
        save_data=args.save_data
    )
    
    tracker.start_tracking()