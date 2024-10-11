import argparse
import sys
import datetime
import os
import json
import time
import click

from typing import Optional
from mne_lsl import lsl
from collections import namedtuple
from dataclasses import dataclass
from pyETA import __datapath__, LOGGER
import pyETA.components.mock as eta_mock
import pyETA.components.utils as eta_utils
try:
    import tobii_research as tr
except ModuleNotFoundError:
    LOGGER.error("Without tobii_research library, Tobii eye-tracker won't work.")
import numpy as np

@dataclass
class FixationTuple:
    is_fixated: bool = False
    velocity: float = 0.0
    x: float = np.nan
    y: float = np.nan
    filtered_x: float = np.nan
    filtered_y: float = np.nan
    timestamp: float = np.nan
    elapsed_time: float = 0.0
    duration: float = 0.0

class Tracker:
    def __init__(
            self,
            data_rate=600,
            use_mock=False,
            fixation=False,
            velocity_threshold=0.5,
            screen_nans=True,
            verbose=False,
            push_stream=False,
            save_data=False,
            **kwargs
        ):
        self.screen_width, self.screen_height = eta_utils.get_current_screen_size()
        self.data_rate = data_rate
        self.screen_nans = screen_nans
        self.verbose = verbose
        self.save_data = save_data
        self.use_mock = use_mock
        self.fixation = fixation
        self.velocity_threshold = velocity_threshold
        self.push_stream = push_stream
        self.gaze_data = []
        self.gaze_id = None
        self.lsl_gaze_outlet = None
        
        try:
            if self.use_mock:
                LOGGER.info("Using a mock service.")
                self.gaze_id = eta_mock.EYETRACKER_GAZE_DATA
                
                self.eyetracker = eta_mock.MockEyeTracker(data_rate=self.data_rate, verbose=self.verbose)
                self.eyetracker.start()
            else:
                LOGGER.info("Using tobii to find eyetrackers.")
                self.gaze_id = tr.EYETRACKER_GAZE_DATA
                self.eyetrackers = tr.find_all_eyetrackers()
                self.eyetracker = self.eyetrackers[0] if self.eyetrackers else None
            if self.eyetracker:
                LOGGER.info(f"Screen Resolution: {self.screen_width}x{self.screen_height}")
                LOGGER.info(f"Address: {self.eyetracker.address}")
                LOGGER.info(f"Model: {self.eyetracker.model}")
                LOGGER.info(f"Name: {self.eyetracker.device_name}")
                LOGGER.info(f"Serial number: {self.eyetracker.serial_number}")
            else:
                raise ValueError("No eye tracker device/Mock found.")
        except Exception as e:
            raise ValueError(f"Error initializing the eye tracker: {e}")
        self.__fixation_left = FixationTuple()
        self.__fixation_right = FixationTuple()
        if self.fixation:
            min_cutoff = 0.004
            beta = 0.7
            self.__one_euro_filter = self.create_filter(
                min_cutoff,
                beta,
                elements=["left_eye_x", "left_eye_y", "right_eye_x", "right_eye_y"])

        if self.push_stream:
            debug = lsl.StreamInfo(
                name='tobii_gaze_fixation',
                stype='Gaze',
                n_channels=22,
                sfreq=self.data_rate,
                dtype='float64',
                source_id=self.eyetracker.serial_number)
            self.lsl_gaze_outlet = lsl.StreamOutlet(debug)
            LOGGER.info(f"LSL Stream Info: {self.lsl_gaze_outlet.get_sinfo()}")
        LOGGER.info(f"Member Variables: {vars(self)}")
        print("Press Ctrl+C to stop tracking...")
    
    def create_filter(self, min_cutoff, beta, elements: list):
        Filter = namedtuple('Filter', elements)
        objects = {}
        for keyword in elements:
            filter_element = eta_utils.OneEuroFilter(
                initial_time=eta_utils.get_timestamp(),
                initial_value=0.0,
                min_cutoff=min_cutoff,
                beta=beta
            )
            LOGGER.debug(f"{keyword}:  {filter_element.previous_time}")
            objects[keyword] = filter_element
        return Filter(**objects)

    def _update_fixation_data(self, t, x, y, element):
        def calculate(previous_t, t, filtered_x, filtered_y):
            distance = np.sqrt((filtered_x - x)**2 + (filtered_y - y)**2)
            elapsed_time = t - previous_t
            velocity = distance / elapsed_time
            is_fixated = False
            if velocity <= self.velocity_threshold:
                is_fixated = True
            LOGGER.debug(f"Distance: {distance}, Elapsed_Time: {elapsed_time}, Velocity: {velocity}")
            return is_fixated, velocity, elapsed_time
        if element == "left_eye":
            previous_t = min(self.__one_euro_filter.left_eye_x.previous_time, self.__one_euro_filter.left_eye_y.previous_time)
            
            # filter for x
            filtered_x = self.__one_euro_filter.left_eye_x(t, x)
            # filter for y
            filtered_y = self.__one_euro_filter.left_eye_y(t, y)
            LOGGER.debug(f"{element}: {previous_t}, {t}, ({x}, {filtered_x}),  ({y}, {filtered_y})")
            is_fixated, velocity, elapsed_time = calculate(previous_t, t, filtered_x, filtered_y)
            self.__fixation_left.x = x
            self.__fixation_left.y = y
            self.__fixation_left.filtered_x = filtered_x
            self.__fixation_left.filtered_y = filtered_y
            self.__fixation_left.velocity = velocity
            self.__fixation_left.is_fixated = is_fixated
            self.__fixation_left.timestamp = t if not is_fixated else self.__fixation_left.timestamp
            self.__fixation_left.elapsed_time = elapsed_time
            self.__fixation_left.duration = self.__fixation_left.duration + elapsed_time if is_fixated else 0
        elif element == "right_eye":
            previous_t = min(self.__one_euro_filter.right_eye_x.previous_time, self.__one_euro_filter.right_eye_y.previous_time)
            
            # filter for x
            filtered_x = self.__one_euro_filter.right_eye_x(t, x)
            # filter for y
            filtered_y = self.__one_euro_filter.right_eye_y(t, y)
            LOGGER.debug(f"{element}: {previous_t}, {t}, ({x}, {filtered_x}),  ({y}, {filtered_y})")
            is_fixated, velocity, elapsed_time = calculate(previous_t, t, filtered_x, filtered_y)
            self.__fixation_right.x = x
            self.__fixation_right.y = y
            self.__fixation_right.filtered_x = filtered_x
            self.__fixation_right.filtered_y = filtered_y
            self.__fixation_right.velocity = velocity
            self.__fixation_right.is_fixated = is_fixated
            self.__fixation_right.timestamp = t if not is_fixated else self.__fixation_right.timestamp
            self.__fixation_right.elapsed_time = elapsed_time
            self.__fixation_right.duration = self.__fixation_right.duration + elapsed_time if is_fixated else 0
        else:
            raise ValueError(f"Unknown element: {element}")

    def _collect_gaze_data(self, gaze_data):
        timestamp = eta_utils.get_timestamp()
        LOGGER.debug(f"gaze: {timestamp}")
        if self.fixation:
            # left eye
            self._update_fixation_data(
                    t=timestamp,
                    x=gaze_data.get("left_gaze_point_on_display_area")[0],
                    y=gaze_data.get("left_gaze_point_on_display_area")[1],
                    element="left_eye"
                )
            
            # right eye
            self._update_fixation_data(
                    t=timestamp,
                    x=gaze_data.get("right_gaze_point_on_display_area")[0],
                    y=gaze_data.get("right_gaze_point_on_display_area")[1],
                    element="right_eye"
                )
        data = {
            "timestamp": timestamp,
            "device_time_stamp": gaze_data.get("device_time_stamp"),
            "left_eye": {
                "gaze_point": gaze_data.get("left_gaze_point_on_display_area"),
                "pupil_diameter": gaze_data.get("left_pupil_diameter"),
                "fixated": self.__fixation_left.is_fixated,
                "velocity": self.__fixation_left.velocity,
                "filtered_gaze_point": [self.__fixation_left.filtered_x, self.__fixation_left.filtered_y],
                "fixation_timestamp": self.__fixation_left.timestamp,
                "fixation_elapsed": self.__fixation_left.duration,
            },
            "right_eye": {
                "gaze_point": gaze_data.get("right_gaze_point_on_display_area"),
                "pupil_diameter": gaze_data.get("right_pupil_diameter"),
                "fixated": self.__fixation_right.is_fixated,
                "velocity": self.__fixation_right.velocity,
                "filtered_gaze_point": [self.__fixation_right.filtered_x, self.__fixation_right.filtered_y],
                "fixation_timestamp": self.__fixation_right.timestamp,
                "fixation_elapsed": self.__fixation_right.duration,
            }
        }
        
        stream_data = np.array([
                    data["left_eye"]["gaze_point"][0] if data["left_eye"]["gaze_point"] else 0 if self.screen_nans else np.nan,
                    data["left_eye"]["gaze_point"][1] if data["left_eye"]["gaze_point"] else 0 if self.screen_nans else np.nan,
                    data["left_eye"]["pupil_diameter"] if data["left_eye"]["pupil_diameter"] else 0 if self.screen_nans else np.nan,
                    data["left_eye"]["fixated"],
                    data["left_eye"]["velocity"],
                    data["left_eye"]["fixation_timestamp"],
                    data["left_eye"]["fixation_elapsed"],
                    data["left_eye"]["filtered_gaze_point"][0] if data["left_eye"]["filtered_gaze_point"] else 0 if self.screen_nans else np.nan,
                    data["left_eye"]["filtered_gaze_point"][1] if data["left_eye"]["filtered_gaze_point"] else 0 if self.screen_nans else np.nan,
                    data["right_eye"]["gaze_point"][0] if data["right_eye"]["gaze_point"] else 0 if self.screen_nans else np.nan,
                    data["right_eye"]["gaze_point"][1] if data["right_eye"]["gaze_point"] else 0 if self.screen_nans else np.nan,
                    data["right_eye"]["pupil_diameter"] if data["right_eye"]["pupil_diameter"] else 0 if self.screen_nans else np.nan,
                    data["right_eye"]["fixated"],
                    data["right_eye"]["velocity"],
                    data["right_eye"]["fixation_timestamp"],
                    data["right_eye"]["fixation_elapsed"],
                    data["right_eye"]["filtered_gaze_point"][0] if data["right_eye"]["filtered_gaze_point"] else 0 if self.screen_nans else np.nan,
                    data["right_eye"]["filtered_gaze_point"][1] if data["right_eye"]["filtered_gaze_point"] else 0 if self.screen_nans else np.nan,
                    self.screen_width,
                    self.screen_height,
                    data["timestamp"],
                    lsl.local_clock()
                ], dtype=np.float64)
        if self.push_stream:
            self.lsl_gaze_outlet.push_sample(stream_data)
        if self.save_data: self.gaze_data.append(data)
        def multiply_tuples(t1, t2=(self.screen_width, self.screen_height)):
            return tuple(x*y for x,y in zip(t1, t2))
        if self.verbose:
            print(f'L: {multiply_tuples(data["left_eye"]["gaze_point"])}, R: {multiply_tuples(data["right_eye"]["gaze_point"])}')
            print(f'L: {multiply_tuples(data["left_eye"]["filtered_gaze_point"])}, R: {multiply_tuples(data["right_eye"]["filtered_gaze_point"])}')
            print(f'L: ({data.get("left_eye").get("fixated")}, {data.get("left_eye").get("velocity")}, {data.get("left_eye").get("fixation_timestamp")}, {data.get("left_eye").get("fixation_elapsed")})')
            print(f'R: ({data.get("right_eye").get("fixated")}, {data.get("right_eye").get("velocity")}, {data.get("right_eye").get("fixation_timestamp")}, {data.get("right_eye").get("fixation_elapsed")})')
            print('\n')

    def start_tracking(self, duration: Optional[float]=None):
        """Starts tracking continuously and saves the data to a file, if save_data flag is set to True during initialization."""
        end_time = datetime.datetime.now() + datetime.timedelta(seconds=duration) if duration is not None else None
        if self.eyetracker:
            try:
                LOGGER.debug("Starting tracking...")
                self.eyetracker.subscribe_to(self.gaze_id, self._collect_gaze_data, as_dictionary=True)
                while True:
                    if end_time and datetime.datetime.now() >= end_time:
                        self.stop_tracking()
                        break
                    time.sleep(1)
            except KeyboardInterrupt:
                self.stop_tracking()
            finally:
                if self.save_data:
                    if not os.path.exists(__datapath__):
                        os.makedirs(__datapath__)
                    file = os.path.join(__datapath__, f"gaze_data_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                    with open(file, "w") as f:
                        json.dump(
                            {
                                "screen_size": (self.screen_width, self.screen_height),
                                "data": self.gaze_data
                            }, f, indent=4)
                    LOGGER.debug(f"Gaze Data saved: {file}!")
        else:
            LOGGER.debug("No eye tracker found!")

    def stop_tracking(self):
        try:
            if self.eyetracker:
                LOGGER.debug("Stopping tracking...")
                self.eyetracker.unsubscribe_from(self.gaze_id, self._collect_gaze_data)
            else:
                LOGGER.debug("No eye tracker found!")
        except Exception as e:
            LOGGER.debug(f"Error stopping tracking: {e}")


@click.command(name="track")
@click.option("--push_stream", is_flag=True, help="Push the data to LSL stream.")
@click.option("--data_rate", default=600, type=int, help="The rate of the data stream.")
@click.option("--use_mock", is_flag=True, help="Use this to start the mock service")
@click.option("--fixation", is_flag=True, help="Use this to add fixations duration to the data stream")
@click.option("--velocity", type=float, default=1.5, help="The velocity threshold for fixation")
@click.option("--dont_screen_nans", is_flag=True, help="Use this to avoid correcting for NaNs")
@click.option("--save_data", is_flag=True, help="Save the data to a file")
@click.option("--verbose", is_flag=True, help="Use this to display LOGGER.debug statements")
@click.option("--duration", type=float, help="The duration for which to track the data")
def main(push_stream, data_rate, use_mock, fixation, velocity, dont_screen_nans, save_data, verbose, duration):
    LOGGER.debug(f"Arguments: {locals()}")
    tracker = Tracker(
        data_rate=data_rate,
        use_mock=use_mock,
        fixation=fixation,
        velocity_threshold=velocity,
        screen_nans=not dont_screen_nans,
        verbose=verbose,
        push_stream=push_stream,
        save_data=save_data
    )
    if duration:
        LOGGER.debug(f"Tracking for {duration} seconds...")
        tracker.start_tracking(duration=duration)
    else:
        tracker.start_tracking()


if __name__ == '__main__':
    main()