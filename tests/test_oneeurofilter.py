import datetime
import pytest
import math
import random
from pyETA.components.utils import OneEuroFilter
from pyETA import LOGGER

def generate_synthetic_data(num_points, noise_amplitude=0.1, frequency=1):
    data = []
    current_time = datetime.datetime.now()
    for i in range(num_points):
        t = current_time + datetime.timedelta(seconds=i * 0.1)
        x = math.sin(2 * math.pi * frequency * i * 0.1) + noise_amplitude * (2 * random.random() - 1)
        data.append((t.timestamp(), x))
    return data

def test_one_euro_filter():
    # Generate synthetic data
    synthetic_data = generate_synthetic_data(100)
    one_euro_filter = OneEuroFilter(synthetic_data[0][0], synthetic_data[0][1])

    # Apply the filter to the synthetic data
    filtered_values = []
    for t, value in synthetic_data[1:]:
        filtered_value = one_euro_filter(t, value)
        filtered_values.append(filtered_value)
    
    # Check that the filtered values are smoother than the original data
    original_diff = [abs(synthetic_data[i+1][1] - synthetic_data[i][1]) for i in range(len(synthetic_data)-1)]
    filtered_diff = [abs(filtered_values[i+1] - filtered_values[i]) for i in range(len(filtered_values)-1)]
    LOGGER.info(f"Original diff: {sum(original_diff)}, Filtered diff: {sum(filtered_diff)}")
    assert sum(filtered_diff) < sum(original_diff), "Filtered data should be smoother than original data"