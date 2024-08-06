import warnings
from typing import List, Optional

class WarningGenerator:
    def __init__(self, filter_categories: Optional[List]=None):
        self.filter_categories = filter_categories

    def generate_warning(self, message: str, category: Optional[Warning]=None):
        if category and self.filter_categories:
            if category in self.filter_categories:
                warnings.filterwarnings('ignore', message, category)
        else:
            warnings.warn(message, category=category, stacklevel=3)