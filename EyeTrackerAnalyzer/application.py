import sys
import asyncio
import multiprocessing
import dash
from EyeTrackerAnalyzer.components.window import run_validation_window
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output

def run_async_function(async_func):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_func())
    loop.close()

app = dash.Dash(__package__, external_stylesheets=[dbc.themes.BOOTSTRAP])

app.layout = dbc.Container([
    dbc.Row(dash.html.H1("Eye Tracker Analyzer")),
    dbc.Row([
        dbc.Col(
            dbc.Row([
                dbc.Col(dash.dcc.Input(id="input-box", type="text")),
                dbc.Col(dash.html.Div(id="output-box"))
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
    Output('output-box', 'children'),
    Input('input-box', 'value')
)
def update_output(value):
    return f'Participant No: {value}'

@app.callback(
    Output('open-grid-window', 'n_clicks'),
    [Input('open-grid-window', 'n_clicks')]
)
def update_window(n_clicks):
    if n_clicks:
        print(f"executing: {run_validation_window.__name__}")
        process = multiprocessing.Process(target=run_async_function, args=(run_validation_window,))
        process.start()
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
        return "Metrics tab"
    return "No tab selected"


if __name__ == '__main__':
    app.run(debug=True)