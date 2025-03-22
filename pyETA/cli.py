import click
from pyETA.application import main as main_application
from pyETA.components.track import main as main_track
from pyETA.components.window import main as main_window
from pyETA.components.validate import main as main_validate

@click.group()
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode. (Creates debug.log file(s))",
)
@click.version_option(package_name="pyETA-toolbox")
def main(debug):
    if debug:
        from pyETA import LOGGER
        import logging
        import logging.handlers
        LOG_FORMAT = '%(asctime)s :: %(name)s:%(filename)s:%(funcName)s:%(lineno)d :: %(levelname)s :: %(message)s'
        file_handler = logging.handlers.RotatingFileHandler(
            filename="debug.log",
            mode='w',
            maxBytes=1000000, # 1MB
            encoding='utf-8', backupCount=2)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
        LOGGER.addHandler(file_handler)


main.add_command(main_application, name="application")
main.add_command(main_track, name="track")
main.add_command(main_window, name="window")
main.add_command(main_validate, name="validate")

if __name__ == "__main__":
    main()