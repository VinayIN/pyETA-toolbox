#!/usr/bin/env python
import sys
import time
import random
from threading import Thread
from mne_lsl import lsl
import argparse
import pynput
import numpy as np
import json
import datetime
import PyQt6.QtWidgets as qtw
from typing import Optional, Callable, Tuple
from abc import ABC, abstractmethod

class Service(ABC):
    def __init__(self, fix_screen: Optional[Tuple], save_data: bool, data_rate: int, verbose: bool):
        pass
    
    def save_data(self):
        pass
        

try:
    import tobii_research as tr
    tobii_module = True
except ModuleNotFoundError:
    print("Tobii eye tracker streaming not possible. tobii-research module not installed.")
    tobii_module = False


def get_current_screen_size():
    app = qtw.QApplication(sys.argv)
    screen = app.primaryScreen()
    size = screen.size()
    width, height = size.width(), size.height()
    return width, height

def get_timestamp():
    return datetime.datetime.now().isoformat()



class Tobii(Service):
    def __init__(self, fix_screen: Optional[Tuple]=None, save_data: bool = False, data_rate=600, verbose: bool = False):
        """Save_data flag saves the data to a file if set to True."""
        if fix_screen is None:
            fix_screen = get_current_screen_size()
        if 0 in fix_screen:
            raise ValueError("Screen size cannot be zero (0)!")
        self.verbose = verbose
        self.save_data = save_data
        self.screen_width, self.screen_heigth = fix_screen
        print(f"Screen Resolution: {self.screen_width}x{self.screen_heigth}")
        eyetrackers = tr.find_all_eyetrackers()
        self.eyetracker = eyetrackers[0] if eyetrackers else None
        if self.eyetracker:
            print(f"Address: {self.eyetracker.address}")
            print(f"Model: {self.eyetracker.model}")
            print(f"Serial number: {self.eyetracker.serial_number}")
            print("\n\nPress Ctrl+C to stop tracking...")
        else:
            raise ValueError("No Eye Tracker found")

class Mock(Service, Thread):
    def __init__(self, fix_screen: Optional[Tuple]=None, data_rate=600, nan_probability=0):
        # Make sure this thread is a daemon
        Thread.__init__(self, name="Mock", daemon=True)
        if fix_screen is None:
            fix_screen = get_current_screen_size()
        if 0 in fix_screen:
            raise ValueError("Screen size cannot be zero (0)!")
        self.known_ids = ["uid_gaze_data", "uid_eyeopenness_data"]
        self.data_rate = data_rate
        self.outlet = None
        self.listener = None
        self.serial_number = "ZA03046BIN2024"
        self.callbacks = dict()
        self.screen_width, self.screen_heigth = fix_screen
        self.curr_x = 0.0
        self.curr_y = 0.0
        self.nan_probability = nan_probability
        self.should_stop = False

    def subscribe_to(self, id, callback, as_dictionary=True):
        if id not in self.known_ids:
            raise ValueError("Unknown data type")

        if callback is None:
            raise ValueError("Callback cannot be None")

        self.callbacks[id] = callback

    def unsubscribe_from(self, id, callback):
        if id in self.callbacks:
            del self.callbacks[id]

        # if no more callbacks than stop
        if not self.callbacks:
            self.stop()

    def on_move(self, x, y):
        # correct for the mouse acceleration and out of screen values
        corr_x = x if x >= 0 else 0
        corr_x = corr_x if corr_x < self.screen_width else self.screen_width-1
        corr_y = y if y >= 0 else 0
        corr_y = corr_y if corr_y < self.screen_heigth else self.screen_heigth-1

        # convert to ratio
        self.curr_x = corr_x/self.screen_width
        self.curr_y = corr_y/self.screen_heigth

    def run(self):
        self.listener = pynput.mouse.Listener(on_move=self.on_move)
        with self.listener as lis:
            while not self.should_stop:
                time.sleep(1/self.data_rate)
                x = self.curr_x
                y = self.curr_y
                if random.uniform(0, 1) < self.nan_probability:
                    x = float('nan')
                    y = float('nan')

                if tr.EYETRACKER_GAZE_DATA in self.callbacks:
                    self.callbacks[tr.EYETRACKER_GAZE_DATA](
                        {
                            "device_time_stamp": get_timestamp(),
                            "system_time_stamp": lsl.local_clock(),
                            'left_gaze_point_on_display_area': [x, y],
                            'left_gaze_point_validity': random.uniform(0, 1) > 0.5,
                            'right_gaze_point_on_display_area': [x, y],
                            'right_gaze_point_validity': random.uniform(0, 1) > 0.5,
                            'left_pupil_diameter': 8.0 + 4 * random.uniform(-1, 1),
                            'left_pupil_validity': random.uniform(0, 1) > 0.5,
                            'right_pupil_diameter': 8.0 + 4 * random.uniform(-1, 1),
                            'right_pupil_validity': random.uniform(0, 1) > 0.5
                        })

                if tr.EYETRACKER_EYE_OPENNESS_DATA in self.callbacks:
                    self.callbacks[tr.EYETRACKER_EYE_OPENNESS_DATA](
                        {
                            "device_time_stamp": get_timestamp(),
                            "system_time_stamp": lsl.local_clock(),
                            "left_eye_validity": random.uniform(0, 1) > 0.5,
                            "left_eye_openness_value": 12.0 + 4 * random.uniform(-1, 1),
                            "right_eye_validity": random.uniform(0, 1) > 0.5,
                            "right_eye_openness_value":  12.0 + 4 * random.uniform(-1, 1)
                        })
            lis.join()

    def stop(self):
        self.should_stop = False



