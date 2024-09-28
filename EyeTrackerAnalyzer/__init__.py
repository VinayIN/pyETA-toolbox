from importlib.metadata import version, PackageNotFoundError
import logging
import os

logging.basicConfig(format='%(asctime)s :: %(name)s:%(filename)s:%(lineno)d:: %(levelname)s :: %(message)s')
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

try:
    __version__ = version('EyeTrackerAnalyzer')
except PackageNotFoundError:
    __version__ = '0.0.0dev'

__datapath__ = os.path.join(os.getcwd(), 'eta_data')
__all__ = [
    'LOGGER',
    '__version__',
    '__datapath__'
]