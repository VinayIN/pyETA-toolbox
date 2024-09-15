import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import numpy as np
import plotly.graph_objs as go
import pylsl
from collections import deque

# Initialize the Dash app
app = dash.Dash(__name__)

# Store gaze data using a deque (efficient for adding and removing elements)
max_data_points = 5000
gaze_data = {
    'left_gaze_x': deque(maxlen=max_data_points),
    'left_gaze_y': deque(maxlen=max_data_points),
    'right_gaze_x': deque(maxlen=max_data_points),
    'right_gaze_y': deque(maxlen=max_data_points)
}

# Set up the layout
app.layout = html.Div([
    dcc.Graph(id='gaze-graph'),
    dcc.Interval(id='interval-component', interval=100, n_intervals=0)  # Update every 100 ms (no initial trigger)
])

# Initialize LSL stream
streams = pylsl.resolve_streams(wait_time=1)
inlet = pylsl.StreamInlet(streams[0])
print(inlet.info().name())

# Callback to update the graph
@app.callback(Output('gaze-graph', 'figure'),
              Input('interval-component', 'n_intervals'))
def update_graph(n):
    if n == 0:  # Skip first call to avoid initial empty data
        return {}  # Return empty dict to avoid unnecessary update

    sample, _ = inlet.pull_sample()

    # Extract gaze data
    screen_width = sample[6]
    screen_height = sample[7]
    gaze_data['left_gaze_x'].append(int(sample[0] * screen_width))
    gaze_data['left_gaze_y'].append(int(sample[1] * screen_height))
    gaze_data['right_gaze_x'].append(int(sample[3] * screen_width))
    gaze_data['right_gaze_y'].append(int(sample[4] * screen_height))

    # Create a scatter plot
    figure = go.Figure()

    # Add left eye gaze points
    figure.add_trace(go.Scatter(
        x=list(gaze_data['left_gaze_x']),
        y=list(gaze_data['left_gaze_y']),
        mode='markers',
        name='Left Eye',
        marker=dict(size=10, color='blue')
    ))

    # Add right eye gaze points
    figure.add_trace(go.Scatter(
        x=list(gaze_data['right_gaze_x']),
        y=list(gaze_data['right_gaze_y']),
        mode='markers',
        name='Right Eye',
        marker=dict(size=10, color='red')
    ))

    # Set graph layout
    figure.update_layout(
        xaxis=dict(range=[0, screen_width]),
        yaxis=dict(range=[screen_height, 0]),
        title='Gaze Data',
        xaxis_title='Screen Width',
        yaxis_title='Screen Height',
    )

    return figure

# Run the app
if __name__ == '__main__':
    app.run(debug=True, port=8051)