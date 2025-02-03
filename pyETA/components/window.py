import PyQt6.QtWidgets as qtw
import PyQt6.QtCore as qtc
import PyQt6.QtGui as qtg
import sys
import random
import datetime
import json
import threading
import os
import click
from typing import Union, Optional
from pyETA import __datapath__, LOGGER
import pyETA.components.utils as eta_utils
from pyETA.components.reader import TrackerThread

class ValidationWindow(qtw.QMainWindow):
    def __init__(self):
        super().__init__()
        self.total_grids = (3,3)
        self.circle_positions = [(row, col) for row in range(self.total_grids[0]) for col in range(self.total_grids[1])]
        self.current_position = None
        self.movement_duration = 1000
        self.stay_duration = 3000
        self.circle_size = 20
        self.collected_data = []
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Validation Window')
        #self.showFullScreen()
        self.screen_width, self.screen_height = self.size().width(), self.size().height()
        LOGGER.info(f"Screen width x height: {self.screen_width} x {self.screen_height}")
        self.gridWidget = qtw.QWidget(self)
        self.setCentralWidget(self.gridWidget)

        layout = qtw.QGridLayout(self.gridWidget)

        for row in range(self.total_grids[0]):
            for col in range(self.total_grids[1]):
                label = qtw.QLabel('+', self)
                label.setAlignment(qtc.Qt.AlignmentFlag.AlignCenter)
                layout.addWidget(label, row, col)

        self.circle = qtw.QLabel(self)
        self.circle.setStyleSheet("background-color: blue; border-radius: 10px;")
        self.circle.setFixedSize(self.circle_size, self.circle_size)
        self.circle.hide()

        self.show()
        self.animation = qtc.QPropertyAnimation(self.circle, b"pos")
        self.animation.finished.connect(self.on_animation_finished)
        qtc.QTimer.singleShot(self.stay_duration*3, self.start_sequence)

    def start_sequence(self):
        if self.circle_positions:
            self.move_to_next_position()
        else:
            self.circle.hide()
            self.process_data()
            LOGGER.info("Sequence completed!")
            qtc.QTimer.singleShot(self.stay_duration*3, self.close)

    def move_to_next_position(self):
        if not self.circle_positions:
            return

        next_position = random.choice(self.circle_positions)
        self.current_position = next_position
        target_widget = self.gridWidget.layout().itemAtPosition(*next_position).widget()
        target_pos = target_widget.mapTo(self, qtc.QPoint(target_widget.width() // 2 - self.circle_size // 2,
                                                          target_widget.height() // 2 - self.circle_size // 2))

        self.current_target_pos = target_pos
        self.animation.setStartValue(self.circle.pos())
        self.animation.setEndValue(target_pos)
        self.animation.setDuration(self.movement_duration)
        
        self.circle.show()
        self.animation.start()

        self.circle_positions.remove(self.current_position)

    def on_animation_finished(self):
        self.collect_data()
        qtc.QTimer.singleShot(self.stay_duration, self.start_sequence)

    def keyPressEvent(self, event: qtg.QKeyEvent):
        if event.key() == qtc.Qt.Key.Key_F11 or event.key() == qtc.Qt.Key.Key_F:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
            self.screen_width, self.screen_height = self.size().width(), self.size().height()
            LOGGER.info(f"Screen width x height: {self.screen_width} x {self.screen_height}")
        elif event.key() == qtc.Qt.Key.Key_Escape or event.key() == qtc.Qt.Key.Key_Q:
            LOGGER.info("Validation Window closed manually!")
            self.close()
        else:
            super().keyPressEvent(event)
    
    def collect_data(self):
        circle_center = qtc.QPoint(self.circle_size // 2, self.circle_size // 2)

        window_pos = self.circle.mapTo(self, circle_center)
        relative_pos = eta_utils.get_relative_from_actual((window_pos.x(), window_pos.y()), self.width(), self.height())
        recalibrated_pos = eta_utils.get_actual_from_relative(relative_pos, self.screen_width, self.screen_height)
        data_point = {
            "timestamp": eta_utils.get_timestamp(),
            "grid_position": self.current_position,
            "screen_position": recalibrated_pos
        }
        LOGGER.debug(f"Grid: {data_point.get('grid_position')}, Target: {self.current_target_pos}, Screen   : {data_point.get('screen_position')}")
        self.collected_data.append(data_point)

    def process_data(self):
        if not os.path.exists(__datapath__):
            os.makedirs(__datapath__)
        file = os.path.join(__datapath__, f"system_{eta_utils.get_system_info()}.json")
        with open(file, "w") as f:
            json.dump(
                {
                    "screen_size": (self.screen_width, self.screen_height),
                    "stay_duration": self.stay_duration,
                    "data": self.collected_data
                }, f, indent=4)
            LOGGER.info(f"Validation Data saved: {file}!")

def run_validation_window(screen_index: Optional[int] = 0):
    validation_window = ValidationWindow()
    screens = qtw.QApplication.screens()

    if screen_index < len(screens):
        screen = screens[screen_index]
        geometry = screen.availableGeometry()
        validation_window.setGeometry(geometry)
        validation_window.move(geometry.topLeft())
        LOGGER.info(f"Validation Window created on screen {screen_index + 1} with resolution: {geometry.width()}x{geometry.height()}")
    else:
        raise ValueError(f"Invalid screen index: {screen_index}")
    return validation_window

@click.command(name="window")
@click.option("--use_mock", is_flag=True, help="Use mockup tracker")
@click.option("--screen_index", default=0, help="Screen index to display the validation window")
@click.option("--verbose", is_flag=True, help="Enable verbose logging")
def main(use_mock, screen_index, verbose):
    app = qtw.QApplication(sys.argv)
    validation_window = run_validation_window(screen_index=screen_index)
    tracker_params = {
        'use_mock': use_mock,
        'fixation': False,
        'verbose': verbose,
        'push_stream': False,
        'save_data': True,
        'screen_index': screen_index,
        'duration': (9*(3000+1000))/1000 + (2000*3)/1000 + 2000/1000
    }


    tracker_thread = TrackerThread()
    tracker_thread.set_variables(tracker_params)
    tracker_thread.finished_signal.connect(lambda msg: LOGGER.info(msg))
    tracker_thread.error_signal.connect(lambda msg: LOGGER.error(msg))
    tracker_thread.start()
    validation_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()