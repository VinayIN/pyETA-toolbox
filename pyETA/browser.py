import multiprocessing.process
import os
import re
import time
import psutil
import asyncio
import multiprocessing
import atexit
import dash
import datetime
import pandas as pd
from pyETA import __version__, __datapath__, LOGGER
from pyETA.components.window import run_validation_window
from pyETA.components.track import Tracker
import pyETA.components.utils as eta_utils
import pyETA.components.validate as eta_validate
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pylsl
import pathlib
import click
import pyETA.components.reader as eta_reader
from threading import Thread

class Variable:
    inlet = None
    metrics_df = pd.DataFrame()
    reader = eta_reader.GazeReader()
    stream_thread = None
    width, height = eta_utils.get_current_screen_size()

    def refresh_gaze(self):
        if self.stream_thread and self.stream_thread.is_alive():
            self.reader.stop()
            self.stream_thread.join()
            self.reader = eta_reader.GazeReader()
            self.start_stream_thread()

    def start_stream_thread(self):
        if self.inlet and not (self.stream_thread and self.stream_thread.is_alive()):
            self.reader.running = True
            self.stream_thread = Thread(
                target=self.reader.read_stream,
                args=(self.inlet,),
                daemon=True
            )
            self.stream_thread.start()
            LOGGER.info("Started gaze data streaming thread")

    def stop_stream_thread(self):
        if self.stream_thread and self.stream_thread.is_alive():
            self.reader.stop()
            self.stream_thread.join()
            LOGGER.info("Stopped gaze data streaming thread")


def run_async_function(async_func):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_func())
    loop.close()

