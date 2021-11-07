import threading
import cherrypy

from core.managers.download import DownloadManager
from core.managers.extraction import FileExtractor
from core.managers.upnp import UpnpManager
from core.models import *


class Dispatcher:
    """A simple centralizer that will hold all Manager instances and call their methods."""
    _instance = None  # Will hold the class instance

    def __new__(cls):
        """Implement the class as a singleton.."""
        if cls._instance is None:
            cls._instance = super(Dispatcher, cls).__new__(cls)
            cls._upnp_manager = UpnpManager()
            cls._download_manager = DownloadManager()
            cls._file_extractor = FileExtractor()
        return cls._instance

    def start_resume_downloads_on_app_launch(self):
        """Start/resume any interrupted/queued item on ircapp launch."""
        self._download_manager.start_downloads_on_app_launch()

    def start_new_download(self, **kwargs):
        """Start a new download and return the appropriate HttpResponse."""
        return self._download_manager.process_new_download(**kwargs)

    def cancel_download(self, server: str, bot: str):
        """
        Cancel an ongoing or queued download.
        :param server: required to identify the server connection
        :param bot: required to identify the specific DCC connection
        :return: None
        """
        self._download_manager.cancel_download(server, bot)

    def shutdown_server(self):
        """Shutdown the local server serving IRCApp after disconnecting from all connected irc servers."""
        self.stop_all_downloads()
        # We delay the shutdown command slightly to be able to serve the next static requests
        threading.Timer(0.5, cherrypy.engine.exit).start()

    def stop_all_downloads(self):
        """Stop all downloads."""
        self._download_manager.stop_all()

    def check_queue(self, download: DownloadOngoing):
        """Check and manage the queue when a download finished or is canceled.

        :param download: the download that just finished.
        :return: None
        """
        self._download_manager.check_queue(download=download)

    def extract_file(self, irc_app_connection):
        """Extract a file.

        :param irc_app_connection: IRCAppConnection instance
        :return: None
        """
        self._file_extractor.extract(irc_app_connection=irc_app_connection)

    @property
    def local_port(self) -> int:
        """Get a new available local port using Upnp."""
        return self._upnp_manager.get_new_port()

    @property
    def external_ip(self) -> str:
        """Get the public IP address using Upnp."""
        return self._upnp_manager.external_ip_address

    @property
    def lan_ip(self) -> str:
        """Get the LAN IP address using Upnp."""
        return self._upnp_manager.lan_ip_address

    def delete_port(self, port: int) -> None:
        """Delete a previously opened port."""
        return self._upnp_manager.delete_port(port)


# We'll call Dispatcher() on import to create the instances
Dispatcher()
