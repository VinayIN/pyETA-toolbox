import PyQt6.QtWidgets as qtw
import PyQt6.QtCore as qtc
import PyQt6.QtGui as qtg
import sys
import asyncio

class ValidationWindow(qtw.QMainWindow):
    def __init__(self):
        super().__init__()
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

        self.show()

    def keyPressEvent(self, event: qtg.QKeyEvent):
        if event.key() == qtc.Qt.Key.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        elif event.key() == qtc.Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)


async def run_validation_window():
    app = qtw.QApplication(sys.argv)
    validation_window = ValidationWindow()
    app.exec()

if __name__ == '__main__':
    sys.exit(run_validation_window())