var = Variable()
process_manager = eta_utils.ProcessStatus()
app = dash.Dash(
    __package__,
    external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True
)
app.title = "Eye Tracker Analyzer"
app._favicon = "favicon.ico"

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            dash.html.H1("Toolbox - Eye Tracker Analyzer", className="my-4 text-muted"),
            dash.html.A([
                    dbc.Badge("Faculty 1", color="secondary", class_name='me-2'),
                    dash.html.Strong("Neuroadaptive Human-Computer Interaction", className="text-muted"),
                    dash.html.P("Brandenburg University of Technology (Cottbus-Senftenberg)", className="text-muted")
                ],
                href="https://www.b-tu.de/en/fg-neuroadaptive-hci/",
                style={"text-decoration": "none"},
                target="_blank"
            )
        ]),
        dbc.Col(
            dbc.ButtonGroup([
                dbc.Button(href="/", color="secondary", outline=True, class_name="bi bi-house-door-fill"),
                dbc.Button(href="/docs", color="secondary", outline=True, disabled=True, class_name="bi bi-book"),
            ], class_name="float-end"),
            width="auto"
        ),
    ], class_name="mb-4"),
    dash.html.Hr(),
    dbc.Row([
        dbc.Col([
            dash.dcc.Markdown(
                f"""
                pyETA, Version: `{__version__}`

                This interface allows you to validate the eye tracker accuracy along with the following:
                - View gaze points
                - View fixation points
                - View eye tracker accuracy
                    * Comparing the gaze data with validation grid locations.
                """,
                className="mb-4"
            ),
        ]),
        dbc.Col([
            dbc.Card(dbc.CardBody([
                dbc.Row([
                    dash.html.Div(id='lsl-status'),
                    dash.dcc.Interval(id='status-interval', interval=1000, n_intervals=0),
                    dash.html.Div(id='process-error'),
                    dbc.Col([
                        dash.dcc.RadioItems(
                            options=[
                                {"label": " Mock", "value": "mock"},
                                {"label": " Eye-Tracker", "value": "eye-tracker"}
                            ],
                            value='eye-tracker',
                            id="tracker-type"
                        ),
                        dbc.Label("Data Rate (Hz)"),
                        dash.dcc.Slider(
                            min=0, step=100, max=800, value=600,
                            id="tracker-data-rate",
                        ),
                        dash.dcc.Checklist(
                            options=[
                                {"label": " Enable Fixation", "value": "fixation"},
                            ],
                            value=["fixation"],
                            id="fixation-options",
                        ),
                        dbc.Label("Velocity Threshold", className="my-2"),
                        dbc.Input(id="fixation-velocity", type="number", value=1.5),
                        dash.dcc.Checklist(
                            options=[
                                {"label": " Push to stream (tobii_gaze_fixation)", "value": "push_stream"},
                                {"label": " Accept screen NaN (default: 0)", "value": "accept_screen_nans"},
                                {"label": " Verbose", "value": "verbose"}
                            ],
                            value=["push_stream"],
                            id="tracker-extra-options",
                        )
                    ]),
                    dbc.Col([
                        dbc.ButtonGroup([
                            dbc.Button("Start - lsl Stream", color="success", outline=True, id="start_lsl_stream"),
                            dbc.Button("Stop - lsl Stream", color="danger", outline=True, id="stop_lsl_stream")
                        ], vertical=True),
                    ], class_name="align-self-center", width="auto"),
                ])
            ])),
            dbc.Row([
                dbc.Col([
                    dash.dcc.RadioItems(
                        options=[
                            {"label": " Mock", "value": "mock"},
                            {"label": " Eye-Tracker", "value": "eye-tracker"}
                        ],
                        value='eye-tracker',
                        id="validation-tracker-type",
                    ),
                    dbc.Button(
                        "Validate Eye Tracker",
                        color="secondary",
                        outline=True,
                        id="open-grid-window",
                    )
                ]),
            ], class_name="mt-4")
        ])
    ]),
    dbc.Spinner([
        dash.dcc.Store(id="stream-store", data={"inlet": None, "message": "Not connected to stream"}),
        dbc.Button("Fetch tobii_gaze_fixation Stream", color="secondary", outline=True, id="fetch_stream", class_name="my-2"),
        dash.html.Div(id="stream-status")],
        delay_show=100
    ),
    dbc.Tabs([
        dbc.Tab(label="Gaze points", tab_id="eye-tracker-gaze"),
        dbc.Tab(label="Fixation", tab_id="eye-tracker-fixation"),
        dbc.Tab(label="Metrics", tab_id="eye-tracker-metrics")  
    ],
    id="tabs",
    active_tab="eye-tracker-gaze",
    class_name="mb-4"),
    dash.html.Div(id="tab-content", className="p-4"),
    dash.html.Footer([
        dbc.Col([
            dash.html.A(
                    dash.html.I(className="bi bi-github"),
                    href="https://github.com/VinayIN/EyeTrackerAnalyzer",
                    target="_blank"
                ),
        ], class_name="float-end my-4"),
    ])
], fluid=True, class_name="p-4")

@app.callback(
    Output('open-grid-window', 'value'),
    [Input('open-grid-window', 'n_clicks'),
     Input('validation-tracker-type', 'value')]
)
def update_window(n_clicks, value):
    if n_clicks:
        tracker_params = {
            'use_mock': value == "mock",
            'fixation': False,
            'verbose': False,
            'push_stream': False,
            'save_data': True,
            'duration': (9*(2000+1000))/1000 + (2000*3)/1000 + 2000/1000
        }
        with multiprocessing.Pool(processes=2) as pool:
            tobii_result = pool.apply_async(run_tracker, args=(tracker_params,))
            validation_result = pool.apply_async(run_validation_window)
            validation_result.get()
            tobii_result.get()
        LOGGER.info("validation window closed")
        return 1
    return 0

def run_tracker(params):
    try:
        duration = params.get("duration")
        tracker = Tracker(**params)
        if duration is not None:
            LOGGER.info(f"Total Duration: {duration}")
        tracker.start_tracking(duration=duration)
    except Exception as e:
        LOGGER.error(f"Tracker error: {str(e)}")

