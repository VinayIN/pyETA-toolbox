from importlib.metadata import version
import logging
import os

__version__ = version("pyETA-toolbox")
__datapath__ = os.path.join(os.getcwd(), 'eta_data')
CONSOLE_LOG_FORMAT = '%(asctime)s :: %(filename)s:%(lineno)d :: %(levelname)s :: %(message)s'
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(CONSOLE_LOG_FORMAT))

LOGGER.addHandler(console_handler)

__all__ = [
    'LOGGER',
    '__version__',
    '__datapath__'
]
LOGGER.debug(f"pyETA version: {__version__}")
LOGGER.debug(f"Data path: {__datapath__}")