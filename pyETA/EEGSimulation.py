import time
import random
import math
from pylsl import StreamInfo, StreamOutlet

def generate_eeg_sample(base_time):
    """
    Generate a sample of EEG-like data based on synchronized sine waves.
    """
    num_channels = 64
    base_frequency = 20  # Hz (base frequency of the sine wave)
    sample = []

    for i in range(num_channels):
        # Randomize amplitude for each channel to simulate differences
        base_amplitude = random.uniform(5, 20)  # Base amplitude between 5 and 20
        noise = random.uniform(-2, 2)  # Random noise between -2 and 2
        amplitude = base_amplitude + noise  # Add noise to amplitude
        phase_shift = random.uniform(0, math.pi / 4)  # Slight phase variation
        channel_value = amplitude * math.sin(base_frequency * base_time + phase_shift)
        sample.append(channel_value)

    return sample

def simulate_eeg_stream():
    # Create an LSL stream info (64 EEG channels, sampling rate 256 Hz, float32 format)
    sampling_rate = 256
    info = StreamInfo('SimulatedEEG', 'EEG', 64, sampling_rate, 'float32', 'eeg_sim_001')
    outlet = StreamOutlet(info)

    print("Simulated EEG stream started.")

    base_time = 0  # Initialize base time for sine wave generation
    sampling_interval = 1.0 / sampling_rate

    while True:
        sample = generate_eeg_sample(base_time)
        outlet.push_sample(sample)
        base_time += sampling_interval  # Increment base time for sine wave generation
        time.sleep(sampling_interval)  # Push data at 256 Hz

if __name__ == "__main__":
    simulate_eeg_stream()
