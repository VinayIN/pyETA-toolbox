from EyeTrackerAnalyzer.components.utils import WarningGenerator

WARN = WarningGenerator(
    filter_categories=[UserWarning]
)

__version__ = '1.0.0'
__all__ = [
    'WARN',
    '__version__'
]
print(f"Version: {__version__}")