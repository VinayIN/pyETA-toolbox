import datetime
import threading
from collections import deque
from mne_lsl import lsl

from pyETA.components.track import Tracker
from pyETA import LOGGER
import PyQt6.QtCore as qtc
import numpy as np
import time


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
        """Stop tracker thread."""
        self.running = False
        self.id = None
        if self.tracker and self.tracker.id:
            self.tracker.signal_break()
            self.tracker = None
        self.wait()
        self.quit()
        LOGGER.info("Tracker thread stopped!")


class GazeReader:
    def __init__(self):
        """
        Initializes the GazeReader instance.
        """
        self.buffer_times, self.buffer_x, self.buffer_y = [], [], []
        self.fixation_data = deque(maxlen=1000)
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
                    self.fixation_data.append((gaze_x, gaze_y, 1, datetime.datetime.fromtimestamp(fixation_time)))

    def get_data(self, fixation=False):
        """
        Returns collected data and clears the buffer.
        
        Args:
            fixation (bool): If True, returns fixation data instead of regular gaze data
        """
        if fixation:
            fixation_points = [(x, y, count) for x, y, count, _ in self.fixation_data]
            self.fixation_data.clear()
            return fixation_points
        else:
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
    found_signal = qtc.pyqtSignal(str)
    update_gaze_signal = qtc.pyqtSignal(np.ndarray, np.ndarray, np.ndarray)
    update_fixation_signal = qtc.pyqtSignal(np.ndarray, np.ndarray, np.ndarray, np.ndarray)
    error_signal = qtc.pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.id = None
        self.buffer = deque(maxlen=5000)
        self.fixation_buffer = deque(maxlen=20)
        self.current_fixation = None
    
    def set_variables(self, tracker_params):
        self.tracker_thread = TrackerThread()
        self.tracker_thread.set_variables(tracker_params)
        self.tracker_thread.finished_signal.connect(lambda msg: LOGGER.info(msg))
        self.tracker_thread.error_signal.connect(self.error_signal.emit)

    def run(self):
        try:
            self.tracker_thread.start()
            streams = lsl.resolve_streams(timeout=1, name='tobii_gaze_fixation')
            if not streams:
                error_msg = "'tobii_gaze_fixation' stream not found. ✘"
                LOGGER.error(error_msg)
                self.error_signal.emit(error_msg)
                return
            inlet = lsl.StreamInlet(streams[0])
            msg = f"Stream: {streams[0].name} ✔"
            LOGGER.info(msg)
            self.found_signal.emit(msg)

            self.running = True
            self.id = threading.get_native_id()
            
            while self.running:
                sample, _ = inlet.pull_sample(timeout=0.1)
                if sample is None or len(sample) < 22:
                    continue
                current_time = sample[-2]
                screen_width, screen_height = sample[-4], sample[-3]
                
                gaze_x = int((sample[7] if sample[7] else sample[16]) * screen_width)
                gaze_y = int((sample[8] if sample[8] else sample[17]) * screen_height)
                
                self.buffer.append((current_time, gaze_x, gaze_y))
                gaze_array = np.array(list(self.buffer), 
                                        dtype=[('timestamp', float), ('x', int), ('y', int)])
                self.update_gaze_signal.emit(
                    gaze_array['timestamp'],
                    gaze_array['x'],
                    gaze_array['y']
                )

                fixation_time = sample[5] if sample[5] else sample[14]
                is_fixation = sample[3] or sample[12]
                if is_fixation and fixation_time:
                    if self.current_fixation is None:
                        self.current_fixation = {'x': gaze_x, 'y': gaze_y, 'count': 1, 'timestamp': fixation_time}
                    else:
                        count = self.current_fixation['count']
                        self.current_fixation['x'] = (self.current_fixation['x'] * count + gaze_x) / (count + 1)
                        self.current_fixation['y'] = (self.current_fixation['y'] * count + gaze_y) / (count + 1)
                        self.current_fixation['count'] += 1
                elif self.current_fixation is not None:
                    self.fixation_buffer.append((
                        self.current_fixation['x'],
                        self.current_fixation['y'],
                        self.current_fixation['count'],
                        self.current_fixation['timestamp']
                    ))
                    self.current_fixation = None

                fixation_array = np.array(list(self.fixation_buffer), 
                                        dtype=[('x', float), ('y', float), ('count', int), ('timestamp', float)])
                self.update_fixation_signal.emit(
                    fixation_array['x'],
                    fixation_array['y'],
                    fixation_array['count'],
                    fixation_array['timestamp']
                )
                
            self.tracker_thread.stop()
            inlet.close_stream()
                        
        except Exception as e:
            LOGGER.error(f"Stream error: {str(e)}")
            self.error_signal.emit(f"Stream error: {str(e)}")
    
    def stop(self):
        self.running = False
        self.id = None
        self.buffer.clear()
        self.fixation_buffer.clear()
        self.current_fixation = None
        self.wait()
        self.quit()
        LOGGER.info("Stream thread stopped!")
