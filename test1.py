import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objs as go
import numpy as np
from datetime import datetime, timedelta

# Initialize the Dash app
app = dash.Dash(__name__)

# Initialize data
initial_time = datetime.now()
times = [initial_time - timedelta(seconds=i) for i in range(100, 0, -1)]
prices = [np.random.uniform(90, 110) for _ in range(100)]

# Define the app layout
app.layout = html.Div([
    html.H1("Live Stock Price Simulation"),
    dcc.Graph(id='live-graph', animate=True),
    dcc.Interval(
        id='graph-update',
        interval=1000,  # in milliseconds
        n_intervals=0
    )
])

# Define callback to update graph
@app.callback(
    Output('live-graph', 'figure'),
    [Input('graph-update', 'n_intervals')]
)
def update_graph(n):
    times.append(datetime.now())
    prices.append(np.random.uniform(90, 110))
    
    # Keep only the last 100 data points
    if len(times) > 100:
        times.pop(0)
        prices.pop(0)

    fig = go.Figure(
        data=[go.Scatter(
            x=times, 
            y=prices, 
            mode='lines+markers'
        )]
    )

    fig.update_layout(
        title='Stock Price Over Time',
        xaxis_title='Time',
        yaxis_title='Price',
        xaxis=dict(
            range=[min(times), max(times)],
            type='date'
        ),
        yaxis=dict(range=[min(prices) - 5, max(prices) + 5])
    )

    return fig

# Run the app
if __name__ == '__main__':
    app.run(debug=True, port=8052)