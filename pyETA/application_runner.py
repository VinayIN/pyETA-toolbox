import sys
import logging
import click
import numpy as np
import pandas as pd
import pyqtgraph as pg

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QComboBox, QMessageBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QSlider, QFrame, QSplitter, QFrame, QDialog, QDoubleSpinBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon
from typing import Optional

from pyETA import __version__, LOGGER
from pyETA.components.track import Tracker
from pyETA.components.window import TrackerThread

class StreamThread(QThread):
    update_gaze_signal = pyqtSignal(list, list, list)  # times, x, y
    update_fixation_signal = pyqtSignal(list, list, list)  # x_coords, y_coords, counts

    def __init__(self):
        super().__init__()
        self.running = False

    def run(self):
        self.running = True
        while self.running:
            try:
                # Simulated data for demonstration
                times = np.arange(10)
                x = np.random.random(10) * 100
                y = np.random.random(10) * 100
                fixation_counts = np.random.randint(1, 10, 10)
                self.update_gaze_signal.emit(times.tolist(), x.tolist(), y.tolist())
                self.update_fixation_signal.emit(x.tolist(), y.tolist(), fixation_counts.tolist())
                self.msleep(1000)  # Simulate 1-second data intervals
            except Exception as e:
                LOGGER.error(f"Stream error: {e}")

    def stop(self):
        self.running = False
        self.quit()
        self.wait()
class EyeTrackerAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"pyETA-{__version__}")
        self.resize(1200, 800)

        # Central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Splitter for collapsible sidebar
        splitter = QSplitter(Qt.Orientation.Horizontal, central_widget)

        # Sidebar
        self.sidebar = self.create_sidebar()
        splitter.addWidget(self.sidebar)

        # Main content area
        main_content_widget = QWidget()
        main_layout = QVBoxLayout(main_content_widget)

        # Stream Configuration and System Info
        config_info_layout = QVBoxLayout()
        stream_config_layout = self.create_stream_configuration()
        config_info_layout.addLayout(stream_config_layout)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        config_info_layout.addWidget(line)
        main_layout.addLayout(config_info_layout)

        # Tabs
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        self.setup_tabs()

        splitter.addWidget(main_content_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)

        # Finalize layout
        layout = QVBoxLayout(central_widget)
        layout.addWidget(splitter)

        # Threads
        self.stream_thread = None
        self.tracker_thread = None

        self.setStyleSheet("""
            QPushButton:hover {
                border: 1px solid;
                border-color: black;
                border-radius: 5px;
                background-color: #2ECC71; 
            }
        """)    

    def create_sidebar(self):
        frame = QFrame()
        layout = QVBoxLayout(frame)

        title = QLabel("<h1>Toolbox - Eye Tracker Analyzer</h1>")
        title.setStyleSheet("color: gray; margin-bottom: 10px;")
        layout.addWidget(title)

        faculty_info = QLabel(
            """<h3 style='color: #555;'>Faculty 1</h3>
            <a href='https://www.b-tu.de/en/fg-neuroadaptive-hci/' style='text-decoration: none;' target='_blank'>
                <strong> Neuroadaptive Human-Computer Interaction</strong><br>
                Brandenburg University of Technology (Cottbus-Senftenberg)
            </a>"""
        )
        faculty_info.setStyleSheet("margin-bottom: 20px;")
        layout.addWidget(faculty_info)

        source_code_link = QLabel(
            """<h3 style='color: #555;'>Source code</h3>
            <a href='https://github.com/VinayIN/EyeTrackerAnalyzer.git' style='text-decoration: none;' target='_blank'>
                https://github.com/VinayIN/EyeTrackerAnalyzer.git
            </a>"""
        )

        markdown_text = QLabel(
            f"""<p>pyETA, Version: <code>{__version__}</code></p>
            <p>This interface allows you to validate the eye tracker accuracy along with the following:</p>
            <ul>
                <li>View gaze points</li>
                <li>View fixation points</li>
                <li>View eye tracker accuracy</li>
                <ul><li>Comparing the gaze data with validation grid locations.</li></ul>
            </ul>"""
        )
        layout.addWidget(markdown_text)
        layout.addWidget(source_code_link)
        self.system_info_card = self.create_system_info_card()
        layout.addWidget(self.system_info_card)
        return frame

    def create_system_info_card(self):
        card = QFrame()
        card.setFrameShape(QFrame.Shape.Box)
        layout = QVBoxLayout(card)
        layout.setSpacing(10)

        self.system_info_labels = {
            "status": QLabel(),
            "pid": QLabel(),
            "runtime": QLabel(),
            "memory": QLabel(),
            "storage": QLabel(),
            "cpu": QLabel(),
        }

        for label_name, label in self.system_info_labels.items():
            layout.addWidget(label)

        self.update_system_info("Not Running", "None", 0, 0.0, 0.0, 0.0)
        return card

    def update_system_info(self, status, pid, runtime, memory, storage, cpu):
        self.system_info_labels["status"].setText(f"<strong>Status:</strong> {status}")
        self.system_info_labels["pid"].setText(f"<strong>PID:</strong> {pid}")
        self.system_info_labels["runtime"].setText(f"<strong>Runtime:</strong> {runtime}s")
        self.system_info_labels["memory"].setText(f"<strong>Memory:</strong> {memory:.1f} MB")
        self.system_info_labels["storage"].setText(f"<strong>Storage avail:</strong> {storage} GB")
        self.system_info_labels["cpu"].setText(f"<strong>CPU:</strong> {cpu:.1f}%")

    def create_stream_configuration(self):
        # Main Horizontal Layout
        main_layout = QHBoxLayout()

        layout_first = QVBoxLayout()

        # Stream Type
        stream_type_layout = QHBoxLayout()
        stream_type_label = QLabel("Stream Type:")
        self.stream_type_combo = QComboBox()
        self.stream_type_combo.addItems(["Eye-Tracker", "Mock"])
        stream_type_layout.addWidget(stream_type_label)
        stream_type_layout.addWidget(self.stream_type_combo)
        layout_first.addLayout(stream_type_layout)

        # Data Rate
        data_rate_layout = QHBoxLayout()
        data_rate_label = QLabel("Data Rate (Hz):")
        self.data_rate_slider = QSlider(Qt.Orientation.Horizontal)
        self.data_rate_slider.setMinimum(0)
        self.data_rate_slider.setMaximum(800)
        self.data_rate_slider.setValue(600)
        self.data_rate_label = QLabel("600 Hz")
        self.data_rate_slider.valueChanged.connect(lambda value: self.data_rate_label.setText(f"{value} Hz"))
        data_rate_layout.addWidget(data_rate_label)
        data_rate_layout.addWidget(self.data_rate_slider)
        data_rate_layout.addWidget(self.data_rate_label)
        layout_first.addLayout(data_rate_layout)

        # Velocity Threshold
        velocity_threshold_layout = QHBoxLayout()
        velocity_threshold_label = QLabel("Velocity Threshold:")
        self.velocity_threshold_spinbox = QDoubleSpinBox()
        self.velocity_threshold_spinbox.setRange(0.0, 5.0)
        self.velocity_threshold_spinbox.setValue(1.5)
        self.velocity_threshold_spinbox.setSingleStep(0.1)
        self.velocity_threshold_spinbox.valueChanged.connect(lambda value: self.velocity_threshold_label.setText(f"{value:.1f}"))
        self.velocity_threshold_label = QLabel("1.5")
        velocity_threshold_layout.addWidget(velocity_threshold_label)
        velocity_threshold_layout.addWidget(self.velocity_threshold_spinbox)
        velocity_threshold_layout.addWidget(self.velocity_threshold_label)
        layout_first.addLayout(velocity_threshold_layout)

        main_layout.addLayout(layout_first)

        layout_second = QVBoxLayout()

        # Fixation Checkbox
        self.fixation_check = QCheckBox("Enable Fixation")
        self.fixation_check.setChecked(True)
        layout_second.addWidget(self.fixation_check)

        # Push to Stream Checkbox
        self.push_stream_check = QCheckBox("Push to Stream")
        self.push_stream_check.setChecked(True)
        layout_second.addWidget(self.push_stream_check)

        # Verbose Checkbox
        self.verbose_check = QCheckBox("Verbose Mode")
        layout_second.addWidget(self.verbose_check)

        # Don't Screen NaNs Checkbox
        self.dont_screen_nans_check = QCheckBox("Don't Screen NaNs (Default: 0)")
        layout_second.addWidget(self.dont_screen_nans_check)

        # Add Right Layout to Main Layout
        main_layout.addLayout(layout_second)

        # Stream Control Buttons (Below Both VBoxes)
        control_layout = QVBoxLayout()
        start_stop_layout = QHBoxLayout()
        self.start_stream_btn = QPushButton("Start Stream")
        self.stop_stream_btn = QPushButton("Stop Stream")
        self.start_stream_btn.clicked.connect(self.start_stream)
        self.stop_stream_btn.clicked.connect(self.stop_stream)
        start_stop_layout.addWidget(self.start_stream_btn)
        start_stop_layout.addWidget(self.stop_stream_btn)
        control_layout.addLayout(start_stop_layout)

        self.validate_btn = QPushButton("Validate Eye Tracker")
        self.validate_btn.clicked.connect(self.validate_eye_tracker)
        control_layout.addWidget(self.validate_btn)

        # Add Control Layout to Main Layout
        main_layout.addLayout(control_layout)

        return main_layout

    def setup_tabs(self):
        # Tabs: Gaze Data, Fixation, Metrics
        self.gaze_tab = self.create_gaze_data_tab()
        self.fixation_tab = self.create_fixation_tab()
        self.metrics_tab = self.create_metrics_tab()

        self.tab_widget.addTab(self.gaze_tab, "Gaze Data")
        self.tab_widget.addTab(self.fixation_tab, "Fixation")
        self.tab_widget.addTab(self.metrics_tab, "Metrics")

    def validate_eye_tracker(self):
        # Screen Selection Dialog
        screen_dialog = QDialog()
        screen_dialog.setWindowTitle("Select Validation Screen")
        layout = QVBoxLayout(screen_dialog)

        # Get available screens
        screens = QApplication.screens()
        screen_combo = QComboBox()
        for i, screen in enumerate(screens):
            screen_combo.addItem(f"Screen {i+1}: {screen.geometry().width()}x{screen.geometry().height()}")

        layout.addWidget(QLabel("Choose Validation Screen:"))
        layout.addWidget(screen_combo)

        validation_result_label = QLabel("Validation Status: Not Started")
        layout.addWidget(validation_result_label)

        if hasattr(self, 'tracker_thread') and self.tracker_thread and self.tracker_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Validation Tracker is already running. Please stop the stream")
            return
        def start_validation():
            selected_screen = screens[screen_combo.currentIndex()]
            tracker_params = {
                'use_mock': self.stream_type_combo.currentText() == "Mock",
                'fixation': False,
                'verbose': self.verbose_check.isChecked(),
                'push_stream': False,
                'save_data': True,
                'duration': (9*(2000+1000))/1000 + (2000*3)/1000 + 2000/1000
            }

            try:
                from pyETA.components.window import run_validation_window

                self.validation_window = run_validation_window(screen=selected_screen)
                self.tracker_thread = TrackerThread(tracker_params)
                self.tracker_thread.finished_signal.connect(
                    lambda msg: validation_result_label.setText(f"Validation Status: {msg}")
                )
                self.tracker_thread.error_signal.connect(
                    lambda msg: validation_result_label.setText(f"Validation Status: {msg}")
                )
                self.tracker_thread.start()
                self.validation_window.show()

                validation_result_label.setText("Validation in Progress...")

            except Exception as e:
                validation_result_label.setText(f"Validation Status: Error - {str(e)}")
                LOGGER.error(f"Validation error: {str(e)}")

        validate_btn = QPushButton("Start Validation")
        validate_btn.clicked.connect(start_validation)
        layout.addWidget(validate_btn)
        screen_dialog.exec()

    def create_gaze_data_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Gaze X Plot
        self.gaze_plot_x = pg.PlotWidget(title="Gaze X Position")
        self.curve_x = self.gaze_plot_x.plot(pen='r')
        layout.addWidget(self.gaze_plot_x)

        # Gaze Y Plot
        self.gaze_plot_y = pg.PlotWidget(title="Gaze Y Position")
        self.curve_y = self.gaze_plot_y.plot(pen='b')
        layout.addWidget(self.gaze_plot_y)

        return tab

    def create_fixation_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Fixation Plot
        self.fixation_plot = pg.PlotWidget(title="Fixation Points")
        layout.addWidget(self.fixation_plot)

        return tab

    def create_metrics_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Metrics Table
        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(4)
        self.metrics_table.setHorizontalHeaderLabels(["Metric", "Value", "Description", "Status"])
        layout.addWidget(self.metrics_table)

        return tab

    def start_stream(self):
        if hasattr(self, 'stream_thread') and self.stream_thread and self.stream_thread.isRunning():
            QMessageBox.warning(self, "Warning", "Stream is already running.")
            return
        tracker_params = {
            'data_rate': self.data_rate_slider.value(),
            'use_mock': self.stream_type_combo.currentText() == "Mock",
            'fixation': self.fixation_check.isChecked(),
            'velocity_threshold': 30,
            'dont_screen_nans': True,
            'verbose': self.verbose_check.isChecked(),
            'push_stream': self.push_stream_check.isChecked(),
            'save_data': False,
            }
        try:
            self.stream_thread = StreamThread()
            self.stream_thread.update_gaze_signal.connect(self.update_gaze_plot)
            self.stream_thread.update_fixation_signal.connect(self.update_fixation_plot)
            self.stream_thread.start()
            self.statusBar().showMessage("Stream started successfully", 3000)
        except Exception as e:
            error_msg = f"Failed to start stream: {str(e)}"
            self.statusBar().showMessage(error_msg, 5000)
            LOGGER.error(error_msg)

    def stop_stream(self):
        if self.stream_thread is None:
            QMessageBox.warning(self, "Warning", "No active stream to stop. Please start a stream first.")
            return
        if self.stream_thread and not self.stream_thread.isRunning():
            QMessageBox.warning(self, "Warning", "No active stream to stop.")
            return

        try:
            self.stream_thread.stop()
            self.stream_thread.wait()
            self.statusBar().showMessage("Stream stopped successfully", 3000)
        except Exception as e:
            error_msg = f"Error stopping stream: {str(e)}"
            self.statusBar().showMessage(error_msg, 5000)
            LOGGER.error(error_msg)

    def update_gaze_plot(self, times, x, y):
        self.curve_x.setData(times, x)
        self.curve_y.setData(times, y)

    def update_fixation_plot(self, x_coords, y_coords, counts):
        self.fixation_plot.clear()
        self.fixation_plot.plot(x_coords, y_coords, pen=None, symbol='o', symbolSize=counts, symbolBrush=(255, 0, 0, 150))

    def show_message(self, title, message, message_type=QMessageBox.information):
        msg_box = QMessageBox()
        msg_box.setIcon(message_type)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.exec()

@click.command(name="application_runner")
def main():
    app = QApplication(sys.argv)
    window = EyeTrackerAnalyzer()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
