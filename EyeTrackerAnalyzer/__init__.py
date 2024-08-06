from EyeTrackerAnalyzer.components.utils import WarningGenerator
import queue

WARN = WarningGenerator(
    filter_categories=[UserWarning]
)
MESSAGE_QUEUE = queue.Queue()

__all__ = [
    'WARN',
    'MESSAGE_QUEUE'
]