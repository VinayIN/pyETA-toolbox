import click
from EyeTrackerAnalyzer.application import main as application_main
from EyeTrackerAnalyzer.components.track import main as track_main
from EyeTrackerAnalyzer.components.window import run_validation_window as window_main

@click.group()
def main():
    "Runs the scripts in the package"
    pass

main.add_command(application_main)
main.add_command(track_main)
main.add_command(window_main)