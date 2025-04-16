from importlib.metadata import version, PackageNotFoundError
import logging
import os

try:
    __version__ = version("pyETA-toolbox")
except PackageNotFoundError:
    __version__ = "0.1.1"

__datapath__ = os.path.join(os.path.join(os.path.expanduser("~/Documents"), "pyETA"), "eta_data")

os.makedirs(__datapath__, exist_ok=True)

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