@app.callback(
    Output("start_lsl_stream", "value"),
    Output("process-error", "children"),
    [
        Input("start_lsl_stream", "n_clicks"),
        Input("tracker-type", "value"),
        Input("tracker-data-rate", "value"),
        Input("fixation-options", "value"),
        Input("fixation-velocity", "value"),
        Input("tracker-extra-options", "value"),
    ],
    prevent_initial_call=True
)
def start_lsl_stream(n_clicks, tracker_type, data_rate, fixation, velocity, extra_options):
    if not n_clicks:
        return None, None
        
    try:
        if process_manager.active_processes:
            return None, dbc.Alert(
                "Another tracking process is already running. Please stop it first.",
                color="warning",
                dismissable=True
            )

        tracker_params = {
            'data_rate': data_rate or 600,
            'use_mock': tracker_type == "mock",
            'fixation': "fixation" in fixation,
            'velocity_threshold': velocity,
            'accept_screen_nans': "accept_screen_nans" in extra_options,
            'verbose': "verbose" in extra_options,
            'push_stream': "push_stream" in extra_options,
            'save_data': False
        }

        ctx = multiprocessing.get_context('spawn')
        process = ctx.Process(
            target=run_tracker,
            args=(tracker_params,),
            daemon=True
        )
        
        process.start()
        time.sleep(1)
        if not process.is_alive():
            return None, dbc.Alert(
                "Process failed to start.",
                color="danger",
                dismissable=True
            )

        process_manager.add_process(process.pid, process)
        LOGGER.info(f"Started tracking process with PID {process.pid}")
        
        return process.pid, None
    
    except Exception as e:
        error_msg = f"Failed to start tracking process: {str(e)}"
        LOGGER.error(error_msg)
        return None, dbc.Alert(error_msg, color="danger", dismissable=True)

@app.callback(
    Output("lsl-status", "children"),
    [
        Input("start_lsl_stream", "value"),
        Input("stop_lsl_stream", "value"),
        Input("status-interval", "n_intervals")
    ]
)
def update_lsl_status(pid, stop_message, n_intervals):
    if stop_message:
        return dbc.Alert(f"{stop_message} (Refresh the page)", color="warning", dismissable=True)
    if not pid:
        return dbc.Alert("Not Running", color="warning", dismissable=True)
    
    try:        
        # Get process info
        process_info = process_manager.get_process_info(pid)
        if not process_info:
            return dbc.Alert("Process not found in manager", color="danger", dismissable=True)
        
        # Check process status using psutil
        try:
            process = psutil.Process(pid)
            if not process.is_running():
                return dbc.Alert("Process not running", color="danger", dismissable=True)
            
            if process.status() == psutil.STATUS_ZOMBIE:
                return dbc.Alert("Process Zombie (Need restart)", color="danger", dismissable=True)
            
            # Get process metrics
            memory_info = process.memory_info()
            cpu_percent = process.cpu_percent()
            storage_free = psutil.disk_usage(os.getcwd()).free / 1024**3
            runtime = datetime.datetime.now() - process_info['start_time']
            
            return dbc.Alert(
                [
                    dash.html.Div([
                        dash.html.Strong("Status: "), "Running",
                        dash.html.Br(),
                        dash.html.Strong("PID: "), str(pid),
                        dash.html.Br(),
                        dash.html.Strong("Runtime: "), f"{runtime.seconds}s",
                        dash.html.Br(),
                        dash.html.Strong("Memory: "), f"{memory_info.rss / 1024 / 1024:.1f} MB",
                        dash.html.Br(),
                        dash.html.Strong("Storage avail: "), f"{storage_free} GB",
                        dash.html.Br(),
                        dash.html.Strong("CPU: "), f"{cpu_percent:.1f}%"
                    ])
                ],
                color="success",
                dismissable=True
            )
            
        except psutil.NoSuchProcess:
            process_manager.remove_process(pid)
            return dbc.Alert("Process terminated unexpectedly", color="danger", dismissable=True)
            
    except Exception as e:
        LOGGER.error(f"Error monitoring process: {str(e)}")
        return dbc.Alert(f"Monitoring error: {str(e)}", color="danger", dismissable=True)

