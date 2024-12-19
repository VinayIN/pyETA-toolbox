import datetime
from collections import defaultdict

class GazeReader:
    def __init__(self):
        """
        Initializes the GazeReader instance.
        """
        self.buffer_times, self.buffer_x, self.buffer_y = [], [], []
        self.fixation_data = defaultdict(lambda: {'count': 0, 'x': 0, 'y': 0, 'timestamp': None})
        self.running = True

    def read_stream(self, inlet):
        """
        Reads data from the given LSL inlet and appends it to the buffer.
        """
        while self.running and inlet:
            sample, _ = inlet.pull_sample(timeout=0.0)
            if sample is not None:
                current_time = datetime.datetime.fromtimestamp(sample[-2])
                screen_width, screen_height = sample[-4], sample[-3]
                gaze_x = int(sample[0] * screen_width)
                gaze_y = int(sample[1] * screen_height)
                
                # Store regular gaze data
                self.buffer_times.append(current_time)
                self.buffer_x.append(gaze_x)
                self.buffer_y.append(gaze_y)
                
                # Process fixation data
                is_fixation = sample[3] or sample[11]  # Check both eyes' fixation flags
                if is_fixation:
                    fixation_time = sample[5] if sample[3] else sample[13]  # Get corresponding timestamp
                    key = f"{gaze_x}_{gaze_y}"
                    self.fixation_data[key]['count'] += 1
                    self.fixation_data[key]['x'] = gaze_x
                    self.fixation_data[key]['y'] = gaze_y
                    self.fixation_data[key]['timestamp'] = datetime.datetime.fromtimestamp(fixation_time)

    def get_data(self, fixation=False):
        """
        Returns collected data and clears the buffer.
        
        Args:
            fixation (bool): If True, returns fixation data instead of regular gaze data
        """
        if fixation:
            fixation_points = [
                (data['x'], data['y'], data['count'])
                for data in self.fixation_data.values()
                if data['timestamp'] is not None
            ]
            # Clear old fixation data
            self.fixation_data.clear()
            return fixation_points
        else:
            # Return regular gaze data
            times, x, y = self.buffer_times, self.buffer_x, self.buffer_y
            self.buffer_times, self.buffer_x, self.buffer_y = [], [], []
            return times, x, y

    def stop(self):
        """
        Stops the data collection process.
        """
        self.running = False
    
    def clear_data(self):
        """
        Clears all internal buffers.
        """
        self.buffer_times, self.buffer_x, self.buffer_y = [], [], []
        self.fixation_data.clear()