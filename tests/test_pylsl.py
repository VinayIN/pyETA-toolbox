import pytest
import pylsl
import asyncio
import time
import random
from pyETA import LOGGER

async def send_data(duration):
    info = pylsl.StreamInfo('TestStream', 'Markers', 1, 100, 'string', 'myuid34234')
    outlet = pylsl.StreamOutlet(info)

    start_time = time.time()
    sent_samples = []

    while time.time() - start_time < duration:
        sample = [f"test_pylsl_{random.randint(1, 1000)}"]
        outlet.push_sample(sample)
        sent_samples.extend(sample)
        await asyncio.sleep(0.01)
    LOGGER.info(f"Sent sample: {len(sent_samples)}")
    return sent_samples

async def receive_data(duration):
    streams = pylsl.resolve_streams(wait_time=1)
    inlet = pylsl.StreamInlet(streams[0])

    start_time = time.time()
    received_samples = []

    while time.time() - start_time < duration:
        try:
            sample, timestamp = inlet.pull_sample(timeout=0.01)
            if sample:
                received_samples.extend(sample)
        except Exception as e:
            print(f"Error receiving data: {e}")
        await asyncio.sleep(0.01)
    LOGGER.info(f"Received sample: {len(received_samples)}")
    return received_samples

@pytest.mark.asyncio
async def test_data_transmission():
    sender_task = asyncio.create_task(send_data(duration=5))
    await asyncio.sleep(0.1)
    receiver_task = asyncio.create_task(receive_data(duration=6))

    # Wait for both tasks to complete
    sent_samples, received_samples = await asyncio.gather(sender_task, receiver_task)
    data_loss = abs(len(sent_samples) - len(received_samples))/len(sent_samples)
    LOGGER.info(f"Data loss: {data_loss*100}%")
    assert data_loss <=.5, f"Data loss ({data_loss*100}%). Sent: {len(sent_samples)}, Received: {len(received_samples)}"