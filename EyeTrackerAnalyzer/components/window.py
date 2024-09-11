import PyQt6.QtWidgets as qtw
import PyQt6.QtCore as qtc
import PyQt6.QtGui as qtg
import sys
import random
import datetime
import json
import os
from EyeTrackerAnalyzer.components.utils import get_system_info, get_current_screen_size

class ValidationWindow(qtw.QMainWindow):
    def __init__(self):
        super().__init__()
        self.total_grids = (3,3)
        self.circle_positions = [(row, col) for row in range(self.total_grids[0]) for col in range(self.total_grids[1])]
        self.current_position = None
        self.movement_duration = 1000
        self.stay_duration = 2000
        self.circle_size = 20
        self.collected_data = []
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Validation Window')
        self.setGeometry(100, 100, 600, 600)
        self.screen_width, self.screen_height = self.size().width(), self.size().height()
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
        qtc.QTimer.singleShot(self.stay_duration, self.start_sequence)

    def start_sequence(self):
        if self.circle_positions:
            self.move_to_next_position()
        else:
            self.circle.hide()
            self.process_data()
            print("Sequence completed!")
            qtc.QTimer.singleShot(self.stay_duration, self.close)

    def move_to_next_position(self):
        if not self.circle_positions:
            return

        next_position = random.choice(self.circle_positions)
        self.current_position = next_position
        target_widget = self.gridWidget.layout().itemAtPosition(*next_position).widget()
        target_pos = target_widget.mapTo(self, qtc.QPoint(target_widget.width() // 2 - self.circle_size // 2,
                                                          target_widget.height() // 2 - self.circle_size // 2))

        self.animation.setStartValue(self.circle.pos())
        self.animation.setEndValue(target_pos)
        self.animation.setDuration(self.movement_duration)
        
        self.circle.show()
        self.animation.start()
        self.collect_data()

        self.circle_positions.remove(self.current_position)

    def on_animation_finished(self):
        qtc.QTimer.singleShot(self.stay_duration, self.start_sequence)

    def keyPressEvent(self, event: qtg.QKeyEvent):
        if event.key() == qtc.Qt.Key.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
            self.screen_width, self.screen_height = self.size().width(), self.size().height()
        elif event.key() == qtc.Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
    
    def collect_data(self):
        circle_screen_pos = self.circle.mapToGlobal(qtc.QPoint(0, 0))
        data_point = {
            "timestamp": datetime.datetime.now().isoformat(),
            "grid_position": self.current_position,
            "screen_position": (circle_screen_pos.x(), circle_screen_pos.y())
        }
        self.collected_data.append(data_point)

    def process_data(self):
        data_path = os.path.join(os.path.dirname(__package__), "data")
        if not os.path.exists(data_path):
            os.makedirs(data_path)
        with open(os.path.join(data_path, f"{get_system_info()}.json"), "w") as f:
            json.dump(
                {
                    "screen_size": (self.screen_width, self.screen_height),
                    "stay_duration": self.stay_duration,
                    "data": self.collected_data
                }, f, indent=4)
            print("Validation Data saved!")

def run_validation_window():
    app = qtw.QApplication(sys.argv)
    validation_window = ValidationWindow()
    sys.exit(app.exec())

if __name__ == '__main__':
    run_validation_window()