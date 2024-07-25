import sys
import asyncio
import multiprocessing
from EyeTrackerAnalyzer.component.window import run_validation_window
import dash_bootstrap_components as dbc
from dash import Dash, html, dcc
from dash.dependencies import Input, Output

def run_async_function(async_func):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_func())
    loop.close()

app = Dash(__package__, external_stylesheets=[dbc.themes.BOOTSTRAP])

app.layout = dbc.Container([
    dbc.Row(dbc.Col(html.H1("Eye Tracker Analyzer"))),
    dbc.Row(dbc.Col(html.Button("Open Grid", id="open-grid-window"))),
    dbc.Row(dbc.Col(dcc.Input(id="input-box", type="text"))),
    dbc.Row(dbc.Col(html.Div(id="output-box")))
])

@app.callback(
    Output('output-box', 'children'),
    Input('input-box', 'value')
)
def update_output(value):
    return f'Input: {value}'

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


if __name__ == '__main__':
    app.run(debug=True)