@app.callback(
    Output("stop_lsl_stream", "value"),
    [Input("stop_lsl_stream", "n_clicks"), Input("start_lsl_stream", "value")],
    allow_duplicate=True
)
def stop_lsl_stream(n_clicks, pid):
    if not (n_clicks and pid):
        return 0
        
    try:
        process = psutil.Process(pid)
    
        process.terminate()
        try:
            process.wait(timeout=3)
        except psutil.TimeoutExpired:
            LOGGER.warning(f"Process {pid} did not terminate within timeout, forcing kill")
            process_manager.cleanup()
            return f"Process {pid} did not terminate within timeout, forcing kill"
            
        process_manager.remove_process(pid)
        LOGGER.info(f"Process with PID {pid} stopped successfully")
        return f"Stopped successfully PID: {pid}"
        
    except psutil.NoSuchProcess:
        LOGGER.info(f"Process with PID {pid} not found")
        process_manager.remove_process(pid)
        return f"PID: {pid} not found"
    except Exception as e:
        error_msg = f"Error stopping process {pid}: {str(e)}"
        LOGGER.error(error_msg)
        return error_msg

@app.callback(
    Output("tab-content", "children"),
    [Input("tabs", "active_tab")],
)
def render_tab_content(active_tab):
    if active_tab == "eye-tracker-gaze":
        LOGGER.info("plotting gaze points")
        return render_tab(tab_type="gaze")
    elif active_tab == "eye-tracker-fixation":
        LOGGER.info("plotting fixation points")
        return render_tab(tab_type="fixation")
    elif active_tab == "eye-tracker-metrics":
        LOGGER.info("plotting metrics")
        return render_metrics_tab()
    return "No tab selected"

def render_tab(tab_type):
    return dbc.Card(dbc.CardBody(
        dbc.Row(
            [
                dash.html.H3(f"Live Visualization: {tab_type.capitalize()} points", className="mb-3"),
                dash.html.Hr(),
                dbc.Col(
                    dbc.Button("Refresh", color="warning", outline=True, id="refresh", class_name="bi bi-arrow-clockwise"),
                    width="auto",
                    class_name="mb-3"
                ),
                dash.html.Div(id=f'live-graph-{tab_type}'),
                dash.dcc.Interval(id=f'graph-update-{tab_type}', interval=300, n_intervals=0),
            ]
        )
    ))

@app.callback(
    Output('refresh', 'n_clicks'),
    [Input('refresh', 'n_clicks')],
    prevent_initial_call=True
)
def clear_data(n_clicks):
    if n_clicks:
        LOGGER.info("Refresh button clicked")
        var.refresh_gaze()
        var.reader.clear_data()
    return n_clicks

def get_available_stream():
    message = "No fetching performed"
    try:
        LOGGER.info("Fetching stream")
        streams = pylsl.resolve_streams(wait_time=1)
        inlet = pylsl.StreamInlet(streams[0])
        message = f"Connected to stream: {inlet.info().name()}"
        expected_name = "tobii_gaze_fixation"
        if inlet.info().name() == expected_name:
            return inlet, message
        message = f"Invalid stream name. Expected: {expected_name}"
        return None, message
    except Exception as e:
        message = f"No stream found. Error: {e}"
    return None, message

@app.callback(
    Output("stream-store", "data"),
    [Input("fetch_stream", "n_clicks")],
    prevent_initial_call=True,
)
def get_inlet(n_clicks):
    if n_clicks:
        if var.inlet is None:
            var.inlet, message = get_available_stream()
            name = var.inlet.info().name() if var.inlet else None
            if var.inlet:
                var.start_stream_thread()
            LOGGER.info(message)
        else:
            name = var.inlet.info().name()
            message = "Already connected to stream"
        return {"inlet": name, "message": message}
    return {"inlet": None, "message": "Not connected to stream"}

