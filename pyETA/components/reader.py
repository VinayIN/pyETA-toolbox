import datetime
import threading
from collections import defaultdict
from mne_lsl import lsl

from pyETA.components.track import Tracker
from pyETA import LOGGER
import PyQt6.QtCore as qtc
import numpy as np


class TrackerThread(qtc.QThread):
    finished_signal = qtc.pyqtSignal(str)
    error_signal = qtc.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.tracker = None
        self.running = False
        self.id = None
    
    def set_variables(self, tracker_params):
        self.tracker_params = tracker_params

    def run(self):
        try:
            self.running = True
            self.id = threading.get_native_id()
            LOGGER.info("Starting tracker thread...")
            self.tracker = Tracker(**self.tracker_params)
            self.tracker.start_tracking(duration=self.tracker_params.get('duration', None))
            self.finished_signal.emit("Tracking completed successfully")
        except Exception as e:
            error_msg = f"Tracker error: {str(e)}"
            LOGGER.error(error_msg)
            self.error_signal.emit(error_msg)

    def stop(self):
        self.running = False
        self.id = None
        self.quit()
        self.wait()
        LOGGER.info("Tracker thread stopped!")

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
                # Get the filtered gaze data
                gaze_x = int((sample[7] if sample[7] else sample[16]) * screen_width)
                gaze_y = int((sample[8] if sample[8] else sample[17]) * screen_height)
                
                # Store regular gaze data
                self.buffer_times.append(current_time)
                self.buffer_x.append(gaze_x)
                self.buffer_y.append(gaze_y)
                
                # Process fixation data
                is_fixation = sample[3] or sample[12]
                if is_fixation:
                    fixation_time = sample[5] if sample[5] else sample[14]
                    key = f"{fixation_time}"
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
        LOGGER.info("GazeReader stopped!")
    
    def clear_data(self):
        """
        Clears all internal buffers.
        """
        self.buffer_times, self.buffer_x, self.buffer_y = [], [], []
        self.fixation_data.clear()

class StreamThread(qtc.QThread):
    update_gaze_signal = qtc.pyqtSignal(list, list, list)
    update_fixation_signal = qtc.pyqtSignal(list, list, list)
    
    def __init__(self):
        super().__init__()
        self.running = False
        self.id = None
        self.buffer_times, self.buffer_x, self.buffer_y = [], [], []
        self.fixation_data = defaultdict(lambda: {'count': 0, 'x': 0, 'y': 0})
        

    def set_variables(self, inlet, refresh_rate):
        self.inlet = inlet
        self.inlet = inlet
        self.refresh_rate = refresh_rate
        self.last_refresh = datetime.datetime.now()
    
    def run(self):
        self.running = True
        self.id = threading.get_native_id()
        
        while self.running:
            try:
                # Clear fixation data based on refresh rate
                if (datetime.datetime.now() - self.last_refresh) >= datetime.timedelta(seconds=self.refresh_rate):
                    self.fixation_data.clear()
                    self.buffer_times, self.buffer_x, self.buffer_y = [], [], []
                    self.last_refresh = datetime.datetime.now()
                
                sample, _ = self.inlet.pull_sample(timeout=0.0)
                if sample is None:
                    continue
                current_time = sample[-2]
                self.buffer_times.append(current_time)
                screen_width, screen_height = sample[-4], sample[-3]
                
                # Get the filtered gaze data
                gaze_x = int((sample[7] if sample[7] else sample[16]) * screen_width)
                gaze_y = int((sample[8] if sample[8] else sample[17]) * screen_height)
                self.buffer_x.append(gaze_x)
                self.buffer_y.append(gaze_y)
                
                # Emit gaze data
                self.update_gaze_signal.emit(self.buffer_times, self.buffer_x, self.buffer_y)
                
                # Process fixation data
                fixation_time = sample[5] if sample[5] else sample[14]
                is_fixation = sample[3] or sample[12]
                
                if is_fixation and fixation_time:
                    key = str(fixation_time)
                    self.fixation_data[key]['count'] += 1
                    self.fixation_data[key]['x'] = gaze_x
                    self.fixation_data[key]['y'] = gaze_y
                    
                    # Emit fixation data
                    x_coords = [data['x'] for data in self.fixation_data.values()]
                    y_coords = [data['y'] for data in self.fixation_data.values()]
                    counts = [data['count'] for data in self.fixation_data.values()]
                    self.update_fixation_signal.emit(x_coords, y_coords, counts)
                        
            except Exception as e:
                LOGGER.error(f"Stream error: {str(e)}")
                
    def stop(self):
        self.running = False
        self.id = None
        self.buffer_times, self.buffer_x, self.buffer_y = [], [], []
        self.fixation_data.clear()
        self.quit()
        self.wait()
        LOGGER.info("Stream thread stopped!")