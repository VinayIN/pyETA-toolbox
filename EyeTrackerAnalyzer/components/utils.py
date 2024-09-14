import warnings
import sys
import platform
import datetime
from typing import List, Optional
import PyQt6.QtWidgets as qtw

def get_current_screen_size():
    app = qtw.QApplication.instance()
    if app is None:
        app = qtw.QApplication(sys.argv)

    screen = app.primaryScreen()
    size = screen.size()
    width, height = size.width(), size.height()
    return width, height

def get_system_info():
    node = platform.node()
    system = platform.system()
    machine = platform.machine()
    width, height = get_current_screen_size()
    return f"{node}_{system}_{machine}_{width}x{height}"

def get_timestamp():
    return datetime.datetime.now().timestamp()

class WarningGenerator:
    def __init__(self, filter_categories: Optional[List]=None):
        self.filter_categories = filter_categories

    def generate_warning(self, message: str, category: Optional[Warning]=None):
        if category and self.filter_categories:
            if category in self.filter_categories:
                warnings.filterwarnings('ignore', message, category)
        else:
            warnings.warn(message, category=category, stacklevel=3)