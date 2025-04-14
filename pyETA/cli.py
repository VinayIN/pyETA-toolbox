import click
import os
import platform
import subprocess
import sys
import shutil
from pathlib import Path
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


@click.command(help="Build executables for the current platform (.exe for Windows, .app for macOS)")
def exe():
    try:
        import os
        import sys
        import subprocess
        from pathlib import Path
        
        click.echo("Starting Briefcase build for pyETA-toolbox...")

        import briefcase
        
        # Build the application using briefcase directly
        current_platform = platform.system().lower()
        
        click.echo("Creating the application...")
        subprocess.run(["briefcase", "create"], check=True)
        
        if current_platform == "darwin":
            click.echo("Building macOS application...")
            subprocess.run(["briefcase", "build", "macOS"], check=True)
            click.echo("Packaging macOS application...")
            subprocess.run(["briefcase", "package", "macOS"], check=True)
            
            click.echo("\nBuild completed successfully!")
            click.echo("Your .app file can be found in the 'macOS/app' directory")
        elif current_platform == "windows":
            click.echo("Building Windows application...")
            subprocess.run(["briefcase", "build", "windows"], check=True)
            click.echo("Packaging Windows application...")
            subprocess.run(["briefcase", "package", "windows"], check=True)
            
            click.echo("\nBuild completed successfully!")
            click.echo("Your .exe file can be found in the 'windows/app' directory")
        else:
            click.echo(f"Platform {current_platform} not supported for packaging")
            
            
    except ImportError:
        click.echo("Briefcase is not installed. Please install it with 'pip install briefcase'")
    except subprocess.CalledProcessError as e:
        click.echo(f"Error during build process: {e}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"Unexpected error: {e}")
        sys.exit(1)

main.add_command(exe)

if __name__ == "__main__":
    main()