@app.callback(
    Output("stream-status", "children"),
    [Input("stream-store", "data")]
)
def update_stream_status(data):
    inlet_name = data["inlet"]
    message = data["message"]
    if inlet_name is not None:
        return dbc.Alert(f"Success ({message})", color="success", dismissable=True)
    return dbc.Alert(f"Failed ({message})", color="danger", dismissable=True)


@app.callback(
    Output('live-graph-gaze', 'children'),
    [   
        Input('graph-update-gaze', 'n_intervals'),
        Input("stream-store", "data")
    ],
)
def update_graph_gaze(n_intervals, data):
    """
    Updates the gaze graph with data retrieved from the GazeGraphUpdater.
    """
    if data["inlet"] is not None:
        times, x, y = var.reader.get_data()

        fig = go.Figure(skip_invalid=True)
        if times:
            fig.add_trace(go.Scatter(x=list(times), y=list(x), mode='lines', name='Gaze X'))
            fig.add_trace(go.Scatter(x=list(times), y=list(y), mode='lines', name='Gaze Y'))

            fig.update_layout(
                title='Eye Gaze Data Over Time',
                xaxis=dict(title='Timestamp', range=[min(times), max(times)], type='date'),
                yaxis=dict(title='Gaze Position', range=[0, max(max(x, default=0), max(y, default=0))]),
                showlegend=True
            )
        return dbc.Card(dbc.CardBody(dash.dcc.Graph(figure=fig)))

    return dbc.Alert("Did you start `lsl stream`? or clicked the button `Fetch tobii_gaze_fixation stream`?",
                     color="danger", dismissable=True)

@app.callback(
    Output('live-graph-fixation', 'children'),
    [
        Input('graph-update-fixation', 'n_intervals'),
        Input("stream-store", "data")
    ],
)
def update_graph_fixation(n_intervals, data):
    """
    Updates the fixation graph with data retrieved from the GazeReader.
    Shows fixation points with bubble sizes proportional to fixation duration.
    """
    if data["inlet"] is not None:
        fixation_points = var.reader.get_data(fixation=True)
        
        fig = go.Figure(skip_invalid=True)
        if fixation_points:
            x_coords, y_coords, counts = zip(*fixation_points)
            normalized_sizes = [min(count, 100)  for count in counts]
            
            fig.add_trace(go.Scatter(
                x=x_coords,
                y=y_coords,
                mode='markers',
                marker=dict(
                    size=normalized_sizes,
                    sizemode='diameter',
                    color='rgba(255, 0, 0, 0.6)',
                    line=dict(color='red', width=3)
                ),
                name='Gaze point'
            ))

            fig.update_layout(
                title='Eye Fixation Tracker',
                xaxis=dict(title='Screen Width', range=[0, var.width]),
                yaxis=dict(title='Screen Height', range=[var.height, 0]),
                showlegend=True,
                plot_bgcolor='white'
            )
            
            return dbc.Card(dbc.CardBody(dash.dcc.Graph(figure=fig)))

    return dbc.Alert(
        "Did you start `lsl stream`? or clicked the button `Fetch tobii_gaze_fixation stream`?",
        color="danger", dismissable=True
    )

