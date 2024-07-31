import json
import datetime
import os
import tobii_research as tr

class Tobii:
    def __init__(self):
        self.eyetracker = tr.find_all_eyetrackers()[0] if self.eyetrackers else None
        self.gaze_data = []

    def get_timestamp(self):
        return datetime.datetime.now().isoformat()
    
    def _append_gaze_data(self):
        data = {
            "timestamp": self.get_timestamp(),
            "left_eye": {
                "gaze_point": self.eyetracker.get_gaze_data().get("left_gaze_point_on_display_area"),
                "pupil_diameter": self.eyetracker.get_gaze_data().get("left_pupil_diameter")
            },
            "right_eye": {
                "gaze_point": self.eyetracker.get_gaze_data().get("right_gaze_point_on_display_area"),
                "pupil_diameter": self.eyetracker.get_gaze_data().get("right_pupil_diameter")
            }
        }
        self.gaze_data.append(data)
    
    def start_tracking(self, duration: float):
        """Starts tracking for the given duration (in seconds) and saves the data to a file."""
        if self.eyetracker:
            print("Starting tracking...")
            end_time = datetime.datetime.now() + datetime.timedelta(seconds=duration)
            while datetime.datetime.now() < end_time:
                self._append_gaze_data()
            data_path = os.path.join(os.path.dirname(__package__), "data")
            if not os.path.exists(data_path):
                os.makedirs(data_path)
            with open(os.path.join(data_path, f"gaze_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"), "w") as file:
                json.dump(self.gaze_data, file, indent=4)
            print("Data saved!")
        else:
            print("No eye tracker found!")

if __name__ == "__main__":
    tobii = Tobii()
    tobii.start_tracking(duration=2)
        
