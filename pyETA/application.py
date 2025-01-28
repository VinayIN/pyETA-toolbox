import sys
import click
import pathlib
import psutil
import os
import datetime
import threading
import numpy as np
import pandas as pd
import pyqtgraph as pg

import PyQt6.QtWidgets as qtw
import PyQt6.QtCore as qtc
import PyQt6.QtGui as qtg
from typing import Optional

from pyETA import __version__, LOGGER, __datapath__
from pyETA.components.track import Tracker
from pyETA.components.window import TrackerThread
import pyETA.components.utils as eta_utils
import pyETA.components.validate as eta_validate

class StreamThread(qtc.QThread):
    update_gaze_signal = qtc.pyqtSignal(list, list, list)  # times, x, y
    update_fixation_signal = qtc.pyqtSignal(list, list, list)  # x_coords, y_coords, counts

    def __init__(self):
        super().__init__()
        self.running = False
        self.id = None

    def run(self):
        self.running = True
        self.id = threading.get_native_id() 
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
            finally:
                self.stop()

    def stop(self):
        self.running = False
        self.id = None
        self.quit()
        self.wait()

class EyeTrackerAnalyzer(qtw.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"pyETA-{__version__}")
        self.resize(1200, 800)
        self.stream_thread = None
        self.tracker_thread = None

        # Central widget and main layout
        central_widget = qtw.QWidget()
        self.setCentralWidget(central_widget)

        # Splitter for collapsible sidebar
        splitter = qtw.QSplitter(qtc.Qt.Orientation.Horizontal, central_widget)

        # Sidebar
        self.sidebar = self.create_sidebar()
        splitter.addWidget(self.sidebar)
        self.system_info_timer = qtc.QTimer()
        self.system_info_timer.timeout.connect(self.update_system_info)
        self.system_info_timer.start(1000)

        # Main content area
        main_content_widget = qtw.QWidget()
        main_layout = qtw.QVBoxLayout(main_content_widget)

        # Stream Configuration and System Info
        config_info_layout = qtw.QVBoxLayout()
        stream_config_layout = self.create_stream_configuration()
        config_info_layout.addLayout(stream_config_layout)
        line = qtw.QFrame()
        line.setFrameShape(qtw.QFrame.Shape.HLine)
        config_info_layout.addWidget(line)
        main_layout.addLayout(config_info_layout)

        # Tabs
        self.tab_widget = qtw.QTabWidget()
        main_layout.addWidget(self.tab_widget)
        self.setup_tabs()

        splitter.addWidget(main_content_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)

        # Finalize layout
        layout = qtw.QVBoxLayout(central_widget)
        layout.addWidget(splitter)

        self.setStyleSheet("""
            QPushButton:hover {
                border: 1px solid black;
                border-radius: 5px;
                background-color: #2ECC71; 
            }
        """)

    def create_sidebar(self):
        frame = qtw.QFrame()
        layout = qtw.QVBoxLayout(frame)

        title = qtw.QLabel("<h1>Toolbox - Eye Tracker Analyzer</h1>")
        title.setStyleSheet("color: gray; margin-bottom: 10px;")
        layout.addWidget(title)

        faculty_info = qtw.QLabel(
            """<h3 style='color: #555;'>Faculty 1</h3>
            <a href='https://www.b-tu.de/en/fg-neuroadaptive-hci/' style='text-decoration: none;' target='_blank'>
                <strong> Neuroadaptive Human-Computer Interaction</strong><br>
                Brandenburg University of Technology (Cottbus-Senftenberg)
            </a>"""
        )
        faculty_info.setStyleSheet("margin-bottom: 20px;")
        layout.addWidget(faculty_info)

        source_code_link = qtw.QLabel(
            """<h3 style='color: #555;'>Source code</h3>
            <a href='https://github.com/VinayIN/EyeTrackerAnalyzer.git' style='text-decoration: none;' target='_blank'>
                https://github.com/VinayIN/EyeTrackerAnalyzer.git
            </a>"""
        )

        markdown_text = qtw.QLabel(
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
        card = qtw.QFrame()
        card.setFrameShape(qtw.QFrame.Shape.Box)
        layout = qtw.QVBoxLayout(card)
        system_buttons = qtw.QHBoxLayout()
        refresh_button = qtw.QPushButton("Refresh")
        exit_button = qtw.QPushButton("Exit")
        exit_button.clicked.connect(self.close)
        refresh_button.clicked.connect(self.refresh_application)
        system_buttons.addWidget(exit_button)
        system_buttons.addWidget(refresh_button)
        layout.addLayout(system_buttons)
        layout.setSpacing(10)

        self.system_info_labels = {
            "status": qtw.QLabel(),
            "pid": qtw.QLabel(),
            "stream pid": qtw.QLabel(),
            "validate pid": qtw.QLabel(),
            "runtime": qtw.QLabel(),
            "memory": qtw.QLabel(),
            "storage": qtw.QLabel(),
            "cpu": qtw.QLabel(),
        }

        for label_name, label in self.system_info_labels.items():
            layout.addWidget(label)

        self.update_system_info()
        return card

    def update_system_info(self):
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent(interval=0.1)
        storage_free = psutil.disk_usage(os.getcwd()).free / 1024**3  # Free storage in GB
        runtime = datetime.datetime.now() - datetime.datetime.fromtimestamp(process.create_time())

        self.system_info_labels["pid"].setText(f"<strong>PID:</strong> {process.pid}")
        self.system_info_labels["stream pid"].setText(f"<strong>Stream Thread ID:</strong> {self.stream_thread.id if self.stream_thread else None}")
        self.system_info_labels["validate pid"].setText(f"<strong>Validate Thread ID:</strong> {self.tracker_thread.id if self.tracker_thread else None}")
        self.system_info_labels["runtime"].setText(f"<strong>Runtime:</strong> {runtime}")
        self.system_info_labels["memory"].setText(f"<strong>Memory:</strong> {memory_info.rss / 1024**2:.1f} MB")
        self.system_info_labels["storage"].setText(f"<strong>Storage avail:</strong> {storage_free:.1f} GB")
        self.system_info_labels["cpu"].setText(f"<strong>CPU:</strong> {cpu_percent:.1f}%")

    def refresh_application(self):
        # plots
        self.gaze_plot_x.clear()
        self.gaze_plot_y.clear()
        self.fixation_plot.clear()

        # dropdown
        self.update_metric_tab()

        # metric table
        self.metrics_table.clear()

        self.statusBar().showMessage("Application refreshed successfully", 5000)
    
    def create_stream_configuration(self):
        # Main Horizontal Layout
        main_layout = qtw.QHBoxLayout()

        layout_first = qtw.QVBoxLayout()

        # Stream Type
        stream_type_layout = qtw.QHBoxLayout()
        stream_type_label = qtw.QLabel("Stream Type:")
        self.stream_type_combo = qtw.QComboBox()
        self.stream_type_combo.addItems(["Eye-Tracker", "Mock"])
        stream_type_layout.addWidget(stream_type_label)
        stream_type_layout.addWidget(self.stream_type_combo)
        layout_first.addLayout(stream_type_layout)

        # Data Rate
        data_rate_layout = qtw.QHBoxLayout()
        data_rate_label = qtw.QLabel("Data Rate (Hz):")
        self.data_rate_slider = qtw.QSlider(qtc.Qt.Orientation.Horizontal)
        self.data_rate_slider.setMinimum(0)
        self.data_rate_slider.setMaximum(800)
        self.data_rate_slider.setValue(600)
        self.data_rate_label = qtw.QLabel("600 Hz")
        self.data_rate_slider.valueChanged.connect(lambda value: self.data_rate_label.setText(f"{value} Hz"))
        data_rate_layout.addWidget(data_rate_label)
        data_rate_layout.addWidget(self.data_rate_slider)
        data_rate_layout.addWidget(self.data_rate_label)
        layout_first.addLayout(data_rate_layout)

        # Velocity Threshold
        velocity_threshold_layout = qtw.QHBoxLayout()
        velocity_threshold_label = qtw.QLabel("Velocity Threshold:")
        self.velocity_threshold_spinbox = qtw.QDoubleSpinBox()
        self.velocity_threshold_spinbox.setRange(0.0, 5.0)
        self.velocity_threshold_spinbox.setValue(1.5)
        self.velocity_threshold_spinbox.setSingleStep(0.1)
        self.velocity_threshold_spinbox.valueChanged.connect(lambda value: self.velocity_threshold_label.setText(f"{value:.1f}"))
        self.velocity_threshold_label = qtw.QLabel("1.5")
        velocity_threshold_layout.addWidget(velocity_threshold_label)
        velocity_threshold_layout.addWidget(self.velocity_threshold_spinbox)
        velocity_threshold_layout.addWidget(self.velocity_threshold_label)
        layout_first.addLayout(velocity_threshold_layout)

        main_layout.addLayout(layout_first)

        layout_second = qtw.QVBoxLayout()

        # Fixation Checkbox
        self.fixation_check = qtw.QCheckBox("Enable Fixation")
        self.fixation_check.setChecked(True)
        layout_second.addWidget(self.fixation_check)

        # Push to Stream Checkbox
        self.push_stream_check = qtw.QCheckBox("Push to Stream")
        self.push_stream_check.setChecked(True)
        layout_second.addWidget(self.push_stream_check)

        # Verbose Checkbox
        self.verbose_check = qtw.QCheckBox("Verbose Mode")
        layout_second.addWidget(self.verbose_check)

        # Don't Screen NaNs Checkbox
        self.dont_screen_nans_check = qtw.QCheckBox("Accept Screen NaNs (Default: 0)")
        layout_second.addWidget(self.dont_screen_nans_check)

        # Add Right Layout to Main Layout
        main_layout.addLayout(layout_second)

        # Stream Control Buttons (Below Both VBoxes)
        control_layout = qtw.QVBoxLayout()
        start_stop_layout = qtw.QHBoxLayout()
        self.start_stream_btn = qtw.QPushButton("Start Stream")
        self.stop_stream_btn = qtw.QPushButton("Stop Stream")
        self.start_stream_btn.clicked.connect(self.start_stream)
        self.stop_stream_btn.clicked.connect(self.stop_stream)
        start_stop_layout.addWidget(self.start_stream_btn)
        start_stop_layout.addWidget(self.stop_stream_btn)
        control_layout.addLayout(start_stop_layout)

        self.validate_btn = qtw.QPushButton("Validate Eye Tracker")
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
        screen_dialog = qtw.QDialog()
        screen_dialog.setWindowTitle("Select Validation Screen")
        layout = qtw.QVBoxLayout(screen_dialog)

        screens = qtw.QApplication.screens()
        screen_combo = qtw.QComboBox()
        for i, screen in enumerate(screens):
            screen_combo.addItem(f"Screen {i+1}: {screen.geometry().width()}x{screen.geometry().height()}")

        layout.addWidget(qtw.QLabel("Choose Validation Screen:"))
        layout.addWidget(screen_combo)

        if self.tracker_thread and self.tracker_thread.isRunning():
            qtw.QMessageBox.warning(self, "Warning", "Validation Tracker is already running. Please stop the stream")
            return

        def start_validation():
            selected_screen_index = screen_combo.currentIndex()
            tracker_params = {
                'use_mock': self.stream_type_combo.currentText() == "Mock",
                'fixation': False,
                'verbose': self.verbose_check.isChecked(),
                'push_stream': False,
                'save_data': True,
                'screen_index': selected_screen_index,
                'duration': (9*(2000+1000))/1000 + (2000*3)/1000 + 2000/1000
            }

            try:
                from pyETA.components.window import run_validation_window

                self.validation_window = run_validation_window(screen_index=selected_screen_index)
                self.tracker_thread = TrackerThread(tracker_params)
                self.tracker_thread.finished_signal.connect(
                    lambda msg: qtw.QMessageBox.information(self, "Tracking Thread", msg)
                )
                self.tracker_thread.error_signal.connect(
                    lambda msg: qtw.QMessageBox.critical(self, "Tracking Thread", msg)
                )
                self.tracker_thread.start()
                self.validation_window.show()

                self.statusBar().showMessage("Validation started", 10000)
                screen_dialog.close()

            except Exception as e:
                qtw.QMessageBox.critical(self, "Validation Error", str(e))
                LOGGER.error(f"Validation error: {str(e)}")

        validate_btn = qtw.QPushButton("Start Validation")
        validate_btn.clicked.connect(start_validation)
        layout.addWidget(validate_btn)
        screen_dialog.exec()

    def create_gaze_data_tab(self):
        tab = qtw.QWidget()
        layout = qtw.QVBoxLayout(tab)

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
        tab = qtw.QWidget()
        layout = qtw.QVBoxLayout(tab)

        # Fixation Plot
        self.fixation_plot = pg.PlotWidget(title="Fixation Points")
        layout.addWidget(self.fixation_plot)

        return tab
    
    def get_gaze_and_validate_data(self):
        gaze = sorted(eta_utils.get_file_names(prefix="gaze_data_"))
        validate = sorted(eta_utils.get_file_names(prefix="system_"))
        return gaze, validate

    def create_metrics_tab(self):
        tab = qtw.QWidget()
        layout = qtw.QVBoxLayout(tab)
        metrics_title = qtw.QLabel("<h2>Statistics: Eye Tracker Validation</h2>")
        metrics_datapath = qtw.QLabel(f"Searching data files at path: {__datapath__}")
        file_selector = qtw.QHBoxLayout()
        
        self.gaze_data = qtw.QComboBox()
        self.validate_data = qtw.QComboBox()

        file_selector.addWidget(self.gaze_data)
        file_selector.addWidget(self.validate_data)
        self.update_metric_tab()

        validate_btn = qtw.QPushButton("Validate")
        self.df = pd.DataFrame()
        validate_btn.clicked.connect(self.update_metrics_table)

        layout.addWidget(metrics_title)
        layout.addWidget(metrics_datapath)
        layout.addLayout(file_selector)
        layout.addWidget(validate_btn)


        # Metrics Table
        self.metrics_table = qtw.QTableWidget()
        layout.addWidget(self.metrics_table)
        download_btn = qtw.QPushButton("Download CSV")
        download_btn.clicked.connect(self.download_csv)
        layout.addWidget(download_btn)

        return tab
    
    def update_metric_tab(self):
        self.gaze_data_items, self.validate_data_items = self.get_gaze_and_validate_data()
        self.gaze_data.clear()
        self.gaze_data.addItems(['select gaze data'] + [f"File {idx+1}: {eta_validate.get_gaze_data_timestamp(file)}" for idx, file in enumerate(self.gaze_data_items)])
        self.validate_data.clear()
        self.validate_data.addItems(['select validation data'] + [f"File {idx+1} {eta_validate.get_validate_data_timestamp(file)}" for idx,file in enumerate(self.validate_data_items)])

    def start_stream(self):
        if self.stream_thread and self.stream_thread.isRunning():
            qtw.QMessageBox.warning(self, "Warning", "Stream is already running.")
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
            self.stream_pid = self.stream_thread.currentThreadId()
            self.statusBar().showMessage("Stream started successfully", 3000)
        except Exception as e:
            error_msg = f"Failed to start stream: {str(e)}"
            self.statusBar().showMessage(error_msg, 5000)
            LOGGER.error(error_msg)

    def stop_stream(self):
        if not self.stream_thread or not self.stream_thread.isRunning():
            qtw.QMessageBox.warning(self, "Warning", "No active stream to stop.")
            return
        try:
            self.stream_thread.stop()

            self.stream_thread = None
            self.stream_pid = None
            self.statusBar().showMessage("Stream stopped successfully", 3000)
        except Exception as e:
            LOGGER.error(f"Error stopping stream: {str(e)}")
            self.statusBar().showMessage(f"Error stopping stream: {str(e)}", 5000)

    def update_gaze_plot(self, times, x, y):
        self.curve_x.setData(times, x)
        self.curve_y.setData(times, y)

    def update_fixation_plot(self, x_coords, y_coords, counts):
        self.fixation_plot.clear()
        self.fixation_plot.plot(x_coords, y_coords, pen=None, symbol='o', symbolSize=counts, symbolBrush=(255, 0, 0, 150))

    def update_metrics_table(self):
        self.df = eta_validate.get_statistics(
            gaze_file=self.gaze_data_items[self.gaze_data.currentIndex() - 1],
            validate_file=self.validate_data_items[self.validate_data.currentIndex() - 1])
        self.metrics_table.setRowCount(self.df.shape[0])
        self.metrics_table.setColumnCount(self.df.shape[1])
        self.metrics_table.setHorizontalHeaderLabels(self.df.columns)

        for row in range(self.df.shape[0]):
            for col in range(self.df.shape[1]):
                item = qtw.QTableWidgetItem(str(self.df.iloc[row, col]))
                item.setTextAlignment(qtc.Qt.AlignmentFlag.AlignCenter)
                self.metrics_table.setItem(row, col, item)
        
        self.metrics_table.setAlternatingRowColors(True)
        self.metrics_table.resizeColumnsToContents()
        self.statusBar().showMessage("Metrics generated successfully", 5000)

    def download_csv(self):
        if self.df.empty:
            qtw.QMessageBox.critical(self, "Error", "No data to save as CSV")
            return
        
        filename, _ = qtw.QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if filename:
            self.df.to_csv(filename, index=False)

    def closeEvent(self, event):
        self.system_info_timer.stop()
        event.accept()

@click.command(name="application")
def main():
    app = qtw.QApplication(sys.argv)
    window = EyeTrackerAnalyzer()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
