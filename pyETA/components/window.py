import PyQt6.QtWidgets as qtw
import PyQt6.QtCore as qtc
import PyQt6.QtGui as qtg
import sys
import random
import datetime
import json
import os
import click
from typing import Union, Optional
from pyETA import __datapath__, LOGGER
from pyETA.components.track import Tracker
import pyETA.components.utils as eta_utils


# TrackerThread class
class TrackerThread(qtc.QThread):
    finished_signal = qtc.pyqtSignal(str)
    error_signal = qtc.pyqtSignal(str)

    def __init__(self, tracker_params):
        super().__init__()
        self.tracker_params = tracker_params
        self.tracker = None
        self.running = False

    def run(self):
        try:
            self.running = True
            LOGGER.info("Starting tracker thread...")
            self.tracker = Tracker(**self.tracker_params)
            self.tracker.start_tracking(duration=self.tracker_params['duration'])
            if self.running:
                self.finished_signal.emit("Tracking completed successfully")
        except Exception as e:
            error_msg = f"Tracker error: {str(e)}"
            LOGGER.error(error_msg)
            self.error_signal.emit(error_msg)
        finally:
            self.running = False

    def stop(self):
        self.running = False
        if self.tracker:
            self.tracker.stop_tracking()
        self.quit()
        self.wait()

# ValidationWindow class (unchanged)
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
        self.showFullScreen()
        self.screen_width, self.screen_height = self.size().width(), self.size().height()
        print("Screen width:", self.screen_width)
        print("Screen height:", self.screen_height)
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
            qtc.QTimer.singleShot(self.stay_duration, self.close)

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
        if event.key() == qtc.Qt.Key.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
            self.screen_width, self.screen_height = self.size().width(), self.size().height()
        elif event.key() == qtc.Qt.Key.Key_Escape or event.key() == qtc.Qt.Key.Key_Q:
            LOGGER.info("Validation Window closed manually!")
            self.close()
        else:
            super().keyPressEvent(event)
    
    def collect_data(self):
        circle_center = qtc.QPoint(self.circle_size // 2, self.circle_size // 2)

        window_pos = self.circle.mapTo(self, circle_center)
        circle_screen_pos = self.mapToGlobal(window_pos)
        x = circle_screen_pos.x()
        data_point = {
            "timestamp": eta_utils.get_timestamp(),
            "grid_position": self.current_position,
            "screen_position": (x, circle_screen_pos.y())
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

def run_validation_window(screen: Optional[qtg.QScreen]=None):
    validation_window = ValidationWindow()

    if screen:
        geometry = screen.geometry()
        validation_window.setGeometry(geometry)
        LOGGER.info(f"Validation Window created on screen resolution: {geometry.width()}x{geometry.height()}")

    return validation_window

@click.command(name="window")
@click.option("--use_mock", is_flag=True, help="Use mockup tracker")
@click.option("--verbose", is_flag=True, help="Enable verbose logging")
def main(use_mock, verbose):
    app = qtw.QApplication(sys.argv)
    validation_window = run_validation_window()
    tracker_params = {
        'use_mock': use_mock,
        'fixation': False,
        'verbose': verbose,
        'push_stream': False,
        'save_data': True,
        'duration': (9*(2000+1000))/1000 + (2000*3)/1000 + 2000/1000
    }

    # Start the tracker thread
    tracker_thread = TrackerThread(tracker_params)
    tracker_thread.finished_signal.connect(lambda msg: LOGGER.info(msg))
    tracker_thread.error_signal.connect(lambda msg: LOGGER.error(msg))
    tracker_thread.start()
    validation_window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()