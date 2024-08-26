import time
import random
import datetime
import argparse
import os
import json
import PyQt6.QtWidgets as qtw
import sys
import pynput
from typing import Optional, Callable

class MockEyeTracker:
    def __init__(self, data_rate: int = 60, save_data: bool = False, verbose: bool = False):
        self.data_rate = data_rate
        self.verbose = verbose
        self.save_data = save_data
        self.screen_width, self.screen_height = self.get_current_screen_size()
        self.id = "ZA03046BINAY2024"
        print(f"Screen Resolution: {self.screen_width}x{self.screen_height}")
        print(f"Mock Serial Number: {self.id}")
        print("\n\nPress Ctrl+C to stop tracking...")
        self.gaze_data = []
        self.callbacks = {}
        self.curr_x = 0.0
        self.curr_y = 0.0
        self.should_stop = False
        self.listener = None

    def get_current_screen_size(self):
        app = qtw.QApplication(sys.argv)
        screen = app.primaryScreen()
        size = screen.size()
        width, height = size.width(), size.height()
        return width, height

    def get_timestamp(self):
        return datetime.datetime.now().isoformat()

    def on_move(self, x, y):
        self.curr_x = x / self.screen_width
        self.curr_y = y / self.screen_height

    def update_callbacks(self, data):
        if "gaze_data" in self.callbacks:
            self.callbacks["gaze_data"](data)

    def subscribe_to(self, callback: Optional[Callable] = None, as_dictionary: bool = True):
        if callback is None:
            raise ValueError("Callback cannot be None")
        self.callbacks["gaze_data"] = callback

    def unsubscribe_from(self, callback: Optional[Callable] = None):
        if callback is None:
            raise ValueError("Callback cannot be None")
        if "gaze_data" in self.callbacks:
            del self.callbacks["gaze_data"]
        if self.listener:
            self.listener.stop()

    def run(self):
        self.listener = pynput.mouse.Listener(on_move=self.on_move)
        with self.listener as lis:
            while not self.should_stop:
                time.sleep(1 / self.data_rate)
                x = self.curr_x
                y = self.curr_y
                data = {
                    "device_time_stamp": time.perf_counter_ns(),
                    "system_time_stamp": time.perf_counter_ns(),
                    "left_gaze_point_on_display_area": [x, y],
                    "left_gaze_point_validity": random.uniform(0, 1) > 0.5,
                    "right_gaze_point_on_display_area": [x, y],
                    "right_gaze_point_validity": random.uniform(0, 1) > 0.5,
                    "left_pupil_diameter": random.uniform(4, 8),
                    "left_pupil_validity": random.uniform(0, 1) > 0.5,
                    "right_pupil_diameter": random.uniform(4, 8),
                    "right_pupil_validity": random.uniform(0, 1) > 0.5
                }

                self.update_callbacks(data)
        lis.join()

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
        self.gaze_data.append(data)

    def start_tracking(self):
        """Starts tracking continuously and saves the data to a file, if save_data flag is set to True during initialization."""
        callback_func = self._append_gaze_data if self.save_data else self._collect_gaze_data
        try:
            print("Starting tracking...")
            self.subscribe_to(callback_func, as_dictionary=True)
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

    def stop_tracking(self):
        print("Stopping tracking...")
        self.should_stop = True
        callback_func = self._append_gaze_data if self.save_data else self._collect_gaze_data
        try:
            self.unsubscribe_from(callback_func)
        except Exception as e:
            print(f"Error stopping tracking: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_rate", help="Data rate in Hz", type=int, default=60)
    parser.add_argument("--save_data", help="Save the data to a file", action="store_true")
    parser.add_argument("--verbose", help="Print the gaze data", action="store_true")
    args = parser.parse_args()

    mock_eye_tracker = MockEyeTracker(data_rate=args.data_rate, save_data=args.save_data, verbose=args.verbose)
    mock_eye_tracker.start_tracking()