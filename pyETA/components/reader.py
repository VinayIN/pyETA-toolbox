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

    def __init__(self, tracker_params):
        super().__init__()
        self.tracker_params = tracker_params
        self.tracker = None
        self.running = False
        self.id = None

    def run(self):
        try:
            self.running = True
            self.id = threading.get_native_id()
            LOGGER.info("Starting tracker thread...")
            self.tracker = Tracker(**self.tracker_params)
            self.tracker.start_tracking(duration=self.tracker_params.get('duration', None))
            self.finished_signal.emit("Tracking completed successfully")
        except KeyboardInterrupt:
            LOGGER.info("KeyboardInterrupt!")
        except Exception as e:
            error_msg = f"Tracker error: {str(e)}"
            LOGGER.error(error_msg)
            self.error_signal.emit(error_msg)
        finally:
            self.stop()

    def stop(self):
        self.running = False
        self.id = None
        if self.tracker:
            self.tracker.stop_tracking()
        self.quit()
        self.wait()

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
    
    def clear_data(self):
        """
        Clears all internal buffers.
        """
        self.buffer_times, self.buffer_x, self.buffer_y = [], [], []
        self.fixation_data.clear()


class StreamThread(qtc.QThread):
    update_gaze_signal = qtc.pyqtSignal(list, list, list)
    update_fixation_signal = qtc.pyqtSignal(list, list, list)
    
    FIXATION_HISTORY_LIMIT = 100
    DATA_CLEANUP_INTERVAL = 10000
    BUFFER_SIZE = 100  # Keep last 100 gaze points
    
    def __init__(self, inlet):
        super().__init__()
        self.running = False
        self.id = None
        self.inlet = inlet
        self.fixation_data = defaultdict(lambda: {'count': 0, 'x': 0, 'y': 0})
        self.last_cleanup = datetime.datetime.now()
        
        # Gaze data buffers
        self.gaze_times = []
        self.gaze_x = []
        self.gaze_y = []
    
    def cleanup_old_fixations(self):
        """Remove old fixation data to prevent memory bloat"""
        if len(self.fixation_data) > self.FIXATION_HISTORY_LIMIT:
            # Convert keys to sorted list and keep only the most recent ones
            sorted_keys = sorted(self.fixation_data.keys())
            keys_to_remove = sorted_keys[:-self.FIXATION_HISTORY_LIMIT]
            for key in keys_to_remove:
                del self.fixation_data[key]
        
    def run(self):
        self.running = True
        self.id = threading.get_native_id()
        
        while self.running:
            try:
                sample, timestamp = self.inlet.pull_sample(timeout=0.0)
                current_time = datetime.datetime.now()
                
                # Periodic cleanup
                if (current_time - self.last_cleanup).total_seconds() >= self.DATA_CLEANUP_INTERVAL / 1000:
                    self.cleanup_old_fixations()
                    self.last_cleanup = current_time
                
                if sample is not None:
                    screen_width, screen_height = sample[-4], sample[-3]
                    
                    # Get the filtered gaze data
                    gaze_x = int((sample[7] if sample[7] else sample[16]) * screen_width)
                    gaze_y = int((sample[8] if sample[8] else sample[17]) * screen_height)
                    
                    # Update gaze buffers
                    self.gaze_times.append(current_time)
                    self.gaze_x.append(gaze_x)
                    self.gaze_y.append(gaze_y)
                    
                    # Maintain buffer size
                    if len(self.gaze_times) > self.BUFFER_SIZE:
                        self.gaze_times = self.gaze_times[-self.BUFFER_SIZE:]
                        self.gaze_x = self.gaze_x[-self.BUFFER_SIZE:]
                        self.gaze_y = self.gaze_y[-self.BUFFER_SIZE:]
                    
                    # Emit gaze data
                    self.update_gaze_signal.emit(
                        self.gaze_times.copy(), 
                        self.gaze_x.copy(), 
                        self.gaze_y.copy()
                    )
                    
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
        if self.inlet:
            self.inlet.close_stream()
        # Clear all buffers
        self.fixation_data.clear()
        self.gaze_times.clear()
        self.gaze_x.clear()
        self.gaze_y.clear()
        self.quit()
        self.wait()
