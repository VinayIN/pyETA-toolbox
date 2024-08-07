import pytest
import asyncio
import time
import random
import logging
from mne_lsl import lsl
from mne_lsl.stream import StreamLSL
import numpy as np

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def send_data(duration):
    info = lsl.StreamInfo('TestStream', 'Markers', 2, 100, 'float32', 'uid001')
    outlet = lsl.StreamOutlet(info)
    logger.debug(f"StreamOutlet: {outlet.get_sinfo()}")

    start_time = time.time()
    sent_samples = []

    while time.time() - start_time < duration:
        sample = np.array([random.randint(1, 100), random.randint(1, 100)], dtype=np.float32)
        outlet.push_sample(sample)
        logger.debug(f"Sent - timestamp:{lsl.local_clock()} sample: {sample}, shape: {sample.shape}")
        sent_samples.append(sample)
        await asyncio.sleep(0.01)
    logger.info(f"Sent samples: {len(sent_samples)}")
    return sent_samples

async def receive_data(duration):
    stream = StreamLSL(bufsize=1, stype='Markers', source_id="uid001").connect(acquisition_delay=0.001)
    logger.debug(f"Available channels types: {stream.get_channel_types()}")
    logger.debug(f"StreamInlet info: {stream.info}")

    start_time = time.time()
    received_samples = []

    while time.time() - start_time < duration:
        if stream.n_new_samples > 0:
            winsize = stream.n_new_samples / stream.info["sfreq"]
            sample, timestamp = stream.get_data(winsize=winsize)

            ch1, ch2 = sample
            logger.debug(f"Received - timestamp: {timestamp} ch1: {ch1}, ch2: {ch2}, shape: {sample.shape}")
            received_samples.append((ch1, ch2))
        await asyncio.sleep(0.001)
    
    stream.disconnect()
    logger.info(f"Received samples: {len(received_samples)}")
    return received_samples

@pytest.mark.asyncio
async def test_data_transmission():
    sender_task = asyncio.create_task(send_data(duration=5))
    await asyncio.sleep(0.1)
    receiver_task = asyncio.create_task(receive_data(duration=6))
    
    # Wait for both tasks to complete
    sent_samples, received_samples = await asyncio.gather(sender_task, receiver_task)
    data_loss = abs(len(sent_samples) - len(received_samples))/len(sent_samples)
    logger.info(f"Data loss: {data_loss*100}%")
    assert data_loss <=.5, f"Data loss ({data_loss*100}%). Sent: {len(sent_samples)}, Received: {len(received_samples)}"
    