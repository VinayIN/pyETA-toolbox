import PyQt6.QtWidgets as qtw
import PyQt6.QtCore as qtc
import PyQt6.QtGui as qtg
import sys
import random
import asyncio

class ValidationWindow(qtw.QMainWindow):
    def __init__(self):
        super().__init__()
        self.circle_positions = [(row, col) for row in range(3) for col in range(3)]
        self.current_position = None
        self.movement_duration = 500  # milliseconds
        self.stay_duration = 1000  # milliseconds
        self.circle_size = 20
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Validation Window')
        self.setGeometry(100, 100, 600, 600)
        self.gridWidget = qtw.QWidget(self)
        self.setCentralWidget(self.gridWidget)

        layout = qtw.QGridLayout(self.gridWidget)

        for row in range(3):
            for col in range(3):
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

        qtc.QTimer.singleShot(0, self.start_sequence)

    def start_sequence(self):
        if self.circle_positions:
            self.move_to_next_position()
        else:
            print("Sequence completed!")

    def move_to_next_position(self):
        if self.current_position:
            self.circle_positions.remove(self.current_position)
        
        if not self.circle_positions:
            self.circle.hide()
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

    def on_animation_finished(self):
        qtc.QTimer.singleShot(self.stay_duration, self.start_sequence)

    def keyPressEvent(self, event: qtg.QKeyEvent):
        if event.key() == qtc.Qt.Key.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        elif event.key() == qtc.Qt.Key.Key_Escape:
            self.close()
        elif event.key() == qtc.Qt.Key.Key_Up:
            self.movement_duration = max(100, self.movement_duration - 100)
            print(f"Movement duration: {self.movement_duration}ms")
        elif event.key() == qtc.Qt.Key.Key_Down:
            self.movement_duration += 100
            print(f"Movement duration: {self.movement_duration}ms")
        elif event.key() == qtc.Qt.Key.Key_Left:
            self.stay_duration = max(100, self.stay_duration - 100)
            print(f"Stay duration: {self.stay_duration}ms")
        elif event.key() == qtc.Qt.Key.Key_Right:
            self.stay_duration += 100
            print(f"Stay duration: {self.stay_duration}ms")
        else:
            super().keyPressEvent(event)

def run_validation_window():
    app = qtw.QApplication(sys.argv)
    validation_window = ValidationWindow()
    sys.exit(app.exec())

if __name__ == '__main__':
    run_validation_window()