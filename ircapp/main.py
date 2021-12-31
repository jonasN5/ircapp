import os
import sys
import webbrowser
import threading
import requests
import cherrypy
from irc.client import ServerConnection

from django import setup
from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler
from django.core.management import call_command
from django.db.utils import OperationalError

# need to add paths to sys.path to be able to import models
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
sys.path.append(os.path.join(BASE_DIR, 'ircapp'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
# Get the wsgi app to be able to load app modules
setup()

# Now we can import app modules
from core.utils.logging import clear_log
from core.models import DownloadSettings, UploadOngoing, SearchTerm


class CherryPyServer:
    """Represents the CherryPy server that will run IRCApp."""

    @staticmethod
    def _mount_static(url, root):
        """
        :param url: Relative url
        :param root: Path to static files root
        """
        config = {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': root,
            'tools.expires.on': True,
            'tools.expires.secs': 86400
        }
        cherrypy.tree.mount(None, url, {'/': config})

    def run(self, host: str, port: int, static_url: str, static_root: str):
        cherrypy.config.update({
            'server.socket_host': host,
            'server.socket_port': port,
            'engine.autoreload.on': False,
            'log.screen': True
        })
        self._mount_static(static_url, static_root)
        # cherrypy.process.plugins.PIDFile(cherrypy.engine, os.path.join(settings.BASE_DIR, 'IRCapp.pid')).subscribe()
        cherrypy.log("Loading and serving IRCApp")
        cherrypy.tree.graft(WSGIHandler())
        cherrypy.engine.start()

        obj = DownloadSettings.objects.latest('id')
        if not obj.restart:
            t = threading.Thread(target=IRCApp.open_browser())
            t.deamon = True
            t.start()
        else:
            obj.restart = False
            obj.save()

        cherrypy.engine.block()


class IRCApp:
    """
    The class to instantiate to launch IRCApp. The run method will actually start the underlying CherryPy server
    and therefore start the ircapp.
    """

    def __init__(self):
        # First we load the user config.
        self._load_config_file()

        # Configure irc
        ServerConnection.buffer_class.encoding = 'latin-1'

        # Create the ircapp data dir that will contain the sqlite database and log file.
        self._create_app_data_dir()

        # Clear the log
        clear_log()

        # Run migrations
        self._run_migrations()

    @staticmethod
    def _create_app_data_dir():
        if sys.platform == "win32":
            if not os.path.isdir(os.path.join(os.environ["LOCALAPPDATA"], "IRCApp")):
                os.makedirs(os.path.join(os.environ["LOCALAPPDATA"], "IRCApp"))
        else:
            if not os.path.isdir(os.path.join(os.path.expanduser("~"), ".IRCApp")):
                os.makedirs(os.path.join(os.path.expanduser("~"), ".IRCApp"))

    def _run_migrations(self):
        try:
            obj = DownloadSettings.objects.latest('id')
        except OperationalError:
            # Displaying stdout will result into an error in a GUI frozen application with cx freeze, that's why we
            # keep verbosity at 0
            call_command('makemigrations', verbosity=0)
            call_command('migrate', verbosity=0)
            self.populate_initial_database()
        finally:
            UploadOngoing.objects.all().delete()

    @staticmethod
    def populate_initial_database():
        """Populate the database with initial entries required to run properly."""
        _settings = DownloadSettings.objects.create()
        initial = [SearchTerm.objects.create(text="hdts"),
                   SearchTerm.objects.create(text="hd-ts"),
                   SearchTerm.objects.create(text="cam")]
        _settings.excludes.add(*initial)

    @staticmethod
    def _load_config_file():
        """Load the user preferences from the config.ini file."""
        with open(os.path.join(settings.BASE_DIR, "config.ini"), "r") as cfg:
            content = cfg.readlines()
            settings.HOST = content[0][1 + content[0].index("="):content[0].index("#")].strip(" ")
            settings.PORT = int(content[1][1 + content[1].index("="):content[1].index("#")].strip(" "))
            settings.TIME_ZONE = content[3][1 + content[3].index("="):content[3].index("#")].strip(" ")
            settings.DOWNLOAD_DIR = content[4][1 + content[4].index("="):content[4].index("#")].strip(" ")
            settings.PORT_FORWARDING = content[2][1 + content[2].index("="):content[2].index("#")].strip(" ")
            if settings.PORT_FORWARDING:
                # Check if a single port was given or a port range
                try:
                    settings.PORT_FORWARDING = int(settings.PORT_FORWARDING)
                except ValueError:
                    # Port range
                    ports = settings.PORT_FORWARDING.split('-')
                    settings.PORT_FORWARDING = (int(ports[0]), int(ports[1]))
            # If the HOST changed, we have to add it ALLOWED_HOSTS
            if settings.HOST not in settings.ALLOWED_HOSTS:
                settings.ALLOWED_HOSTS.append(settings.HOST)

    @staticmethod
    def open_browser():
        c = requests.get('http://' + settings.HOST + ':' + str(settings.PORT) + '/')
        if c.status_code == 200:
            webbrowser.open('http://' + settings.HOST + ':' + str(settings.PORT) + '/')

    @staticmethod
    def run():
        # Run the server, since it has to be the last line
        CherryPyServer().run(settings.HOST, settings.PORT, settings.STATIC_URL, settings.STATIC_ROOT)


def start_app():
    IRCApp().run()


if __name__ == '__main__':
    start_app()
