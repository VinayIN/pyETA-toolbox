import sys
import os
import re
import asyncio
import multiprocessing
import signal
import dash
import datetime
import numpy as np
import pandas as pd
from EyeTrackerAnalyzer import WARN, __version__
from EyeTrackerAnalyzer.components.window import run_validation_window
from EyeTrackerAnalyzer.components.track import Tracker
import EyeTrackerAnalyzer.components.utils as eta_utils
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import plotly.express as px
import plotly.graph_objs as go
from collections import deque
import pylsl

class Variable:
    inlet = None
    max_data_points = 1000 * 60 * 2
    times = deque(maxlen=max_data_points)
    left_gaze_x = deque(maxlen=max_data_points)
    left_gaze_y = deque(maxlen=max_data_points)
    buffer_times, buffer_x, buffer_y = [], [], []

    def refresh_gaze(self):
        self.times.clear()
        self.left_gaze_x.clear()
        self.left_gaze_y.clear()
        self.buffer_times, self.buffer_x, self.buffer_y = [], [], []


var = Variable()

def run_async_function(async_func):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_func())
    loop.close()

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
                Version: `{__version__}`

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
                    dbc.Col([
                        dash.dcc.RadioItems(
                            options=[
                                {"label": " Mock", "value": "mock"},
                                {"label": " Eye-Tracker", "value": "eye-tracker"}
                            ],
                            value='mock',
                            id="tracker-type"
                        ),
                        dbc.Label("Data Rate (Hz)"),
                        dash.dcc.Slider(
                            min=0, step=100, max=800, value=600,
                            id="tracker-data-rate",
                        ),
                        dash.dcc.Checklist(
                            options=[
                                {"label": " Push to stream (tobii_gaze)", "value": "push_stream"},
                                {"label": " Add Fixation duration", "value": "fixation"},
                                {"label": " Remove screen NaN (default: 0)", "value": "dont_screen_nans"},
                                {"label": " Verbose", "value": "verbose"}
                            ],
                            value=["push_stream", "dont_screen_nans"],
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
                        value='mock',
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
        dbc.Button("Fetch tobii_gaze Stream", color="secondary", outline=True, id="fetch_stream", class_name="my-2"),
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
        print(f"executing: {run_validation_window.__name__}")
        tracker_params = {
            'data_rate': 600,
            'use_mock': value == "mock",
            'fixation': False,
            'dont_screen_nans': True,
            'verbose': False,
            'push_stream': False,
            'save_data': True,
            'duration': (9*(2000+1000))/1000 + (2000*3)/1000 + 2000/1000
        }
        with multiprocessing.Pool(processes=2) as pool:
            tobii_result = pool.apply_async(run_tracker, args=(tracker_params,))
            validation_result = pool.apply_async(run_validation_window)
            tobii_result.get()
            validation_result.get()
        print("validation window closed")
        return 1
    return 0

def run_tracker(params):
    duration = params.get("duration")
    tracker = Tracker(
        data_rate=params['data_rate'],
        use_mock=params['use_mock'],
        fixation=params['fixation'],
        screen_nans=not params['dont_screen_nans'],
        verbose=params['verbose'],
        push_stream=params['push_stream'],
        save_data=params['save_data']
    )
    if duration is not None:
        print(f"Total Duration: {duration}")
    tracker.start_tracking(duration=duration)

@app.callback(
    Output("start_lsl_stream", "value"),
    [
        Input("start_lsl_stream", "n_clicks"),
        Input("tracker-type", "value"),
        Input("tracker-data-rate", "value"),
        Input("tracker-extra-options", "value"),
    ]
)
def start_lsl_stream(n_clicks, tracker_type, data_rate, extra_options):
    if n_clicks:
        tracker_params = {
            'data_rate': data_rate or 600,
            'use_mock': tracker_type == "mock",
            'fixation': "fixation" in extra_options,
            'dont_screen_nans': "dont_screen_nans" in extra_options,
            'verbose': "verbose" in extra_options,
            'push_stream': "push_stream" in extra_options,
            'save_data': False
        }

        process = multiprocessing.Process(target=run_tracker, args=(tracker_params,), daemon=True)
        process.start()
        return process.pid
    return None

@app.callback(
    Output("lsl-status", "children"),
    [
        Input("start_lsl_stream", "value"),
        Input("stop_lsl_stream", "value"),
    ]
)
def update_lsl_status(pid, stop_val):
    if stop_val == 1:
        return dbc.Alert("Stopped (Refresh the browser)", color="danger", dismissable=True)
    if pid:
        return dbc.Alert(f"Starting (PID: {pid})", color="success", dismissable=True)
    return dbc.Alert("Not Running", color="warning", dismissable=True)

@app.callback(
    Output("stop_lsl_stream", "value"),
    [Input("stop_lsl_stream", "n_clicks"), Input("start_lsl_stream", "value")],
    allow_duplicate=True
)
def stop_lsl_stream(n_clicks, pid):
    if n_clicks and pid:
        try:
            os.kill(pid, signal.SIGINT)
            print(f"Process with PID {pid} stopped.")
            return 1
        except ProcessLookupError:
            print(f"Process with PID {pid} not found.")
    return 0


@app.callback(
    [Output("start_lsl_stream", "disabled"), Output("stop_lsl_stream", "disabled")],
    [Input("start_lsl_stream", "value")]
)
def update_button_states(pid):
    return bool(pid), not bool(pid)

@app.callback(
    Output("tab-content", "children"),
    [Input("tabs", "active_tab")],
)
def render_tab_content(active_tab):
    if active_tab == "eye-tracker-gaze":
        print("plotting gaze points")
        return render_tab(tab_type="gaze")
    elif active_tab == "eye-tracker-fixation":
        print("plotting fixation points")
        return render_tab(tab_type="fixation")
    elif active_tab == "eye-tracker-metrics":
        print("plotting metrics")
        return render_metrics_tab()
    return "No tab selected"

def render_tab(tab_type):
    return dbc.Card(dbc.CardBody(
        dbc.Row(
            [
                dash.html.H3(f"Live Visualization: {tab_type.capitalize()} points", className="mb-3"),
                dash.html.Hr(),
                dbc.Col(
                    dbc.Button("Refresh", color="warning", outline=True, id=f"refresh-{tab_type}", class_name="bi bi-arrow-clockwise"),
                    width="auto",
                    class_name="mb-3"
                ),
                dash.html.Div(id=f'live-graph-{tab_type}'),
                dash.dcc.Interval(id=f'graph-update-{tab_type}', interval=300, n_intervals=0),
            ]
        )
    ))

@app.callback(
    Output('refresh-gaze', 'n_clicks'),
    [Input('refresh-gaze', 'n_clicks')],
    prevent_initial_call=True
)
def clear_data(n_clicks):
    if n_clicks:
        print("Refresh button clicked gaze")
        var.refresh_gaze()
    return n_clicks

def get_available_stream():
    message = "No fetching performed"
    try:
        print("Fetching stream")
        streams = pylsl.resolve_streams(wait_time=1)
        inlet = pylsl.StreamInlet(streams[0])
        message = f"Connected to stream: {inlet.info().name()}"
        expected_name = "tobii_gaze"
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
            print(message)
        else:
            name = var.inlet.info().name()
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
    if data["inlet"] is not None:
        while True:
            sample, _ = var.inlet.pull_sample(timeout=0.0)
            if sample is None:
                break

            current_time = datetime.datetime.fromtimestamp(sample[8])
            screen_width, screen_height = sample[6], sample[7]
            gaze_x = int(sample[0] * screen_width)
            gaze_y = int(sample[1] * screen_height)

            var.buffer_times.append(current_time)
            var.buffer_x.append(gaze_x)
            var.buffer_y.append(gaze_y)
        
        var.times.extend(var.buffer_times)
        var.left_gaze_x.extend(var.buffer_x)
        var.left_gaze_y.extend(var.buffer_y)
        var.buffer_times, var.buffer_x, var.buffer_y = [], [], []

        fig = go.Figure(skip_invalid=True)
        fig.add_trace(go.Scatter(x=list(var.times), y=list(var.left_gaze_x), mode='lines', name='Gaze X'))
        fig.add_trace(go.Scatter(x=list(var.times), y=list(var.left_gaze_y), mode='lines', name='Gaze Y'))

        if len(var.times) > 0:
            fig.update_layout(
                title='Eye Gaze Data Over Time',
                xaxis=dict(title='Timestamp', range=[min(var.times), max(var.times)], type='date'),
                yaxis=dict(title='Gaze Position', range=[0, max(screen_height, screen_width)]),
                showlegend=True
            )
        return dbc.Card(dbc.CardBody(dash.dcc.Graph(figure=fig)))
    return dbc.Alert("Did you start `lsl stream`? or clicked the button `Fetch tobii_gaze stream`?",
                     color="danger", dismissable=True)

def get_file_names(prefix):
    if os.path.exists('data/'):
        return [f for f in os.listdir('data/') if f.startswith(prefix)]
    return []

def render_metrics_tab():
    gaze_files = get_file_names("gaze_data_")
    validation_files = get_file_names("system_")

    return dbc.Card(
        dbc.CardBody(
            dbc.Row([
                dash.html.H3("Statistics: Eye Tracker Validation", className="mb-3"),
                dbc.Row([
                    dbc.Col(dash.dcc.Dropdown(
                        id='gaze-data-dropdown',
                        options=[{'label': f, 'value': f} for f in gaze_files],
                        placeholder="Select Gaze Data File"
                    )),
                    dbc.Col(dash.dcc.Dropdown(
                        id='validation-data-dropdown',
                        options=[{'label': f, 'value': f} for f in validation_files],
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
    Output('live-graph-fixation', 'children'),
    [Input("stream-store", "data")],
)
def update_graph_fixation(data):
    if data["inlet"] is not None:
        pass
    return dbc.Alert(
        "Did you start `lsl stream`? or clicked the button `Fetch tobii_gaze stream`?",
        color="danger", dismissable=True)

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
        info_validation_data = re.search(r"system_(.*).json", validation_data).group(1)
        info_validation_data = re.sub(r'_', " | ", info_validation_data)
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
        return dbc.Card(
            dbc.CardBody([
                dash.html.H4("Eye Tracker Metrics Analysis"),
                dash.html.P(f"Analysis based on: {gaze_data} and {validation_data}")
            ]),
            class_name="mt-3"
        )
    return dbc.Alert(
                "Choose appropriate files combination to analyze the eye tracker data",
                color="info", dismissable=True)

if __name__ == '__main__':
    app.run(debug=True)