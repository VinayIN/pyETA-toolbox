import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import pylsl
from collections import deque
import datetime

# Initialize the Dash app
app = dash.Dash(__name__)

# Store gaze data using deques
max_data_points = 1000*60*2
times = deque(maxlen=max_data_points)
left_gaze_x = deque(maxlen=max_data_points)
left_gaze_y = deque(maxlen=max_data_points)

# Buffer for collecting data between renders
buffer_times = []
buffer_x = []
buffer_y = []

# Set up the layout
app.layout = html.Div([
    html.H1("Live Gaze Data Visualization"),
    dcc.Graph(id='live-graph', animate=False),
    dcc.Interval(
        id='graph-update',
        interval=300,  # in milliseconds
        n_intervals=0
    ),
    html.Button('Clear Graph', id='clear-button')  # Add clear button here
])

# Initialize LSL stream
streams = pylsl.resolve_streams(wait_time=1)
inlet = pylsl.StreamInlet(streams[0])
print(f"Connected to stream: {inlet.info().name()}")

# Callback to update graph
@app.callback(
    Output('live-graph', 'figure'),
    [Input('graph-update', 'n_intervals'), Input('clear-button', 'n_clicks')]
)
def update_graph(n, clear_clicks):
    global buffer_times, buffer_x, buffer_y
    if n == 0 or clear_clicks:  # Clear data on first run or button click
        times.clear()
        left_gaze_x.clear()
        left_gaze_y.clear()
        buffer_times, buffer_x, buffer_y = [], [], []  # Clear buffers as well

    # Collect all available samples
    while True:
        sample, timestamp = inlet.pull_sample(timeout=0.0)
        if sample is None:
            break

        current_time = datetime.datetime.fromtimestamp(sample[8])
        screen_width = sample[6]
        screen_height = sample[7]
        gaze_x = int(sample[0] * screen_width)
        gaze_y = int(sample[1] * screen_height)

        buffer_times.append(current_time)
        buffer_x.append(gaze_x)
        buffer_y.append(gaze_y)

    # Update deques with buffered data
    times.extend(buffer_times)
    left_gaze_x.extend(buffer_x)
    left_gaze_y.extend(buffer_y)

    # Clear buffers
    buffer_times, buffer_x, buffer_y = [], [], []

    # Create figure
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=list(times),
        y=list(left_gaze_x),
        mode='lines',
        name='Gaze X'
    ))

    fig.add_trace(go.Scatter(
        x=list(times),
        y=list(left_gaze_y),
        mode='lines',
        name='Gaze Y'
    ))

    # Update layout
    fig.update_layout(
        title='Left Eye Gaze Data Over Time',
        xaxis=dict(
            title='Timestamp',
            range=[min(times), max(times)],
            type='date'
        ),
        yaxis=dict(
            title='Gaze Position',
            range=[0, max(screen_height, screen_width)]
        ),
        showlegend=True
    )

    return fig

# Run the app
if __name__ == '__main__':
    app.run(debug=True, port=8051)