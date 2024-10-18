from importlib.metadata import version
import logging
import os

logging.basicConfig(format='%(asctime)s :: %(name)s:%(filename)s:%(lineno)d:: %(levelname)s :: %(message)s')
formatter = logging.Formatter(fmt='%(asctime)s :: %(name)s:%(filename)s:%(lineno)d:: %(levelname)s :: %(message)s')
handler = logging.FileHandler(f"log.log", mode='w', encoding='utf-8')
handler.setFormatter(formatter)
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
LOGGER.addHandler(handler)


__version__ = version('pyETA')
__datapath__ = os.path.join(os.getcwd(), 'eta_data')
__all__ = [
    'LOGGER',
    '__version__',
    '__datapath__'
]