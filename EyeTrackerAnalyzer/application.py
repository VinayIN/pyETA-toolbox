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
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output
import plotly.express as px
import plotly.graph_objs as go
from collections import deque
import pylsl

class Variable:
    # Store gaze data using deques
    max_data_points = 1000*60*2
    times = deque(maxlen=max_data_points)
    left_gaze_x = deque(maxlen=max_data_points)
    left_gaze_y = deque(maxlen=max_data_points)

    # Buffer for collecting data between renders
    buffer_times = []
    buffer_x = []
    buffer_y = []

    def refresh(self):
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

def run_tobii():
    tobii_process = Tracker(
        use_mock=True,
        screen_nans=True,
        save_data=True,
        push_stream=False,
        verbose=False)
    duration = (9*(2000+1000))/1000 + (2000*3)/1000 + 2000/1000
    print(f"Totat Duration: {duration}")
    tobii_process.start_tracking(duration)

app = dash.Dash(
    __package__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True)

app.layout = dbc.Container([
    dash.html.H1("Eye Tracker Analyzer", className="text-center my-4"),
    dash.html.Hr(),
    dbc.Row([
        dbc.Col(
            dbc.Row([
                dash.dcc.Markdown(
                    f'''
                    version: `{__version__}`


                    This interface allows you to validate the eye tracker accuracy along with the following:
                    - View gaze points
                    - View fixation points
                    - View eye tracker accuracy
                        * Comparing the gaze data with validation grid locations.
                    '''
                ),
            ])),
        dbc.Col(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    dbc.Row(dash.dcc.RadioItems(options=[{"label": " Mock", "value": "mock"}, {"label": " Eye-Tracker", "value": "eye-tracker"}], value='mock', id="tracker-type")),
                                    dbc.Row(dbc.Label("Data Rate (Hz)", width="auto")),
                                    dbc.Row(dash.dcc.Slider(min=0, max=800, value=600, id="tracker-data-rate")),
                                    dbc.Row(dash.dcc.Checklist(
                                        options=[
                                            {"label": " Push to stream (tobii_gaze)", "value": "push_stream"},
                                            {"label": " Remove screen NaN (default: 0)", "value": "dont_screen_nans"},
                                            {"label": " Verbose", "value": "verbose"}
                                        ],
                                        value=["push_stream", "dont_screen_nans"], id="tracker-extra-options"))
                                ]
                            ),
                            dbc.Col(
                                [
                                    dbc.Row(dbc.Button("Start - lsl Stream", color="primary", disabled=False, outline=True, id="start_lsl_stream"), class_name="my-4"),
                                    dbc.Row(dbc.Button("Stop - lsl Stream", color="danger", disabled=False, outline=True, id="stop_lsl_stream"), class_name="my-4")
                                ], class_name="align-self-center")
                        ]
                    ),
                    dash.html.Hr(),
                    dbc.Row([dbc.Button("Validate Eye Tracker", color="secondary", disabled=False, outline=True, id="open-grid-window")], className='my-4')
                ]),
        ],),
    dbc.Tabs([
        dbc.Tab(label="Gaze points", tab_id="eye-tracker-gaze"),
        dbc.Tab(label="Fixation", tab_id="eye-tracker-fixation"),
        dbc.Tab(label="Metrics", tab_id="eye-tracker-metrics")  
    ],
    id="tabs",
    active_tab="eye-tracker-gaze"),
    dbc.Spinner(
            [
                dash.dcc.Store(id="store"),
                dash.html.Div(id="tab-content", className="p-4"),
            ],
            delay_show=100,
        ),
])


@app.callback(
    Output('open-grid-window', 'value'),
    [Input('open-grid-window', 'n_clicks')]
)
def update_window(n_clicks):
    if n_clicks:
        print(f"executing: {run_validation_window.__name__}")
        with multiprocessing.Pool(processes=2) as pool:
            tobii_result = pool.apply_async(run_tobii)
            validation_result = pool.apply_async(run_validation_window)
            tobii_result.get()
            validation_result.get()
        print("validation window closed")
        return 1
    return 0

def run_tracker(params):
    tracker = Tracker(
        data_rate=params['data_rate'],
        use_mock=params['use_mock'],
        screen_nans=not params['dont_screen_nans'],
        verbose=params['verbose'],
        push_stream=params['push_stream'],
        save_data=params['save_data']
    )
    tracker.start_tracking()

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
        use_mock = True if tracker_type == "mock" else False
        push_stream = True if "push_stream" in extra_options else False
        dont_screen_nans = True if "dont_screen_nans" in extra_options else False
        data_rate = data_rate if data_rate else 600
        verbose = True if "verbose" in extra_options else False

        tracker_params = {
            'data_rate': data_rate,
            'use_mock': use_mock,
            'dont_screen_nans': dont_screen_nans,
            'verbose': verbose,
            'push_stream': push_stream,
            'save_data': False
        }

        process = multiprocessing.Process(target=run_tracker, args=(tracker_params,), daemon=True)
        process.start()
        return process.pid
    return None

@app.callback(
    Output("stop_lsl_stream", "n_clicks"),
    [Input("stop_lsl_stream", "n_clicks"), Input("start_lsl_stream", "value")])
def stop_lsl_stream(n_clicks, pid):
    if n_clicks and pid:
        try:
            os.kill(pid, signal.SIGINT)
            print(f"Process with PID {pid} stopped.")
            return n_clicks
        except ProcessLookupError:
            print(f"Process with PID {pid} not found.")
    return 0

