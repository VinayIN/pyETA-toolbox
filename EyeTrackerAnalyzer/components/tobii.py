import json
import datetime
import os
import tobii_research as tr

class Tobii:
    def __init__(self, save_data: bool = False):
        """Save_data flag saves the data to a file if set to True."""
        self.save_data = save_data
        eyetrackers = tr.find_all_eyetrackers()
        self.eyetracker = eyetrackers[0] if eyetrackers else None
        if self.eyetracker:
            print("Address: " + self.eyetracker.address)
            print("Model: " + self.eyetracker.model)
            print("Name (It's OK if this is empty): " + self.eyetracker.device_name)
            print("Serial number: " + self.eyetracker.serial_number)
        self.gaze_data = []

    def get_timestamp(self):
        return datetime.datetime.now().isoformat()
    
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
            }
        }
        print(f'L: {data["left_eye"]["gaze_point"]}, R: {data["right_eye"]["gaze_point"]}')
        self.gaze_data.append(data)
    
    def start_tracking(self, duration: float):
        """Starts tracking for the given duration (in seconds) and saves the data to a file."""
        if self.eyetracker:
            print("Starting tracking...")
            self.eyetracker.subscribe_to(tr.EYETRACKER_GAZE_DATA, self._append_gaze_data, as_dictionary=True)
            end_time = datetime.datetime.now() + datetime.timedelta(seconds=duration)
            while datetime.datetime.now() <= end_time:
                continue
            self.eyetracker.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self._append_gaze_data)
            if self.save_data:
                data_path = os.path.join(os.path.dirname(__package__), "data")
                if not os.path.exists(data_path):
                    os.makedirs(data_path)
                with open(os.path.join(data_path, f"gaze_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"), "w") as file:
                    json.dump(self.gaze_data, file, indent=4)
                print("Data saved!")
        else:
            print("No eye tracker found!")

if __name__ == "__main__":
    tobii = Tobii(save_data=False)
    tobii.start_tracking(duration=2)
        
