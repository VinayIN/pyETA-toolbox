import sys
import os
import re
import asyncio
import multiprocessing
import dash
import datetime
from EyeTrackerAnalyzer import WARN, MESSAGE_QUEUE
try:
    from EyeTrackerAnalyzer.components.window import run_validation_window
    from EyeTrackerAnalyzer.components.tobii import Tobii
except ModuleNotFoundError:
    WARN.generate_warning(
        "Without tobii_research & PyQt6 library, Validation of eye-tracker won't work.",
        category=UserWarning)
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

def run_async_function(async_func):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_func())
    loop.close()

def run_tobii():
    tobii_process = Tobii(save_data=True, verbose=True)
    tobii_process.start_tracking(duration=10)

app = dash.Dash(
    __package__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True)

app.layout = dbc.Container([
    dbc.Row(dash.html.H1("Eye Tracker Analyzer")),
    dbc.Row([
        dbc.Col(
            dbc.Row([
                dash.dcc.Markdown(
                    '''
                    This interface allows you to validate the eye tracker accuracy along with the following:
                    - View gaze points
                    - View fixation points
                    - View eye tracker accuracy
                        * Comparing the gaze data with validation grid locations.
                    '''
                ),
            ])),
        dbc.Col(
            dbc.Row([
                dbc.Button("Validate Eye Tracker", id="open-grid-window")
            ])),
        ]),
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
    Output('open-grid-window', 'n_clicks'),
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
    return n_clicks

@app.callback(
    Output("tab-content", "children"),
    [Input("tabs", "active_tab"), Input("store", "data")],
)
def render_tab_content(active_tab, data):
    if active_tab == "eye-tracker-gaze":
        print("plotting gaze points")
        return "Gaze tab"
    elif active_tab == "eye-tracker-fixation":
        print("plotting fixation points")
        return "Fixation tab"
    elif active_tab == "eye-tracker-metrics":
        print("plotting metrics")
        return render_metrics_tab()
    return "No tab selected"

def get_file_names(prefix):
    return [f for f in os.listdir('data/') if f.startswith(prefix)]

def render_metrics_tab():
    gaze_files = get_file_names("gaze_data_")
    validation_files = get_file_names("validation_")

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
            dbc.Button("Analyze", id="analyze-button"),
            dash.html.Div(id='graph-output')
        ])
    ])

@app.callback(
    Output('dropdown-output', 'children'),
    [Input('gaze-data-dropdown', 'value'),
     Input('validation-data-dropdown', 'value')]
)
def update_dropdown(gaze_data, validation_data):
    ts_gaze_data = "-"
    ts_validation_data = "-"
    if gaze_data:
        ts_gaze_data = re.search(r"gaze_data_(.*).json", gaze_data).group(1)
        ts_gaze_data = datetime.datetime.strptime(ts_gaze_data, "%Y%m%d_%H%M%S")
    if validation_data:
        ts_validation_data = re.search(r"validation_(.*).json", validation_data).group(1)
        ts_validation_data = datetime.datetime.strptime(ts_validation_data, "%Y%m%d_%H%M%S")
    return dbc.Row([
        dbc.Col(f"Timestamp: {ts_gaze_data}"),
        dbc.Col(f"Timestamp: {ts_validation_data}")
    ])

@app.callback(
    Output('graph-output', 'children'),
    [Input('analyze-button', 'n_clicks')],
    [Input('gaze-data-dropdown', 'value'),
     Input('validation-data-dropdown', 'value')]
)
def update_graph(n_clicks, gaze_data, validation_data):
    if n_clicks and gaze_data and validation_data:
        return dash.dcc.Graph(figure={
            'data': [
                {'x': [1, 2, 3], 'y': [4, 1, 2], 'type': 'bar', 'name': 'Gaze Data'},
                {'x': [1, 2, 3], 'y': [2, 4, 5], 'type': 'bar', 'name': 'Validation Data'},
            ],
            'layout': {
                'title': 'Gaze Data vs Validation Data'
            }
        })

if __name__ == '__main__':
    app.run(debug=True)