@app.callback(
    [Output("start_lsl_stream", "disabled"), Output("stop_lsl_stream", "disabled")],
    [Input("start_lsl_stream", "value")]
)
def update_button_states(pid):
    if pid:
        return True, False
    return False, True

@app.callback(
    Output("tab-content", "children"),
    [Input("tabs", "active_tab"), Input("store", "data")],
)
def render_tab_content(active_tab, data):
    if active_tab == "eye-tracker-gaze":
        print("plotting gaze points")
        return render_gaze_tab()
    elif active_tab == "eye-tracker-fixation":
        print("plotting fixation points")
        return render_fixation_tab()
    elif active_tab == "eye-tracker-metrics":
        print("plotting metrics")
        return render_metrics_tab()
    return "No tab selected"


@app.callback(
    Output("clear-button", "n_clicks"),
    Input("clear-button", "n_clicks")
    )
def clear_variables(n_clicks):
    if n_clicks:
        var.refresh()
    return n_clicks

def render_gaze_tab():
    return dbc.Container(
        dbc.Row(
            [
                dash.html.H1("Live Gaze Data Visualization"),
                dbc.Col([
                    dbc.Button('Clear Graph', color="danger", outline=True, disabled=False, id='clear-button', class_name="mx-4"),
                    dbc.Button("Fetch (Gaze points)", color="primary", outline=True, disabled=False, id="collect_gaze_point", class_name="mx-4"),
                ]),
                dash.dcc.Graph(id='live-graph', animate=False),
                dash.dcc.Interval(
                    id='graph-update',
                    interval=300,
                    n_intervals=0
                ),
            ]))

@app.callback(
    Output("collect_gaze_point", "inlet"),
    Input("collect_gaze_point", "n_clicks")
)
def fetch_gaze_stream(n_clicks):
    if n_clicks:
        var.refresh()
        try:
            print("fetching stream")
            streams = pylsl.resolve_streams(wait_time=1)
            inlet = pylsl.StreamInlet(streams[0])
            print(f"Connected to stream: {inlet.info().name()}")
            if inlet.info().name() != "tobii_gaze":
                print("Invalid stream name. Expected: tobii_gaze")
                return None
        except Exception:
            print("No stream found.")
            return None
        return inlet
    return None

@app.callback(
    Output('live-graph', 'figure'),
    [Input("collect_gaze_point", "inlet")],
)
def update_gaze_graph(inlet):
    fig = go.Figure()
    while True:
        if inlet is None:
            return fig
        sample, _ = inlet.pull_sample(timeout=0.0)
        if sample is None:
            break

        current_time = datetime.datetime.fromtimestamp(sample[8])
        screen_width = sample[6]
        screen_height = sample[7]
        gaze_x = int(sample[0] * screen_width)
        gaze_y = int(sample[1] * screen_height)

        var.buffer_times.append(current_time)
        var.buffer_x.append(gaze_x)
        var.buffer_y.append(gaze_y)

    var.times.extend(var.buffer_times)
    var.left_gaze_x.extend(var.buffer_x)
    var.left_gaze_y.extend(var.buffer_y)
    var.buffer_times, var.buffer_x, var.buffer_y = [], [], []

    fig.add_trace(go.Scatter(
        x=list(var.times),
        y=list(var.left_gaze_x),
        mode='lines',
        name='Gaze X'
    ))

    fig.add_trace(go.Scatter(
        x=list(var.times),
        y=list(var.left_gaze_y),
        mode='lines',
        name='Gaze Y'
    ))

    fig.update_layout(
        title='Eye Gaze Data Over Time',
        xaxis=dict(
            title='Timestamp',
            range=[min(var.times), max(var.times)],
            type='date'
        ),
        yaxis=dict(
            title='Gaze Position',
            range=[0, max(screen_height, screen_width)]
        ),
        showlegend=True
    )
    return fig

def render_fixation_tab():
    return dbc.Container([
            dbc.Row([dbc.Button("Fetch (Modified Gaze points)", outline=True, color="primary", disabled=True, id="append-gaze-point")], className='my-2')
        ])

def get_file_names(prefix):
    return [f for f in os.listdir('data/') if f.startswith(prefix)]

def render_metrics_tab():
    gaze_files = get_file_names("gaze_data_")
    validation_files = get_file_names("system_")

    return dbc.Container([
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
        dbc.Row([
            dash.html.Div(id='dropdown-output'),
            dbc.Button("Analyze", color="success", disabled=False, outline=True, id="analyze-button"),
            dash.html.Div(id='graph-output')
        ])
    ])

@app.callback(
    Output('dropdown-output', 'children'),
    [Input('gaze-data-dropdown', 'value')]
)
def update_dropdown(gaze_data):
    ts_gaze_data = "-"
    if gaze_data:
        ts_gaze_data = re.search(r"gaze_data_(.*).json", gaze_data).group(1)
        ts_gaze_data = datetime.datetime.strptime(ts_gaze_data, "%Y%m%d_%H%M%S")
    return dbc.Row([
        dbc.Col(f"Timestamp: {ts_gaze_data}")
    ])

@app.callback(
    Output('graph-output', 'children'),
    [Input('analyze-button', 'n_clicks')],
    [Input('gaze-data-dropdown', 'value'),
     Input('validation-data-dropdown', 'value')]
)
def update_graph(n_clicks, gaze_data, validation_data):
    if n_clicks:
        pass
    return dash.html.Div()


if __name__ == '__main__':
    app.run(debug=True)