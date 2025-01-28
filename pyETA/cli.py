import click
from pyETA.application import main as main_application
from pyETA.browser import main as main_browser
from pyETA.components.track import main as main_track
from pyETA.components.window import main as main_window
from pyETA.components.validate import main as main_validate

@click.group()
@click.version_option()
def main():
    "Runs the scripts in the package"
    pass

main.add_command(main_application, name="application")
main.add_command(main_browser, name="browser")
main.add_command(main_track, name="track")
main.add_command(main_window, name="window")
main.add_command(main_validate, name="validate")

if __name__ == "__main__":
    main()