def render_metrics_tab():
    gaze_files = eta_utils.get_file_names("gaze_data_")
    validation_files = eta_utils.get_file_names("system_")

    return dbc.Card(
        dbc.CardBody(
            dbc.Row([
                dash.html.H3("Statistics: Eye Tracker Validation", className="mb-3"),
                dash.dcc.Markdown(
                    f'''
                    Searching Data files at path: `{__datapath__}`
                    '''
                ),
                dbc.Row([
                    dbc.Col(dash.dcc.Dropdown(
                        id='gaze-data-dropdown',
                        options=[{'label': pathlib.Path(f).name, 'value': f} for f in gaze_files],
                        placeholder="Select Gaze Data File"
                    )),
                    dbc.Col(dash.dcc.Dropdown(
                        id='validation-data-dropdown',
                        options=[{'label': pathlib.Path(f).name, 'value': f} for f in validation_files],
                        placeholder="Select Validation File"
                    )),
                ]),
                dash.html.Div(id='dropdown-output', className="my-2"),
                dbc.Button("Analyze", color="success", outline=True, id="analyze-button", class_name="mb-2"),
                dash.html.Hr(),
                dash.html.Div(id='graph-output')
            ])
        )
    )

@app.callback(
    Output('download-metrics-csv', 'data'),
    Input('download-metrics-btn', 'n_clicks'),
    prevent_initial_call=True
)
def download_data(n_clicks):
    if n_clicks > 0:
        return dash.dcc.send_data_frame(var.metrics_df.to_csv, f"validation_metrics_{eta_utils.get_timestamp()}.csv")

@app.callback(
    Output('dropdown-output', 'children'),
    [Input('gaze-data-dropdown', 'value'), Input('validation-data-dropdown', 'value')]
)
def update_dropdown(gaze_data, validation_data):
    ts_gaze_data = "-"
    info_validation_data = "-"
    if gaze_data:
        ts_gaze_data = re.search(r"gaze_data_(.*).json", gaze_data).group(1)
        ts_gaze_data = datetime.datetime.strptime(ts_gaze_data, "%Y%m%d_%H%M%S")
    if validation_data:
        info = re.search(r"system_(.*).json", validation_data).group(1)
        info = info.split("_")
        ts_validation_data = datetime.datetime.strptime("_".join(info[-2:]), "%Y%m%d_%H%M%S")
        info_validation_data = " | ".join(info[:-2]) + f" | {ts_validation_data}"
    return dbc.Row(
        [
        dbc.Col(dash.html.I(f"Selected Gaze Data Timestamp: {ts_gaze_data}")),
        dbc.Col(dash.html.I(f"Selected System Information: {info_validation_data}"))
        ]
    )

@app.callback(
    Output('graph-output', 'children'),
    [Input('analyze-button', 'n_clicks'),
     Input('gaze-data-dropdown', 'value'),
     Input('validation-data-dropdown', 'value')]
)
def update_graph_metrics(n_clicks, gaze_data, validation_data):
    if n_clicks and gaze_data and validation_data:
        var.metrics_df = eta_validate.get_statistics(gaze_data, validation_data).astype(str)
        content = dbc.Alert(
            "No data available for the selected files",
            color="danger", dismissable=True)
        if not var.metrics_df.empty:
            content = [
                    dash.dash_table.DataTable(
                        data = var.metrics_df.to_dict('records'),
                        id='metrics-table',
                        style_table={'width': '100%', 'overflowX': 'auto'},
                        style_cell={'textAlign': 'center', 'minWidth': '120px', 'whiteSpace': 'normal'},
                        style_header={'fontWeight': 'bold'},
                    ),
                    dbc.Button("Download", id="download-metrics-btn", color="success", outline=True, class_name="my-2"),
                    dash.dcc.Download(id="download-metrics-csv")
                ]
        return dbc.Card(
            dbc.CardBody(content, class_name="table-responsive"),
            class_name="mt-3"
        )
    return dbc.Alert(
                "Choose appropriate files combination to analyze the eye tracker data",
                color="info", dismissable=True)


@click.command(name="browser")
@click.option('--debug', type=bool, is_flag=True, help="debug mode")
@click.option('--port', type=int, default=8050, help="port number")
def main(debug: bool, port: int):
    def cleanup():
        var.stop_stream_thread()
        process_manager.cleanup()
    
    atexit.register(cleanup)
    
    try:
        app.run(debug=debug, port=port)
    finally:
        cleanup()

if __name__ == '__main__':
    main()