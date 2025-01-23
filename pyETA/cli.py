import click
import pyETA.application_runner as application_runner
import pyETA.application as application
import pyETA.components.track as track
import pyETA.components.window as window

@click.group()
@click.version_option()
def main():
    "Runs the scripts in the package"
    pass

main.add_command(application_runner.main)
main.add_command(application.main)
main.add_command(track.main)
main.add_command(window.main)