import sys
import time
import threading
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMainWindow, QPushButton, QVBoxLayout, QWidget, QLabel


class Worker(QThread):
    # Signal to emit data from the thread
    data_updated = pyqtSignal(str)

    def __init__(self, thread_id):
        super().__init__()
        self.thread_id = thread_id
        self._is_running = False

    def run(self):
        self._is_running = True
        while self._is_running:
            time.sleep(1)
            self.data_updated.emit(f"Thread {self.thread_id} is running")

    def stop(self):
        self._is_running = False
        self.wait()
        self.quit()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("QThread Start/Stop Example")
        self.setGeometry(100, 100, 300, 200)

        # Create two worker threads
        self.thread1 = Worker(1)
        self.thread2 = Worker(2)

        self.total_threads_count_label = QLabel("0")

        # Connect signals to slots
        self.thread1.data_updated.connect(self.update_status)
        self.thread2.data_updated.connect(self.update_status)

        # Create buttons to control the threads
        self.start_button1 = QPushButton("Start Thread 1")
        self.start_button1.clicked.connect(self.start_thread1)

        self.stop_button1 = QPushButton("Stop Thread 1")
        self.stop_button1.clicked.connect(self.stop_thread1)

        self.start_button2 = QPushButton("Start Thread 2")
        self.start_button2.clicked.connect(self.start_thread2)

        self.stop_button2 = QPushButton("Stop Thread 2")
        self.stop_button2.clicked.connect(self.stop_thread2)

        self.status = QLabel("-")

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.total_threads_count_label)
        layout.setSpacing(10)
        layout.addWidget(self.start_button1)
        layout.addWidget(self.stop_button1)
        layout.addSpacing(10)
        layout.addWidget(self.start_button2)
        layout.addWidget(self.stop_button2)
        layout.addSpacing(10)
        layout.addWidget(self.status)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def total_threads_count(self):
        count = threading.active_count()
        self.total_threads_count_label.setText(str(count))

    def start_thread1(self):
        if not self.thread1.isRunning():
            self.thread1.start()
        self.total_threads_count()

    def stop_thread1(self):
        if self.thread1.isRunning():
            self.thread1.stop()
        self.total_threads_count()

    def start_thread2(self):
        if not self.thread2.isRunning():
            self.thread2.start()
        self.total_threads_count()

    def stop_thread2(self):
        if self.thread2.isRunning():
            self.thread2.stop()
        self.total_threads_count()

    def update_status(self, message):
        self.status.setText(message)

    def closeEvent(self, event):
        # Ensure threads are stopped when the application closes
        if self.thread1.isRunning():
            self.thread1.stop()
        if self.thread2.isRunning():
            self.thread2.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())