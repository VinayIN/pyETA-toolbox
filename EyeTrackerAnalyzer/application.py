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
                                            {"label": " Add Fixation duration", "value": "fixation"},
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
                    dbc.Row(dash.dcc.RadioItems(options=[{"label": " Mock", "value": "mock"}, {"label": " Eye-Tracker", "value": "eye-tracker"}], value='mock', id="validation-tracker-type")),
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
    [Input('open-grid-window', 'n_clicks'),
     Input('validation-tracker-type', 'value')]
)
def update_window(n_clicks, value):
    if n_clicks:
        print(f"executing: {run_validation_window.__name__}")
        tracker_params = {
            'data_rate': 600,
            'use_mock': True if value == "mock" else False,
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
    duration = None
    tracker = Tracker(
        data_rate=params['data_rate'],
        use_mock=params['use_mock'],
        fixation=params['fixation'],
        screen_nans=not params['dont_screen_nans'],
        verbose=params['verbose'],
        push_stream=params['push_stream'],
        save_data=params['save_data']
    )
    if params["duration"] is not None:
        duration = params["duration"]
        print(f"Totat Duration: {duration}")
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
        use_mock = True if tracker_type == "mock" else False
        fixation = True if "fixation" in extra_options else False
        push_stream = True if "push_stream" in extra_options else False
        dont_screen_nans = True if "dont_screen_nans" in extra_options else False
        data_rate = data_rate if data_rate else 600
        verbose = True if "verbose" in extra_options else False

        tracker_params = {
            'data_rate': data_rate,
            'use_mock': use_mock,
            'fixation': fixation,
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
        return render_tab(tab_type="gaze")
    elif active_tab == "eye-tracker-fixation":
        print("plotting fixation points")
        return render_tab(tab_type="fixation")
    elif active_tab == "eye-tracker-metrics":
        print("plotting metrics")
        return render_metrics_tab()
    return "No tab selected"


def render_tab(tab_type):
    return dbc.Container([
        dbc.Row([
            dash.html.H3(f"Live Visualization: {tab_type.capitalize()} points"),
            dbc.Button("Fetch tobii_gaze Stream", color="info", disabled=False, outline=True, id="fetch_stream", class_name="my-2"),
            dbc.Col([
                dbc.Button('Clear/Refresh', color="danger", outline=True, id="clear-button", class_name="mx-4"),
                dbc.Button(f"Load ({tab_type.capitalize()} Visualization)", color="primary", outline=True, id=f"collect_{tab_type}_points", class_name="mx-4"),
            ], class_name="my-4"),
            dash.html.Hr(),
            dash.html.Div(id=f'live-graph-{tab_type}'),
            dash.dcc.Interval(id=f'graph_update_{tab_type}', interval=300, n_intervals=0),
        ])
    ])

@app.callback(
    Output('clear-button', 'n_clicks'),
    [Input('clear-button', 'n_clicks')],
    prevent_initial_call=True
)
def clear_data(n_clicks):
    if n_clicks:
        print("clear button clicked")
        var.refresh()
    return n_clicks


def get_available_stream():
    var.refresh()
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
    Output("fetch_stream", "value"),
    [Input("fetch_stream", "n_clicks")],
    prevent_initial_call=True
)
def get_inlet(n_clicks):
    if n_clicks:
        inlet, message = get_available_stream()
        print(message)
        return inlet
    return None


@app.callback(
    Output('live-graph-gaze', 'children'),
    [Input("collect_gaze_points", "n_clicks"),
     Input("fetch_stream", "value")],
)
def update_graph_gaze(n_clicks, inlet):
    if n_clicks:
        if inlet is not None:
            while True:
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
            fig = go.Figure()
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
        print("update_graph_gaze")
        return dash.dcc.Markdown("Did you start `lsl stream`?/ clicked the button `Fetch tobii_gaze stream`?")
    return dash.dcc.Markdown("Click the button to load the graph")

def get_file_names(prefix):
    return [f for f in os.listdir('data/') if f.startswith(prefix)]

def render_metrics_tab():
    gaze_files = get_file_names("gaze_data_")
    validation_files = get_file_names("system_")

    return dbc.Container([
        dbc.Row([
            dash.html.H3("Statistics: Eye Tracker Validation"),
            dash.html.Hr(),
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
    Output('live-graph-fixation', 'children'),
    [Input("collect_fixation_points", "n_clicks"),
     Input("fetch_stream", "value")],
)
def update_graph_fixation(n_clicks, inlet):
    if n_clicks:
        if inlet is not None:
            pass
        print("update_graph_fixation")
        return dash.dcc.Markdown("Did you start `lsl stream`?/ clicked the button `Fetch tobii_gaze stream`?")
    return dash.dcc.Markdown("Click the button to load the graph")

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
    [Input('analyze-button', 'n_clicks'),
     Input('gaze-data-dropdown', 'value'),
     Input('validation-data-dropdown', 'value')]
)
def update_graph_metrics(n_clicks, gaze_data, validation_data):
    if n_clicks:
        pass
    return dash.html.Div()


if __name__ == '__main__':
    app.run(debug=True)