class Gaze:
    def __init__(self, screen_nans=True):
        self.lsl_gaze_outlet = None
        self.lsl_eye_openness_outlet = None
        self.screen_nans = screen_nans

    def manage_stream(self, service):
        try:
            if tr.CAPABILITY_HAS_GAZE_DATA in service.device_capabilities:
                service.subscribe_to(tr.EYETRACKER_GAZE_DATA, self.gaze_data_callback, as_dictionary=True)
                info = lsl.StreamInfo(
                    name='tobii_gaze',
                    stype='Gaze',
                    n_channels=14,
                    sfreq=service.data_rate,
                    dtype='double64',
                    source_id=service.serial_number)

                info.desc().append_child_value("manufacturer", "Tobii")
                info.desc().append_child_value("tracker", "Tobii Pro Spectrum")
                chns = info.desc().append_child("channels")
                #  1 gaze_pixel_left_x
                ch = chns.append_child("channel")
                ch.append_child_value("label", "gpl_x")
                ch.append_child_value("unit", "px")
                ch.append_child_value("type", "gaze")
                #  2 gaze_pixel_left_y
                ch = chns.append_child("channel")
                ch.append_child_value("label", "gpl_y")
                ch.append_child_value("unit", "px")
                ch.append_child_value("type", "gaze")
                #  3 gaze_pixel_right_x
                ch = chns.append_child("channel")
                ch.append_child_value("label", "gpr_x")
                ch.append_child_value("unit", "px")
                ch.append_child_value("type", "gaze")
                #  4 gaze_pixel_right_y
                ch = chns.append_child("channel")
                ch.append_child_value("label", "gpr_y")
                ch.append_child_value("unit", "px")
                ch.append_child_value("type", "gaze")
                #  5 gaze_raw_left_x
                ch = chns.append_child("channel")
                ch.append_child_value("label", "gl_x")
                ch.append_child_value("unit", "adcs")
                ch.append_child_value("type", "gaze")
                #  6 gaze_raw_left_y
                ch = chns.append_child("channel")
                ch.append_child_value("label", "gl_y")
                ch.append_child_value("unit", "adcs")
                ch.append_child_value("type", "gaze")
                #  7 gaze_raw_right_x
                ch = chns.append_child("channel")
                ch.append_child_value("label", "gr_x")
                ch.append_child_value("unit", "adcs")
                ch.append_child_value("type", "gaze")
                #  8 gaze_raw_right_y
                ch = chns.append_child("channel")
                ch.append_child_value("label", "gr_y")
                ch.append_child_value("unit", "adcs")
                ch.append_child_value("type", "gaze")
                #  9 gaze left validity
                ch = chns.append_child("channel")
                ch.append_child_value("label", "glval")
                ch.append_child_value("unit", "bool")
                ch.append_child_value("type", "gaze")
                #  10 gaze right validity
                ch = chns.append_child("channel")
                ch.append_child_value("label", "grval")
                ch.append_child_value("unit", "bool")
                ch.append_child_value("type", "gaze")
                #  11 pupil left diameter
                ch = chns.append_child("channel")
                ch.append_child_value("label", "pld")
                ch.append_child_value("unit", "mm")
                ch.append_child_value("type", "gaze")
                #  12 pupil right diameter
                ch = chns.append_child("channel")
                ch.append_child_value("label", "prd")
                ch.append_child_value("unit", "mm")
                ch.append_child_value("type", "gaze")
                #  13 pupil left diameter validity
                ch = chns.append_child("channel")
                ch.append_child_value("label", "pldval")
                ch.append_child_value("unit", "bool")
                ch.append_child_value("type", "gaze")
                #  14 pupil right diameter validity
                ch = chns.append_child("channel")
                ch.append_child_value("label", "prdval")
                ch.append_child_value("unit", "bool")
                ch.append_child_value("type", "gaze")
                #  15 device timestamp
                ch = chns.append_child("channel")
                ch.append_child_value("label", "dts")
                ch.append_child_value("unit", "us")
                ch.append_child_value("type", "gaze")
                #  16 system timestamp
                ch = chns.append_child("channel")
                ch.append_child_value("label", "sts")
                ch.append_child_value("unit", "us")
                ch.append_child_value("type", "gaze")

                self.lsl_gaze_outlet = lsl.StreamOutlet(info)

            if tr.CAPABILITY_HAS_EYE_OPENNESS_DATA in service.device_capabilities:
                service.subscribe_to(tr.EYETRACKER_EYE_OPENNESS_DATA, self.eye_openness_callback, as_dictionary=True)
                info = lsl.StreamInfo(
                    name='tobii_eye_openness',
                    type='GazeEyeOpenness',
                    n_channels=6,
                    sfreq=self.data_rate,
                    dtype='double64',
                    source_id=service.serial_number)

                info.desc().append_child_value("manufacturer", "Tobii")
                info.desc().append_child_value("tracker", "Tobii Pro Spectrum")
                chns = info.desc().append_child("channels")

                #  1 eye openness diameter left
                ch = chns.append_child("channel")
                ch.append_child_value("label", "eold")
                ch.append_child_value("unit", "mm")
                ch.append_child_value("type", "gaze")
                #  2 eye openness left validity
                ch = chns.append_child("channel")
                ch.append_child_value("label", "eolval")
                ch.append_child_value("unit", "bool")
                ch.append_child_value("type", "gaze")
                #  3 eye openness diameter right
                ch = chns.append_child("channel")
                ch.append_child_value("label", "eord")
                ch.append_child_value("unit", "mm")
                ch.append_child_value("type", "gaze")
                #  4 eye openness right validity
                ch = chns.append_child("channel")
                ch.append_child_value("label", "eorval")
                ch.append_child_value("unit", "bool")
                ch.append_child_value("type", "gaze")
                #  5 eye openness device timestamp
                ch = chns.append_child("channel")
                ch.append_child_value("label", "dts")
                ch.append_child_value("unit", "us")
                ch.append_child_value("type", "gaze")
                #  6 eye openness
                ch = chns.append_child("channel")
                ch.append_child_value("label", "sts")
                ch.append_child_value("unit", "us")
                ch.append_child_value("type", "gaze")

                self.lsl_eye_openness_outlet = lsl.StreamOutlet(info)

        except KeyboardInterrupt:
            if tr.CAPABILITY_HAS_GAZE_DATA in service.device_capabilities:
                service.unsubscribe_from(tr.EYETRACKER_GAZE_DATA, self.gaze_data_callback)

            if tr.CAPABILITY_HAS_EYE_OPENNESS_DATA in service.device_capabilities:
                service.unsubscribe_from(tr.EYETRACKER_EYE_OPENNESS_DATA, self.eye_openness_callback)

    def eye_openness_callback(self, eye_openness_data):
        eod_dt = eye_openness_data["device_time_stamp"]
        eod_st = eye_openness_data["system_time_stamp"]
        eod_lev = eye_openness_data["left_eye_validity"]
        eod_leo = eye_openness_data["left_eye_openness_value"]
        eod_rev = eye_openness_data["right_eye_validity"]
        eod_reo = eye_openness_data["right_eye_openness_value"]
        
        if self.lsl_eye_openness_outlet:
            self.lsl_eye_openness_outlet.push_sample((eod_leo, eod_lev, eod_reo, eod_rev, eod_dt, eod_st))

        if self.verbose: print("L: (%g, %r), R: (%g, %r), TS: (%g, %g)" %
              (eod_leo, eod_lev, eod_reo, eod_rev, eod_dt, eod_st), '\r', end='')

    def gaze_data_callback(self, gaze_data):
        def nan_int(x):
            return x if np.isnan(x) else int(x)

        gzd_dt = gaze_data["device_time_stamp"]
        gzd_st = gaze_data["system_time_stamp"]

        gaze_l = gaze_data['left_gaze_point_on_display_area']
        gaze_lv = gaze_data['left_gaze_point_validity']
        gaze_r = gaze_data['right_gaze_point_on_display_area']
        gaze_rv = gaze_data['right_gaze_point_validity']

        gaze_pixel_l = [nan_int(gaze_l[0] * self.scr_width), nan_int(gaze_l[1] * self.scr_height)]
        gaze_pixel_r = [nan_int(gaze_r[0] * self.scr_width), nan_int(gaze_r[1] * self.scr_height)]

        pupil_l = gaze_data['left_pupil_diameter']
        pupil_lv = gaze_data['left_pupil_validity']
        pupil_r = gaze_data['right_pupil_diameter']
        pupil_rv = gaze_data['right_pupil_validity']

        if self.screen_nans:
            gaze_pixel_l = [0, 0] if np.isnan(gaze_pixel_l).any() else gaze_pixel_l
            gaze_pixel_r = [0, 0] if np.isnan(gaze_pixel_r).any() else gaze_pixel_r

        if not np.isnan(gaze_pixel_l).any():
            # bound x between 0 and screen width -1
            # bound y between 0 and screen height -1
            gaze_pixel_l[0] = 0 if gaze_pixel_l[0] < 0 else gaze_pixel_l[0]
            gaze_pixel_l[0] = pixelsX - 1 if gaze_pixel_l[0] >= pixelsX else gaze_pixel_l[0]
            gaze_pixel_l[1] = 0 if gaze_pixel_l[1] < 0 else gaze_pixel_l[1]
            gaze_pixel_l[1] = pixelsY - 1 if gaze_pixel_l[1] >= pixelsY else gaze_pixel_l[1]

        if not np.isnan(gaze_pixel_r).any():
            # bound x between 0 and screen width -1
            # bound y between 0 and screen height -1
            gaze_pixel_r[0] = 0 if gaze_pixel_r[0] < 0 else gaze_pixel_r[0]
            gaze_pixel_r[0] = pixelsX - 1 if gaze_pixel_r[0] >= pixelsX else gaze_pixel_r[0]
            gaze_pixel_r[1] = 0 if gaze_pixel_r[1] < 0 else gaze_pixel_r[1]
            gaze_pixel_r[1] = pixelsY - 1 if gaze_pixel_r[1] >= pixelsY else gaze_pixel_r[1]

        if self.lsl_gaze_outlet:
            self.lsl_gaze_outlet.push_sample((*gaze_pixel_l, *gaze_pixel_r,
                                              gaze_lv, gaze_rv,
                                              pupil_l, pupil_r,
                                              pupil_lv, pupil_rv,
                                              self.scr_width, self.scr_height,
                                              gzd_dt, gzd_st))

        if self.verbose: print("L: (%g, %g <--> %g, %g [%r]), R: (%g, %g <--> %g, %g [%r]), PD: (%g, %g) [%r, %r] TS: (%g, %g)" %
              (*gaze_l, *gaze_pixel_l, gaze_lv, *gaze_r, *gaze_pixel_r, gaze_rv, pupil_l, pupil_r, pupil_lv, pupil_rv, gzd_dt, gzd_st), '\r', end='')



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_rate", default=600, type=int,
                        help="The rate of the data stream.")
    parser.add_argument("--dont_screen_nans", action="store_true",
                        help="Use this to avoid correcting for NaNs")
    parser.add_argument("--use_mockup", action="store_true", required=False,
                        help="If no eye Tobii eye-tracker is present use mockup")
    parser.add_argument("--fix_screen_size", required=False, nargs=2, type=int, metavar=('width', 'height'), default=[1920, 1080],
                        help="Set the screen size. Doing so it will ignore the calculated values")
    parser.add_argument("--mockup_nan_probability", default=0, required=False, type=float,
                        help="The probability to get a NaN in the gaze data")
    parser.add_argument("--verbose", action="store_true",
                        help="Use this to display print statements; Flag to keep the terminal clean.")
    args = parser.parse_args()
    print(args)

    if args.use_mockup:
        print("Mockup requested.")
        mockup = Mock(
            fix_screen=args.fix_screen_size,
            data_rate=args.data_rate,
            nan_probability=args.mockup_nan_probability,
            verbose=args.verbose)
        mockup.start()
        Gaze(screen_nans=not args.dont_screen_nans).manage_stream(mockup)
    else:
        print("Tobii requested.")
        tobii = Tobii(
            save_data=False,
            data_rate=args.data_rate,
            verbose=args.verbose)
        if tobii_module:
            Gaze(screen_nans=not args.dont_screen_nans).manage_stream(tobii)