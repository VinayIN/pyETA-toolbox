"""
Main entry point for running the pyETA application as a package.
"""
import sys
from pyETA.application import main as main_application

if __name__ == '__main__':
    sys.exit(main_application())
