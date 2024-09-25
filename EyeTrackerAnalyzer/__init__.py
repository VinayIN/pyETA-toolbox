from importlib.metadata import version, PackageNotFoundError
from EyeTrackerAnalyzer.components.utils import WarningGenerator
import logging

logging.basicConfig(format='%(asctime)s :: %(name)s:%(filename)s:%(lineno)d:: %(levelname)s :: %(message)s')
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.DEBUG)

WARN = WarningGenerator(
    filter_categories=[UserWarning]
)

try:
    __version__ = version('EyeTrackerAnalyzer')
except PackageNotFoundError:
    __version__ = '0.0.0dev'
__all__ = [
    'LOGGER',
    'WARN',
    '__version__'
]
print(f"Version: {__version__}")