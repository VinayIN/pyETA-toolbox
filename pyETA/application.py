import sys
import click
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

from pyETA.components.reader import StreamThread, TrackerThread
import pyETA.components.utils as eta_utils
import pyETA.components.validate as eta_validate


class EyeTrackerAnalyzer(qtw.QMainWindow):
    """Main application window for pyETA"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"pyETA-{__version__}")
        self.resize(1200, 800)
        self.stream_thread = None
        self.validate_thread = None
        self.is_gaze_playing = False
        self.is_fixation_playing = False
        self.start_time = None

        self.plot_timer = qtc.QTimer()
        self.plot_timer.timeout.connect(self.update_plots_from_stream)
        self.plot_timer.start(500)

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
        self.update_status_bar("pyETA status OK", 1, 5000)

        self.setStyleSheet("""
            QPushButton:hover {
                border: 1px solid black;
                border-radius: 5px;
                background-color: #2ECC71; 
            }
        """)

    def update_status_bar(self, message, state=3, timeout=5000):
        """
        Updates the status bar with the given message and state.

        0: Error (Red)
        1: Success (Green)
        2: Processing (Yellow)
        3: Default (None)
        """
        if state == 2:
            self.statusBar().setStyleSheet("background-color: #FFFF00; color: black;")
        elif state == 0:
            self.statusBar().setStyleSheet("background-color: #FF0000; color: white;")
        elif state == 1:
            self.statusBar().setStyleSheet("background-color: #2ECC71; color: black;")
        else:
            self.statusBar().setStyleSheet("background-color: none;")
        self.statusBar().showMessage(message, timeout)
        qtc.QTimer.singleShot(timeout, lambda: self.statusBar().setStyleSheet("background-color: none;"))

    def create_sidebar(self):
        frame = qtw.QFrame()
        layout = qtw.QVBoxLayout(frame)

        title = qtw.QLabel("<h1>Toolbox - Eye Tracker Analyzer</h1>")
        title.setStyleSheet("color: gray; margin-bottom: 10px;")
        layout.addWidget(title)

        self.source_code_link = qtw.QTextBrowser()
        self.source_code_link.setOpenExternalLinks(True)
        self.source_code_link.setReadOnly(True)
        self.source_code_link.setHtml(
            """
            <h3 style='color: #555;'>Faculty 1</h3>
            <a href='https://www.b-tu.de/en/fg-neuroadaptive-hci/' style='text-decoration: none;'>
                <strong>Neuroadaptive Human-Computer Interaction</strong><br>
                Brandenburg University of Technology (Cottbus-Senftenberg)
            </a>
            <h3 style='color: #555;'>Source code</h3>
            <a href='https://github.com/VinayIN/EyeTrackerAnalyzer.git' style='text-decoration: none;' target='_blank'>
                https://github.com/VinayIN/EyeTrackerAnalyzer.git
            </a>
            <h3 style='color: #555;'>Documentation</h3>
            <a href='https://vinayin.gitbook.io/pyeta/' style='text-decoration: none;' target='_blank'>
                https://vinayin.gitbook.io/pyeta
            """
        )
        self.source_code_link.setStyleSheet("margin-bottom: 20px; background: transparent;")
        self.source_code_link.anchorClicked.connect(lambda url: qtg.QDesktopServices.openUrl(url))

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
        layout.addWidget(self.source_code_link)

        self.system_info_card = self.create_system_info_card()
        layout.addWidget(self.system_info_card)
        return frame

    def create_system_info_card(self):
        card = qtw.QFrame()
        card.setFrameShape(qtw.QFrame.Shape.Box)
        layout = qtw.QVBoxLayout(card)
        system_buttons = qtw.QHBoxLayout()
        refresh_button = qtw.QPushButton("Refresh application")
        exit_button = qtw.QPushButton("Exit")
        exit_button.clicked.connect(self.close)
        refresh_button.clicked.connect(self.refresh_application)
        system_buttons.addWidget(exit_button)
        system_buttons.addWidget(refresh_button)
        layout.addLayout(system_buttons)

        # Add refresh slider for plot updates
        refresh_rate_layout = qtw.QHBoxLayout()
        refresh_rate_label = qtw.QLabel("Refresh Rate (ms):")
        self.refresh_slider = qtw.QSlider(qtc.Qt.Orientation.Horizontal)
        self.refresh_slider.setMinimum(10)
        self.refresh_slider.setMaximum(1000)
        self.refresh_slider.setValue(200)
        self.refresh_label = qtw.QLabel("200 ms")
        self.refresh_slider.valueChanged.connect(self.update_plot_refresh_rate)
        refresh_rate_layout.addWidget(refresh_rate_label)
        refresh_rate_layout.addWidget(self.refresh_slider)
        refresh_rate_layout.addWidget(self.refresh_label)
        layout.addLayout(refresh_rate_layout)

        self.system_info_labels = {
            "status": qtw.QLabel(),
            "pid": qtw.QLabel(),
            "stream id": qtw.QLabel(),
            "validate id": qtw.QLabel(),
            "total threads": qtw.QLabel(),
            "runtime": qtw.QLabel(),
            "memory": qtw.QLabel(),
            "storage": qtw.QLabel(),
            "cpu": qtw.QLabel(),
        }

        for label_name, label in self.system_info_labels.items():
            layout.addWidget(label)

        self.update_system_info()
        return card

    def update_plot_refresh_rate(self, value):
        self.plot_timer.setInterval(value)
        self.refresh_label.setText(f"{value} ms")
        LOGGER.info(f"Plot refresh rate set to {value} ms")

    def update_system_info(self):
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent(interval=0.1)
        storage_free = psutil.disk_usage(os.getcwd()).free / 1024**3  # Free storage in GB
        runtime = datetime.datetime.now() - datetime.datetime.fromtimestamp(process.create_time())

        self.system_info_labels["pid"].setText(f"<strong>Application PID:</strong> {process.pid}")
        self.system_info_labels["stream id"].setText(
            f"<strong>Stream Thread ID:</strong> {self.stream_thread.id if self.stream_thread else 'Not Running'}"
        )
        self.system_info_labels["validate id"].setText(
            f"<strong>Validate Thread ID:</strong> {self.validate_thread.id if self.validate_thread else 'Not Running'}"
        )
        self.system_info_labels["total threads"].setText(f"<strong>Total Threads:</strong> {threading.active_count()}")
        self.system_info_labels["runtime"].setText(f"<strong>Runtime:</strong> {runtime}")
        self.system_info_labels["memory"].setText(f"<strong>Memory:</strong> {memory_info.rss / 1024**2:.1f} MB")
        self.system_info_labels["storage"].setText(f"<strong>Storage available:</strong> {storage_free:.1f} GB")
        self.system_info_labels["cpu"].setText(f"<strong>CPU Usage:</strong> {cpu_percent:.1f}%")

    def refresh_application(self):
        self.source_code_link.clearFocus()
        self.gaze_plot_x_curve.setData([], [])
        self.gaze_plot_y_curve.setData([], [])
        self.fixation_scatter.setData([], [])
        self.update_metric_tab()
        self.metrics_table.clear()
        self.update_status_bar("Application refreshed successfully", 1, 5000)
    
    def create_stream_configuration(self):
        main_layout = qtw.QHBoxLayout()
        layout_first = qtw.QVBoxLayout()

        stream_type_layout = qtw.QHBoxLayout()
        stream_type_label = qtw.QLabel("Stream Type:")
        self.stream_type_combo = qtw.QComboBox()
        self.stream_type_combo.addItems(["Eye-Tracker", "Mock"])
        stream_type_layout.addWidget(stream_type_label)
        stream_type_layout.addWidget(self.stream_type_combo)
        layout_first.addLayout(stream_type_layout)

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

        velocity_threshold_layout = qtw.QHBoxLayout()
        velocity_threshold_label = qtw.QLabel("Velocity Threshold:")
        self.velocity_threshold_spinbox = qtw.QDoubleSpinBox()
        self.velocity_threshold_spinbox.setRange(0.0, 50.0)
        self.velocity_threshold_spinbox.setValue(5.0)
        self.velocity_threshold_spinbox.setSingleStep(0.1)
        self.velocity_threshold_spinbox.valueChanged.connect(
            lambda value: self.velocity_threshold_label.setText(f"{value:.1f}")
        )
        self.velocity_threshold_label = qtw.QLabel("50.0")
        velocity_threshold_layout.addWidget(velocity_threshold_label)
        velocity_threshold_layout.addWidget(self.velocity_threshold_spinbox)
        velocity_threshold_layout.addWidget(self.velocity_threshold_label)
        layout_first.addLayout(velocity_threshold_layout)

        main_layout.addLayout(layout_first)

        layout_second = qtw.QVBoxLayout()
        self.fixation_check = qtw.QCheckBox("Enable Fixation")
        self.fixation_check.setChecked(True)
        layout_second.addWidget(self.fixation_check)

        self.push_stream_check = qtw.QCheckBox("Push to Stream")
        self.push_stream_check.setChecked(True)
        layout_second.addWidget(self.push_stream_check)

        self.verbose_check = qtw.QCheckBox("Verbose Mode")
        layout_second.addWidget(self.verbose_check)

        self.dont_screen_nans_check = qtw.QCheckBox("Accept Screen NaNs (Default: 0)")
        layout_second.addWidget(self.dont_screen_nans_check)

        main_layout.addLayout(layout_second)

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

        main_layout.addLayout(control_layout)
        return main_layout

    def setup_tabs(self):
        self.gaze_tab = self.create_gaze_data_tab()
        self.fixation_tab = self.create_fixation_tab()
        self.metrics_tab = self.create_metrics_tab()

        self.tab_widget.addTab(self.gaze_tab, "Gaze Data")
        self.tab_widget.addTab(self.fixation_tab, "Fixation")
        self.tab_widget.addTab(self.metrics_tab, "Metrics")

    def validate_eye_tracker(self):
        screen_dialog = qtw.QDialog()
        screen_dialog.setWindowTitle("Select Validation Screen")
        layout = qtw.QVBoxLayout(screen_dialog)

        screens = qtw.QApplication.screens()
        screen_combo = qtw.QComboBox()
        for i, screen in enumerate(screens):
            screen_combo.addItem(f"Screen {i+1}: {screen.geometry().width()}x{screen.geometry().height()}")

        layout.addWidget(qtw.QLabel("Choose Validation Screen:"))
        layout.addWidget(screen_combo)

        if self.validate_thread and self.validate_thread.isRunning():
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
                'duration': (9*(3000+1000))/1000 + (2000*3)/1000 + 2000/1000
            }

            try:
                from pyETA.components.window import run_validation_window

                self.validation_window = run_validation_window(screen_index=selected_screen_index)
                self.validate_thread = TrackerThread()
                self.validate_thread.set_variables(tracker_params)
                self.validate_thread.finished_signal.connect(
                    lambda msg: qtw.QMessageBox.information(self, "Validation Thread", msg)
                )
                self.validate_thread.error_signal.connect(
                    lambda msg: qtw.QMessageBox.critical(self, "Validation Thread", msg)
                )
                self.validate_thread.start()
                self.validation_window.show()

                self.update_status_bar("Validation started", 2, 10000)
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

        control_panel = qtw.QHBoxLayout()
        self.gaze_play_btn = qtw.QPushButton("Play")
        self.gaze_play_btn.setFixedSize(60, 30)
        self.gaze_play_btn.clicked.connect(self.toggle_gaze_play)
        self.gaze_stream_label = qtw.QLabel("Stream: Not Connected")
        control_panel.addWidget(self.gaze_play_btn)
        control_panel.addWidget(self.gaze_stream_label)
        layout.addLayout(control_panel)

        self.gaze_plot_x = pg.PlotWidget(title="Gaze X Position")
        self.gaze_plot_x.showGrid(x=True, y=True)
        self.gaze_plot_x.setYRange(0, self.screen().size().width())
        self.gaze_plot_x.setLabel('bottom', 'Time (s)')
        self.gaze_plot_x.setLabel('left', 'Pixel Position - Width')
        self.gaze_plot_x_curve = self.gaze_plot_x.plot(pen='y')
        layout.addWidget(self.gaze_plot_x)

        self.gaze_plot_y = pg.PlotWidget(title="Gaze Y Position")
        self.gaze_plot_y.showGrid(x=True, y=True)
        self.gaze_plot_y.setYRange(0, self.screen().size().height())
        self.gaze_plot_y.setLabel('bottom', 'Time (s)')
        self.gaze_plot_y.setLabel('left', 'Pixel Position - Height')
        self.gaze_plot_y_curve = self.gaze_plot_y.plot(pen='r')
        layout.addWidget(self.gaze_plot_y)
        
        return tab

    def create_fixation_tab(self):
        tab = qtw.QWidget()
        layout = qtw.QVBoxLayout(tab)

        control_panel = qtw.QHBoxLayout()
        self.fixation_play_btn = qtw.QPushButton("Play")
        self.fixation_play_btn.setFixedSize(60, 30)
        self.fixation_play_btn.clicked.connect(self.toggle_fixation_play)
        self.fixation_stream_label = qtw.QLabel("Stream: Not Connected")
        control_panel.addWidget(self.fixation_play_btn)
        control_panel.addWidget(self.fixation_stream_label)
        layout.addLayout(control_panel)

        self.fixation_plot = pg.PlotWidget(title="Fixation Points")
        self.fixation_plot.setXRange(0, self.screen().size().width())
        self.fixation_plot.setYRange(0, self.screen().size().height())
        self.fixation_plot.getAxis('left').setLabel('Pixel Position - Height')
        self.fixation_plot.getAxis('bottom').setLabel('Pixel Position - Width')
        self.fixation_plot.invertY(True)
        self.fixation_scatter = pg.ScatterPlotItem()
        self.fixation_plot.addItem(self.fixation_scatter)
        layout.addWidget(self.fixation_plot)
        return tab
    
    def toggle_gaze_play(self):
        self.is_gaze_playing = not self.is_gaze_playing
        self.gaze_play_btn.setText("Pause" if self.is_gaze_playing else "Play")
    
    def toggle_fixation_play(self):
        self.is_fixation_playing = not self.is_fixation_playing
        self.fixation_play_btn.setText("Pause" if self.is_fixation_playing else "Play")
    
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

        self.metrics_table = qtw.QTableWidget()
        layout.addWidget(self.metrics_table)
        download_btn = qtw.QPushButton("Download CSV")
        download_btn.clicked.connect(self.download_csv)
        layout.addWidget(download_btn)

        return tab

    def update_plots_from_stream(self):
        if not self.stream_thread or not self.stream_thread.isRunning() or not self.start_time:
            return

        if self.is_gaze_playing:
            gaze_data = self.stream_thread.get_data(fixation=False)
            if len(gaze_data) > 0:
                timestamps = gaze_data['timestamp']
                x_coord = gaze_data['x']
                y_coord = gaze_data['y']
                self.update_gaze_plot(timestamps, x_coord, y_coord)
    
        if self.is_fixation_playing:
            fixation_data = self.stream_thread.get_data(fixation=True)
            if len(fixation_data) > 0:
                x_coord = fixation_data['x']
                y_coord = fixation_data['y']
                count = fixation_data['count']
                timestamp = fixation_data['timestamp']
                self.update_fixation_plot(x_coord, y_coord, count, timestamp)

    def update_gaze_plot(self, timestamp, x_coord, y_coord):
        current_time = timestamp[-1] - self.start_time
        window_size = 10

        relative_times = timestamp - self.start_time
        mask = relative_times >= (current_time - window_size)
        filtered_times = relative_times[mask]
        filtered_x = x_coord[mask]
        filtered_y = y_coord[mask]

        self.gaze_plot_x_curve.setData(filtered_times, filtered_x)
        self.gaze_plot_y_curve.setData(filtered_times, filtered_y)
        self.gaze_plot_x.setXRange(max(0, current_time - window_size), current_time)
        self.gaze_plot_y.setXRange(max(0, current_time - window_size), current_time)

    def update_fixation_plot(self, x_coord, y_coord, counts, timestamp):
        self.fixation_scatter.setData(
            x=x_coord,
            y=y_coord,
            size = np.minimum(counts/10, 50),
            symbol='o'
        )

    def update_metric_tab(self):
        self.gaze_data_items, self.validate_data_items = self.get_gaze_and_validate_data()
        self.gaze_data.clear()
        self.gaze_data.addItems(['select gaze data'] + [
            f"File {idx+1}: {eta_validate.get_gaze_data_timestamp(file)}" for idx, file in enumerate(self.gaze_data_items)
        ])
        self.validate_data.clear()
        self.validate_data.addItems(['select validation data'] + [
            f"File {idx+1} {eta_validate.get_validate_data_timestamp(file)}" for idx, file in enumerate(self.validate_data_items)
        ])

    def start_stream(self):
        if self.stream_thread and self.stream_thread.isRunning():
            qtw.QMessageBox.warning(self, "Warning", "Stream is already running.")
            return
        
        tracker_params = {
            'data_rate': self.data_rate_slider.value(),
            'use_mock': self.stream_type_combo.currentText() == "Mock",
            'fixation': self.fixation_check.isChecked(),
            'velocity_threshold': self.velocity_threshold_spinbox.value(),
            'dont_screen_nans': self.dont_screen_nans_check.isChecked(),
            'verbose': self.verbose_check.isChecked(),
            'push_stream': self.push_stream_check.isChecked(),
            'save_data': False,
        }
        
        try:
            self.update_status_bar("Stream: Connecting...", 2, 2000)
            self.start_time = datetime.datetime.now().timestamp()
            self.stream_thread = StreamThread()
            self.stream_thread.set_variables(tracker_params=tracker_params)
            self.stream_thread.found_signal.connect(lambda msg: self.update_plot_label(msg))
            self.stream_thread.error_signal.connect(lambda msg: qtw.QMessageBox.critical(self, "Error", msg))
            self.stream_thread.start()
            self.plot_timer.start(self.refresh_slider.value())  # Start timer with current slider value

        except Exception as e:
            error_msg = f"Failed to start stream: {str(e)}"
            LOGGER.error(error_msg)
            self.update_status_bar(error_msg, 0, 5000)

    def stop_stream(self):
        if not self.stream_thread or not self.stream_thread.isRunning():
            qtw.QMessageBox.warning(self, "Warning", "No active stream to stop.")
            return
        
        try:
            self.stream_thread.stop()
            self.stream_thread = None
            self.start_time = None
            self.plot_timer.stop()  # Stop the plot update timer
            self.update_status_bar("Stream stopped successfully", 1, 3000)
            self.is_gaze_playing = False
            self.is_fixation_playing = False
            self.gaze_play_btn.setText("Play")
            self.fixation_play_btn.setText("Play")
            self.update_plot_label()
            LOGGER.warning(f"Thread count after stop stream: {threading.active_count()}")
        except Exception as e:
            LOGGER.error(f"Error stopping stream: {str(e)}")
            self.update_status_bar(f"Error stopping stream: {str(e)}", 0, 5000)

    def update_plot_label(self, msg="Stream: Not Connected"):
        self.gaze_stream_label.setText(msg)
        self.fixation_stream_label.setText(msg)
        if "✔" in msg:
            self.update_status_bar("Stream connected successfully", 1, 5000)
        if "✘" in msg:
            self.update_status_bar("Stream connection failed", 0, 5000)

    def update_metrics_table(self):
        self.update_status_bar("Calculating", 2, 5000)
        self.combined_df, df, described_df = eta_validate.get_statistics(
            gaze_file=self.gaze_data_items[self.gaze_data.currentIndex() - 1],
            validate_file=self.validate_data_items[self.validate_data.currentIndex() - 1]
        )
        LOGGER.info(f"Combined DataFrame: {self.combined_df.shape}, Grid DataFrame: {df.shape}, Described DataFrame: {described_df.shape}")

        self.metrics_table.setRowCount(self.combined_df.shape[0])
        self.metrics_table.setColumnCount(self.combined_df.shape[1])
        self.metrics_table.setHorizontalHeaderLabels(self.combined_df.columns)

        for row in range(self.combined_df.shape[0]):
            for col in range(self.combined_df.shape[1]):
                item = qtw.QTableWidgetItem(str(self.combined_df.iloc[row, col]))
                item.setTextAlignment(qtc.Qt.AlignmentFlag.AlignCenter)
                self.metrics_table.setItem(row, col, item)
        
        self.metrics_table.setAlternatingRowColors(True)
        self.metrics_table.resizeColumnsToContents()
        self.update_status_bar("Metrics generated successfully", 1, 8000)

    def download_csv(self):
        if self.combined_df.empty:
            qtw.QMessageBox.critical(self, "Error", "No data to save as CSV")
            return
        
        filename, _ = qtw.QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if filename:
            self.combined_df.to_csv(filename, index=False)
            self.update_status_bar(f"csv saved at: {os.path.abspath(filename)}", 1, 5000)

    def closeEvent(self, event):
        LOGGER.info("close event invoked.")
        self.system_info_timer.stop()
        if self.stream_thread and self.stream_thread.isRunning():
            self.stream_thread.stop()
            LOGGER.info("Stopping stream thread during closeEvent")
        if self.validate_thread and self.validate_thread.isRunning():
            self.validate_thread.stop()
            LOGGER.info("Stopping validate thread during closeEvent")
        LOGGER.warning(f"Threads alive: {[t.name for t in threading.enumerate()]}")
        event.accept()


@click.command(name="application")
def main():
    app = qtw.QApplication(sys.argv)
    window = EyeTrackerAnalyzer()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()