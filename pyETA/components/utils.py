import warnings
import sys
import math
import platform
import datetime
import multiprocessing
from typing import List, Optional
import PyQt6.QtWidgets as qtw
import PyQt6.QtGui as qtg
import numpy as np
import os
import glob
import psutil
from pyETA import __datapath__, LOGGER

def get_current_screen_size(screen_index=0):
    app = qtw.QApplication.instance()
    app_created = False

    if app:
        LOGGER.info("This framework application already exists. Using an instance!")
    else:
        app = qtw.QApplication(sys.argv)
        app_created = True
        LOGGER.info("Created a new application to fetch the geometry!")

    screens = app.screens()

    try:
        if screen_index < len(screens):
            screen = screens[screen_index]
            geometry = screen.geometry()
            return geometry.width(), geometry.height()
        else:
            raise ValueError(f"Invalid screen index. Only {len(screens)} screen(s) available. (starting index from 0)")
    except Exception as e:
        LOGGER.error(str(e))
        raise e
    finally:
        if app_created:
            app.quit()
            LOGGER.info("Quitting the application created to fetch the geometry.")
    return 0, 0

def get_system_info():
    node = platform.node()
    system = platform.system()
    machine = platform.machine()
    time_now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"{node}_{system}_{machine}_{time_now}"

def get_timestamp():
    return datetime.datetime.now().timestamp()


class OneEuroFilter:
    def __init__(
        self,
        initial_time: float,
        initial_value: float,
        initial_derivative: float = 0.0,
        min_cutoff: float = 1.0,
        beta: float = 0.0,
        derivative_cutoff: float = 1.0,
    ):
        """Initialize the one euro filter."""
        # Previous values.
        self.previous_value: float = initial_value
        self.previous_derivative: float = initial_derivative
        self.previous_time: float = initial_time
        # The parameters.
        self.min_cutoff: float = min_cutoff
        self.beta: float = beta
        self.derivative_cutoff: float = derivative_cutoff

    def smoothing_factor(
            self,
            time_elapsed: float,
            cutoff_frequency: float) -> float:
            r = 2 * math.pi * cutoff_frequency * time_elapsed
            return self.__no_nan(r) / (self.__no_nan(r) + 1)

    def exp_smoothing(
            self,
            alpha: float,
            current_value: float,
            previous_value: float
        ) -> float:
        return self.__no_nan(alpha) * self.__no_nan(current_value) + (1 - self.__no_nan(alpha)) * self.__no_nan(previous_value)
    
    def __no_nan(self, value):
        return value if not np.isnan(value) else 0.0

    def __call__(self, current_time: float, current_value: float) -> float:
        """Compute the filtered signal."""
        time_elapsed = current_time - self.previous_time
        LOGGER.debug(f"time elapsed: {time_elapsed}")

        # The filtered derivative of the signal.
        alpha_derivative = self.smoothing_factor(time_elapsed, self.derivative_cutoff)
        current_derivative = (current_value - self.previous_value) / time_elapsed
        filtered_derivative = self.exp_smoothing(alpha_derivative, current_derivative, self.previous_derivative)
        LOGGER.debug(f"alpha_derivative: {alpha_derivative}, current_derivative: {current_derivative}, filtered_derivative: {filtered_derivative}")

        # The filtered signal.
        adaptive_cutoff = self.min_cutoff + self.beta * abs(filtered_derivative)
        alpha = self.smoothing_factor(time_elapsed, adaptive_cutoff)
        filtered_value = self.exp_smoothing(alpha, current_value, self.previous_value)
        LOGGER.debug(f"alpha: {alpha}, value: {current_value}, previous_value: {self.previous_value}, filtered: {filtered_value}")

        # Memorize the previous values.
        self.previous_value = filtered_value
        self.previous_derivative = filtered_derivative
        self.previous_time = current_time

        return filtered_value
    
def get_euler_form(point, reference=None):
    "If reference provided, point of origin changes to reference. Provide the parameters in cartesian form"
    point = complex(point[0], point[1])
    if reference is not None:
        point = point - complex(reference[0] - reference[1])
    p = math.atan2(point.imag, point.real)
    m = math.sqrt(point.real**2 + point.imag**2)
    return m,p

def get_cartesian(euler, reference=None):
    x = euler[0] * math.cos(euler[1])
    y = euler[0] * math.sin(euler[1])
    if reference is not None:
        ref_x, ref_y = get_cartesian(reference)
        x = x + ref_x
        y = y + ref_y
    return x, y

def phase_to_degree(phase):
    if phase < 0:
        phase += 2 * math.pi
    return phase * 180 / math.pi

def degree_to_phase(degree):
    if degree < 0:
        degree += 360
    return degree * math.pi / 180

def get_actual_from_relative(relative, screen_width, screen_height):
    pixel_x = relative[0]*screen_width
    pixel_y = relative[1]*screen_height
    return int(pixel_x), int(pixel_y)

def get_relative_from_actual(actual, screen_width, screen_height):
    pixel_x = actual[0]/screen_width
    pixel_y = actual[1]/screen_height
    return pixel_x, pixel_y

def get_distance(point1, point2):
    return math.sqrt((point1[0]-point2[0])**2 + (point1[1]-point2[1])**2)

def get_file_names(prefix, directory=None):
    '''
    if directory is None, check from the default path specified in EyeTrackerAnalyzer.__dirpath__
    '''
    if directory is None:
        directory = __datapath__
    directory = os.path.abspath(directory)
    if os.path.exists(directory):
        return glob.glob(os.path.join(directory, f'{prefix}*'))
    return []


class ProcessStatus:
    """Class to maintain process status and error information"""
    def __init__(self):
        self.active_processes = {}
    
    def add_process(self, pid, process):
        self.active_processes[pid] = {
            'process': process,
            'start_time': datetime.datetime.now(),
            'status': 'starting',
            'last_error': None,
            'last_update': datetime.datetime.now()
        }
    
    def remove_process(self, pid):
        if pid in self.active_processes:
            del self.active_processes[pid]
    
    def update_status(self, pid, status, error=None):
        if pid in self.active_processes:
            self.active_processes[pid].update({
                'status': status,
                'last_error': error,
                'last_update': datetime.datetime.now()
            })

    def get_process_info(self, pid):
        return self.active_processes.get(pid)
    
    def cleanup(self):
        LOGGER.info("Cleaning up initiated!")
        for pid in self.active_processes.keys():
            try:
                process = psutil.Process(pid)
                LOGGER.info(f"Terminating process {pid}")
                process.terminate()
                try:
                    process.wait(timeout=1)
                except psutil.TimeoutExpired:
                    LOGGER.warning(f"Process {pid} did not terminate within timeout, forcing kill")
                    process.kill()
            except psutil.NoSuchProcess:
                LOGGER.info(f"Process {pid} already terminated")
            except Exception as e:
                LOGGER.error(f"Error cleaning up process {pid}: {str(e)}")
        for p in multiprocessing.active_children():
            try:
                LOGGER.info(f"Terminating child process {p.pid}")
                p.terminate()
                p.join(timeout=1)
                if p.is_alive():
                    LOGGER.warning(f"Force killing process {p.pid}")
                    p.kill()
                    p.join()
            except Exception as e:
                LOGGER.error(f"Error during cleanup process {p.pid}: {str(e)}")
        self.active_processes.clear()
        LOGGER.info("Cleanup complete")

