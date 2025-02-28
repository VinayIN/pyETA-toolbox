import sys
import click
import pathlib
import psutil
import os
import datetime
import threading
import pylsl
from mne_lsl import lsl
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
        self.system_info_timer.start(100)

        self.refresh_rate_timer = qtc.QTimer()
        self.refresh_rate_timer.timeout.connect(self.adjust_refresh_rate)
        self.refresh_rate_timer.start(1000 * self.refresh_rate_slider.value())

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
        Updates the status bar with a message and changes its color based on the state.
        
        0: error
        1: sucess
        2: processing
        3: None
        Args:
            message (str): The message to display.
            state (str): The state of the operation ("processing", "error", "success").
            timeout (int): Time in milliseconds to display the message.
        """
        if state == 2:
            self.statusBar().setStyleSheet("background-color: #FFFF00;")
        elif state == 0:
            self.statusBar().setStyleSheet("background-color: #FF0000;")
        elif state == 1:
            self.statusBar().setStyleSheet("background-color: #2ECC71;")
        else:
            self.statusBar().setStyleSheet("background-color: none;")
        self.statusBar().showMessage(message, timeout)
        qtc.QTimer.singleShot(timeout, lambda: self.statusBar().setStyleSheet("background-color: none;"))

    def create_sidebar(self):
        """Create the sidebar with system information and about section"""
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
        """Create the system information card with refresh rate slider"""
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

        # Add Refresh Rate Slider
        refresh_rate_layout = qtw.QHBoxLayout()
        refresh_rate_label = qtw.QLabel("Refresh Rate (Hz):")
        self.refresh_rate_slider = qtw.QSlider(qtc.Qt.Orientation.Horizontal)
        self.refresh_rate_slider.setMinimum(1)
        self.refresh_rate_slider.setMaximum(10)
        self.refresh_rate_slider.setValue(3)
        self.refresh_rate_label = qtw.QLabel("3 Hz")
        self.refresh_rate_slider.valueChanged.connect(lambda value: self.refresh_rate_label.setText(f"{value} Hz"))
        self.refresh_rate_slider.valueChanged.connect(self.adjust_refresh_rate)
        refresh_rate_layout.addWidget(refresh_rate_label)
        refresh_rate_layout.addWidget(self.refresh_rate_slider)
        refresh_rate_layout.addWidget(self.refresh_rate_label)

        layout.addLayout(system_buttons)
        layout.setSpacing(5)
        layout.addLayout(refresh_rate_layout)
        layout.setSpacing(5)

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

    def update_system_info(self):
        """Update the system information labels"""
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent(interval=0.1)
        storage_free = psutil.disk_usage(os.getcwd()).free / 1024**3  # Free storage in GB
        runtime = datetime.datetime.now() - datetime.datetime.fromtimestamp(process.create_time())

        self.system_info_labels["pid"].setText(f"<strong>Application PID:</strong> {process.pid}")
        self.system_info_labels["stream id"].setText(f"<strong>Stream Thread ID:</strong> {self.stream_thread.id if self.stream_thread else 'Not Running'}")
        self.system_info_labels["validate id"].setText(f"<strong>Validate Thread ID:</strong> {self.validate_thread.id if self.validate_thread else 'Not Running'}")
        self.system_info_labels["total threads"].setText(f"<strong>Total Threads:</strong> {threading.active_count()}")
        self.system_info_labels["runtime"].setText(f"<strong>Runtime:</strong> {runtime}")
        self.system_info_labels["memory"].setText(f"<strong>Memory:</strong> {memory_info.rss / 1024**2:.1f} MB")
        self.system_info_labels["storage"].setText(f"<strong>Storage available:</strong> {storage_free:.1f} GB")
        self.system_info_labels["cpu"].setText(f"<strong>CPU Usage:</strong> {cpu_percent:.1f}%")

    def refresh_application(self):
        """Refresh the application by clearing the data and updating the files info in metrics tab"""
        self.gaze_plot_x_curve.clear()
        self.gaze_plot_y_curve.clear()
        self.fixation_plot.clear()
        self.update_metric_tab()
        self.metrics_table.clear()
        eta_utils.close_dummy_threads() # This is a workaround. remove after finding the cause for dummy thread
        self.update_status_bar("Application refreshed successfully", 1, 5000)
    
    def create_stream_configuration(self):
        """
        Creates the stream configuration layout for the application.
        This method sets up the user interface components for configuring the stream,
        including stream type selection, data rate adjustment, velocity threshold setting,
        and various checkboxes for additional options. It also includes buttons for
        starting, stopping, and validating the stream.
        Returns:
            QHBoxLayout: The main horizontal layout containing all the configuration components.
        """
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
        """
        Sets up the tabs for the application.
        This method creates three tabs: Gaze Data, Fixation, and Metrics.
        It initializes each tab by calling the respective creation methods
        and then adds them to the tab widget.
        Tabs:
            - Gaze Data: Displays gaze data.
            - Fixation: Displays fixation data.
            - Metrics: Displays various metrics.
        Methods called:
            - create_gaze_data_tab: Creates the Gaze Data tab.
            - create_fixation_tab: Creates the Fixation tab.
            - create_metrics_tab: Creates the Metrics tab.
        """
        # Tabs: Gaze Data, Fixation, Metrics
        self.gaze_tab = self.create_gaze_data_tab()
        self.fixation_tab = self.create_fixation_tab()
        self.metrics_tab = self.create_metrics_tab()

        self.tab_widget.addTab(self.gaze_tab, "Gaze Data")
        self.tab_widget.addTab(self.fixation_tab, "Fixation")
        self.tab_widget.addTab(self.metrics_tab, "Metrics")

    def validate_eye_tracker(self):
        """
        Opens a dialog for selecting a screen to use for eye tracker validation and starts the validation process.
        The method performs the following steps:
        1. Opens a QDialog to allow the user to select a screen for validation.
        2. Checks if the validation tracker thread is already running and shows a warning if it is.
        3. Sets up the validation parameters and starts the validation process on the selected screen.
        4. Handles any exceptions that occur during the validation process and logs the error.
        Returns:
        None
        """
        
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
                self.validate_thread.finished_signal.connect(lambda msg: qtw.QMessageBox.information(self, "Validation Thread", msg))
                self.validate_thread.error_signal.connect(lambda msg: qtw.QMessageBox.critical(self, "Validation Thread", msg))
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
        if self.validate_thread and self.validate_thread.isRunning():
            self.validate_thread.stop()
            self.validate_thread = None
    
    def create_gaze_data_tab(self):
        """
        Creates a tab for displaying gaze data with control panel and plots.
        This method sets up a QWidget containing a vertical layout with the following components:
        - A control panel with a "Play" button and a label indicating the stream status.
        - A plot for displaying the gaze X position over time.
        - A plot for displaying the gaze Y position over time.
        Returns:
            QWidget: The tab containing the gaze data visualization components.
        """
        tab = qtw.QWidget()
        layout = qtw.QVBoxLayout(tab)

        control_panel = qtw.QHBoxLayout()
        self.gaze_play_btn = qtw.QPushButton("Play")
        self.gaze_play_btn.setFixedSize(60, 30)
        self.gaze_play_btn.clicked.connect(self.toggle_gaze_play)
        self.gaze_stream_label = qtw.QLabel("Stream: Not Connected")
        control_panel.addWidget(self.gaze_play_btn)
        control_panel.addWidget(self.gaze_stream_label)
        #control_panel.addStretch()
        layout.addLayout(control_panel)

        # Gaze X Plot
        self.gaze_plot_x = pg.PlotWidget(title="Gaze X Position")
        self.gaze_plot_x.showGrid(x=True, y=True)
        self.gaze_plot_x.setYRange(0, self.size().width())
        self.gaze_plot_x.setLabel('bottom', 'Time (s)')
        self.gaze_plot_x.setLabel('left', 'Pixel Position - Width')
        self.gaze_plot_x_curve = self.gaze_plot_x.plot(pen='b')
        layout.addWidget(self.gaze_plot_x)

        # Gaze Y Plot
        self.gaze_plot_y = pg.PlotWidget(title="Gaze Y Position")
        self.gaze_plot_y.showGrid(x=True, y=True)
        self.gaze_plot_y.setYRange(0, self.size().height())
        self.gaze_plot_y.setLabel('bottom', 'Time (s)')
        self.gaze_plot_y.setLabel('left', 'Pixel Position - Height')
        self.gaze_plot_y_curve = self.gaze_plot_y.plot(pen='r')
        layout.addWidget(self.gaze_plot_y)
        
        return tab

    def create_fixation_tab(self):
        """
        Creates a tab for displaying fixation points in the application.
        This method sets up a QWidget with a QVBoxLayout containing a control panel
        with a play button and a stream status label, and a PlotWidget for displaying
        fixation points. It also initializes a dictionary to store current fixation data.
        Returns:
            QWidget: The tab widget containing the fixation points display and controls.
        """
        tab = qtw.QWidget()
        layout = qtw.QVBoxLayout(tab)

        control_panel = qtw.QHBoxLayout()
        self.fixation_play_btn = qtw.QPushButton("Play")
        self.fixation_play_btn.setFixedSize(60, 30)
        self.fixation_play_btn.clicked.connect(self.toggle_fixation_play)
        self.fixation_stream_label = qtw.QLabel("Stream: Not Connected")
        control_panel.addWidget(self.fixation_play_btn)
        control_panel.addWidget(self.fixation_stream_label)
        #control_panel.addStretch()
        layout.addLayout(control_panel)

        self.fixation_plot = pg.PlotWidget(title="Fixation Points")
        self.fixation_plot.setXRange(0, self.size().width())
        self.fixation_plot.setYRange(0, self.size().height())
        
        layout.addWidget(self.fixation_plot)
        
        # Store current fixation data
        self.current_fixations = {
            'x_coords': [],
            'y_coords': [],
            'counts': []
        }
        
        return tab
    
    def toggle_gaze_play(self):
        """toggle button for gaze plot"""
        self.is_gaze_playing = not self.is_gaze_playing
        self.gaze_play_btn.setText("Pause" if self.is_gaze_playing else "Play")
        
    def toggle_fixation_play(self):
        """toggle button for fixation plot"""
        self.is_fixation_playing = not self.is_fixation_playing
        self.fixation_play_btn.setText("Pause" if self.is_fixation_playing else "Play")
    
    def get_gaze_and_validate_data(self):
        """fetch gaze&validate data files"""
        gaze = sorted(eta_utils.get_file_names(prefix="gaze_data_"))
        validate = sorted(eta_utils.get_file_names(prefix="system_"))
        return gaze, validate

    def create_metrics_tab(self):
        """Create the metrics tab for the application."""
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

    def adjust_refresh_rate(self, value=None):
        """
        Adjusts the refresh rate of the stream thread and resets fixation plot data.
        Parameters:
        value (int, optional): The new refresh rate in Hz. If not provided, the refresh rate will not be adjusted.
        Behavior:
        - If a value is provided, the refresh rate timer interval is set to the specified value in milliseconds.
        - If the stream thread is running, its refresh rate is updated and a log message is generated.
        - Clears the fixation plot and resets the current fixation data.
        """
        if value is not None:
            self.refresh_rate_timer.setInterval(value*1000)
        
            if self.stream_thread and self.stream_thread.isRunning():
                LOGGER.info(f"Adjusting refresh rate of stream thread to {value} Hz")
                self.stream_thread.refresh_rate = value
        
        self.fixation_plot.clear()
        self.current_fixations = {'x_coords': [], 'y_coords': [], 'counts': []}

    def update_metric_tab(self):
        """update gaze and validate data files, upon called"""
        self.gaze_data_items, self.validate_data_items = self.get_gaze_and_validate_data()
        self.gaze_data.clear()
        self.gaze_data.addItems(['select gaze data'] + [f"File {idx+1}: {eta_validate.get_gaze_data_timestamp(file)}" for idx, file in enumerate(self.gaze_data_items)])
        self.validate_data.clear()
        self.validate_data.addItems(['select validation data'] + [f"File {idx+1} {eta_validate.get_validate_data_timestamp(file)}" for idx,file in enumerate(self.validate_data_items)])

    def start_stream(self):
        """
        Starts the data stream and initializes the tracker and stream threads.
        This method performs the following steps:
        1. Checks if the stream or tracker threads are already running and displays a warning if they are.
        2. Sets up tracker parameters based on the current UI settings.
        3. Initializes and starts the tracker thread with the specified parameters.
        4. Resolves the LSL stream and initializes the stream inlet.
        5. If the stream is successfully fetched, updates the UI labels and starts the stream thread.
        6. Displays a success message in the status bar if the stream starts successfully.
        7. Handles exceptions by stopping the tracker thread if necessary and displaying an error message.
        Raises:
            Exception: If there is an error starting the stream, an error message is displayed and logged.
        """
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
            self.stream_thread = StreamThread()
            self.stream_thread.set_variables(refresh_rate=self.refresh_rate_slider.value(), tracker_params=tracker_params)
            self.stream_thread.found_signal.connect(lambda msg: self.update_plot_label(msg))
            self.stream_thread.update_gaze_signal.connect(self.update_gaze_plot)
            self.stream_thread.update_fixation_signal.connect(self.update_fixation_plot)
            self.stream_thread.error_signal.connect(lambda msg: qtw.QMessageBox.critical(self, "Error", msg))
            self.stream_thread.start()
            self.update_status_bar("Stream started successfully", 1, 3000)

        except Exception as e:
            error_msg = f"Failed to start stream: {str(e)}"
            LOGGER.error(error_msg)

    def stop_stream(self):
        """
        Stops the active stream and updates the UI accordingly.
        This method stops the active stream if it is running. It first attempts to stop the tracker thread,
        updating the status bar and stream labels to indicate the stream is not connected. If an error occurs
        while stopping the tracker, it logs the error and updates the status bar with an error message.
        After stopping the tracker, it stops the stream thread, updates the status bar, and resets the play
        buttons and playing status flags for gaze and fixation streams.
        Raises:
            Exception: If an error occurs while stopping the stream or tracker.
        """
        if not self.stream_thread.isRunning():
            qtw.QMessageBox.warning(self, "Warning", "No active stream to stop.")
            return
        
        try:
            self.stream_thread.stop()
            self.stream_thread = None
            self.update_status_bar("Stream stopped successfully", 1, 3000)
            self.is_gaze_playing = False
            self.is_fixation_playing = False
            self.gaze_play_btn.setText("Play")
            self.fixation_play_btn.setText("Play")
            self.update_plot_label()
            LOGGER.warning(f"Thread count after stop stream: {threading.active_count()}")
            LOGGER.warning(f"Threads alive: {[t.name for t in threading.enumerate()]}")
        except Exception as e:
            LOGGER.error(f"Error stopping stream: {str(e)}")
            self.update_status_bar(f"Error stopping stream: {str(e)}", 0, 5000)

    def update_plot_label(self, msg="Stream: Not Connected"):
        """update the stream label with the message"""
        self.gaze_stream_label.setText(msg)
        self.fixation_stream_label.setText(msg)

    def update_gaze_plot(self, times, x, y):
        """update gaze plot with a moving time window"""
        if not times or not x or not y or not self.is_gaze_playing:
            return
        
        self.gaze_plot_x_curve.setData(times, x)
        self.gaze_plot_y_curve.setData(times, y)
        if times:
            self.gaze_plot_x.setXRange(min(times), max(times))
            self.gaze_plot_y.setXRange(min(times), max(times))

    def update_fixation_plot(self, x_coords, y_coords, counts):
        """update fixation plot with increasing size of scatter point based on counts"""
        if not self.is_fixation_playing:
            return
        max_count = [min(count, 30) for count in counts]
        scatter = pg.ScatterPlotItem(x=x_coords, y=y_coords, size=max_count, symbol='o', symbolBrush=(255, 0, 0, 150))
        self.fixation_plot.addItem(scatter)

    def update_metrics_table(self):
        """update the table with metrics calculated from gaze and validate data using `eta_validate:get_statistics()`"""
        self.update_status_bar("Calculating", 2, 3000)
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
        self.update_status_bar("Metrics generated successfully", 1, 5000)

    def download_csv(self):
        """
        Prompts the user to save the current DataFrame as a CSV file.
        If the DataFrame is empty, displays an error message and exits the function.
        Otherwise, opens a file dialog for the user to specify the save location and filename.
        Saves the DataFrame to the specified CSV file and shows a status message indicating the save location.
        Returns:
            None
        """
        if self.df.empty:
            qtw.QMessageBox.critical(self, "Error", "No data to save as CSV")
            return
        
        filename, _ = qtw.QFileDialog.getSaveFileName(self, "Save CSV", "", "CSV Files (*.csv)")
        if filename:
            self.df.to_csv(filename, index=False)
            self.update_status_bar(f"csv saved at: {os.path.abspath(filename)}", 5000)

    def closeEvent(self, event):
        LOGGER.info("close event invoked.")
        self.system_info_timer.stop()
        self.refresh_rate_timer.stop()
        if self.stream_thread and self.stream_thread.isRunning():
            self.stream_thread.stop()
            LOGGER.info("Stopping stream thread during closeEvent")
        if self.validate_thread and self.validate_thread.isRunning():
            self.validate_thread.stop()
            LOGGER.info("Stopping validate thread during closeEvent")
        
        event.accept()

@click.command(name="application")
def main():
    """
    Entry point for the Eye Tracker Analyzer application.
    This function initializes the Qt application, creates an instance of the 
    EyeTrackerAnalyzer window, displays it, and starts the application's 
    event loop.
    """
    app = qtw.QApplication(sys.argv)
    window = EyeTrackerAnalyzer()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
