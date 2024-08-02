import json
import datetime
import os
import time
import sys
import tobii_research as tr
from collections import deque
import PyQt6.QtWidgets as qtw

class Tobii:
    def __init__(self, save_data: bool = False, verbose: bool = False):
        """Save_data flag saves the data to a file if set to True."""
        self.verbose = verbose
        self.save_data = save_data
        self.screen_width, self.screen_heigth = self.get_current_screen_size()
        print(f"Screen Resolution: {self.screen_width}x{self.screen_heigth}")
        eyetrackers = tr.find_all_eyetrackers()
        self.eyetracker = eyetrackers[0] if eyetrackers else None
        if self.eyetracker:
            screen_area = self.eyetracker.get_display_area()
            print(f"Address: {self.eyetracker.address}")
            print(f"Model: {self.eyetracker.model}")
            print(f"Serial number: {self.eyetracker.serial_number}")
            print("\n\nPress Ctrl+C to stop tracking...")
            
        self.gaze_data = []
        self.gaze_data_deque = deque(maxlen=100)
    
    def get_current_screen_size(self):
        app = qtw.QApplication(sys.argv)
        screen = app.primaryScreen()
        size = screen.size()
        width, height = size.width(), size.height()
        return width, height

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
        self.gaze_data_deque.append(data)
    
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
    
    def start_tracking(self, duration: float):
        """Starts tracking for the given duration (in seconds) and saves the data to a file."""
        if self.eyetracker:
            try:
                print(f"Starting tracking...for {duration} seconds")
                self.eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, self._append_gaze_data, as_dictionary=True)
                end_time = datetime.datetime.now() + datetime.timedelta(seconds=duration)
                while datetime.datetime.now() <= end_time:
                    continue
                print("Stopping tracking...")
                self.eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self._append_gaze_data)
            except KeyboardInterrupt:
                print("Stopping tracking...")
                self.eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self._append_gaze_data)
            finally:
                if self.save_data:
                    data_path = os.path.join(os.path.dirname(__package__), "data")
                    if not os.path.exists(data_path):
                        os.makedirs(data_path)
                    with open(os.path.join(data_path, f"gaze_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"), "w") as file:
                        json.dump(
                            {
                                "screen_size": (self.screen_width, self.screen_heigth),
                                "data": self.gaze_data
                            }, file, indent=4)
                    print("Gaze Data saved!")
        else:
            print("No eye tracker found!")

    def start_tracking_indefinite(self):
        """Start tracking indefinitely unless interrupted."""
        try:
            if self.eyetracker:
                print("Starting tracking...")
                self.eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, self._collect_gaze_data, as_dictionary=True)
                while True:
                    continue
            else:
                print("No eye tracker found!")
        except KeyboardInterrupt:
            print("Stopping tracking...")
            self.eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self._collect_gaze_data)

if __name__ == "__main__":
    tobii = Tobii(save_data=False, verbose=False)
    # tobii.start_tracking_indefinite()
    tobii.start_tracking(10)
        
