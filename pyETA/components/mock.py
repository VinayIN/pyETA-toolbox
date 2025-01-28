import datetime
import random
import argparse
import time
from threading import Thread
from pynput import mouse
from pyETA.components import utils

EYETRACKER_GAZE_DATA = 'mock_gaze_data'
CAPABILITY_HAS_GAZE_DATA = 'mock_has_gaze_data'

KNOWN_DATA_IDS = [EYETRACKER_GAZE_DATA]
device_capabilities = [CAPABILITY_HAS_GAZE_DATA]

class MockEyeTracker(Thread):
    def __init__(self, data_rate=600, verbose=False):
        Thread.__init__(self, name="MockEyeTracker", daemon=True)
        self.verbose = verbose
        self.data_rate = data_rate
        self.listener = None
        self.screen_width, self.screen_height = utils.get_current_screen_size()
        self.address ="ZA03046BINAY2024"
        self.model = "ZA03046BINAY2024"
        self.device_name = "Mock Tracker"
        self.serial_number = "ZA03046BINAY2024"
        self.callbacks = dict()
        self.curr_x = 0.0
        self.curr_y = 0.0
        self.should_stop = False

    def subscribe_to(self, id, callback, as_dictionary=True):
        if id not in KNOWN_DATA_IDS:
            raise ValueError(f"Unknown data type: {id}")

        if callback is None:
            raise ValueError("Callback cannot be None")

        self.callbacks[id] = callback

    def unsubscribe_from(self, id, callback):
        if id not in KNOWN_DATA_IDS:
            raise ValueError(f"Unknown data type: {id}")

        if callback is None:
            raise ValueError("Callback cannot be None")
        
        if id in self.callbacks:
            del self.callbacks[id]

        if not self.callbacks:
            self.stop()

    def on_move(self, x, y):
        corr_x = max(0, min(x, self.screen_width - 1))
        corr_y = max(0, min(y, self.screen_height - 1))
        self.curr_x = corr_x / self.screen_width
        self.curr_y = corr_y / self.screen_height

    def run(self):
        self.listener = mouse.Listener(on_move=self.on_move)
        with self.listener as lis:
            while not self.should_stop:
                time.sleep(.99 / self.data_rate)
                x = self.curr_x
                y = self.curr_y

                if EYETRACKER_GAZE_DATA in self.callbacks:
                    self.callbacks[EYETRACKER_GAZE_DATA](
                        {
                            "device_time_stamp": utils.get_timestamp(),
                            "system_time_stamp": utils.get_timestamp(),
                            'left_gaze_point_on_display_area': [x, y],
                            'left_gaze_point_validity': random.uniform(0, 1) > 0.5,
                            'right_gaze_point_on_display_area': [x, y],
                            'right_gaze_point_validity': random.uniform(0, 1) > 0.5,
                            'left_pupil_diameter': 8.0 + 4 * random.uniform(-1, 1),
                            'left_pupil_validity': random.uniform(0, 1) > 0.5,
                            'right_pupil_diameter': 8.0 + 4 * random.uniform(-1, 1),
                            'right_pupil_validity': random.uniform(0, 1) > 0.5
                        })
            lis.join()

    def stop(self):
        self.should_stop = True

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_rate", help="Data rate in Hz", type=int, default=60)
    parser.add_argument("--verbose", help="Print the gaze data", action="store_true")
    args = parser.parse_args()

    mock_eye_tracker = MockEyeTracker(data_rate=args.data_rate, verbose=args.verbose)
    mock_eye_tracker.start()
    while True:
        try:
            continue
        except KeyboardInterrupt:
            mock_eye_tracker.stop()