from EyeTrackerAnalyzer.components.utils import WarningGenerator
import queue

WARN = WarningGenerator(
    filter_categories=[UserWarning]
)
MESSAGE_QUEUE = queue.Queue()

__version__ = '1.0.0'
__all__ = [
    'WARN',
    'MESSAGE_QUEUE',
    '__version__'
]