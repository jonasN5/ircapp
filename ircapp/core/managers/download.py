import random
import string
import threading
import cherrypy
import os
import platform
import subprocess
import ssl

from irc.client import ServerConnectionError
from irc.connection import Factory
from dataclasses import dataclass, field
from typing import Dict, Optional
from django.http import HttpResponse, JsonResponse

from core.client import IRCAppClient
from core.ircapp_connection import IRCAppConnection
from core.utils.logging import log
from core.utils.directory import get_free_space_mb
from core.models import *


@dataclass
class IRCAppClients:
    clients: Dict[str, IRCAppClient] = field(default_factory=dict)

    def add_client(self, irc_app_client: IRCAppClient):
        self.clients[self.get_client_key(irc_app_client)] = irc_app_client

    def remove_client(self, irc_app_client: IRCAppClient):
        server = irc_app_client.server
        if server in self.clients:
            del self.clients[server]

    @staticmethod
    def get_client_key(irc_app_client: IRCAppClient) -> str:
        return irc_app_client.server

    def get_client(self, server: str) -> Optional[IRCAppClient]:
        return self.clients.get(server, None)


class DownloadManager:
    """
    This class is responsible for managing the download queue and start downloads. It will be used as a Singleton.
    """

    # Store all IRCAppClient instances, e.g. server connections.
    irc_app_clients = IRCAppClients()

    # Used to cancel an ongoing server connection {'client_id'}
    cancel_server_connection_signals = set()

    def __init__(self):
        # Start any previous download
        threading.Timer(1, self.start_downloads_on_app_launch).start()

    def start_downloads_on_app_launch(self):
        """Start/resume any interrupted/queued item on ircapp launch."""
        log("Resuming interrupted downloads")
        checklist = []
        if DownloadOngoing.objects.all().exists():
            if not DownloadOngoing.objects.filter(active=True).exists():
                DownloadOngoing.objects.all().delete()
            else:
                # Case where we resume interrupted downloads
                for down_obj in DownloadOngoing.objects.all():
                    if not down_obj.active:
                        down_obj.delete()
                    else:
                        down_obj.update(status=Status.INTERRUPTED)
                        checklist.append(down_obj.server)
                        irc_app_connection = IRCAppConnection(
                            download=down_obj,
                            history=DownloadHistory(filename=down_obj.filename, size=down_obj.size)
                        )
                        self.process_new_download(irc_app_connection=irc_app_connection)

        # In case there is a queue, let's check and launch the downloads
        for queue_obj in DownloadQueue.objects.all():
            if queue_obj.server not in checklist:
                irc_app_connection = IRCAppConnection(
                    download=DownloadOngoing(server=queue_obj.server, channel=queue_obj.channel, bot=queue_obj.bot,
                                             package_number=queue_obj.package_number, filename=queue_obj.filename,
                                             size=queue_obj.size),
                    history=DownloadHistory(filename=queue_obj.filename, size=queue_obj.size)
                )
                self.process_new_download(irc_app_connection=irc_app_connection)
                checklist.append(queue_obj.server)
                queue_obj.delete()

    def process_new_download(self, **kwargs) -> HttpResponse:
        """Process a new incoming download request."""
        # Create the IRCAppConnection object
        print("Processing new download")
        irc_app_connection = kwargs.get('irc_app_connection', None)
        if not irc_app_connection:
            irc_app_connection = IRCAppConnection(
                download=DownloadOngoing(server=kwargs['server'], channel=kwargs['channel'], bot=kwargs['bot'],
                                         package_number=int(kwargs['pack_number']),
                                         filename=kwargs['filename'], size=int(kwargs['size']),
                                         status=Status.CONNECTING),
                history=DownloadHistory(filename=kwargs['filename'], size=int(kwargs['size']))
            )
        d = irc_app_connection.download
        if get_free_space_mb() <= int(d.size) / (1000 ** 3):
            # Not enough disk space, add to queue without further checking
            return JsonResponse(d.add_to_queue().format())
        else:
            # There is enough disk space, we have to check whether the download can be started immediately.
            for download_ongoing in DownloadOngoing.objects.exclude(pk=d.id).exclude(status=Status.INTERRUPTED):
                if download_ongoing.server == d.server:
                    # If it's the same package, don't do anything
                    if (download_ongoing.channel == d.channel and download_ongoing.bot == d.bot and
                            download_ongoing.package_number == d.package_number):
                        return HttpResponse("Package already requested")
                    # If it's the same server, channel and bot OR
                    # queue_similar == True & same filename: add to queue
                    elif ((download_ongoing.channel == d.channel and download_ongoing.bot == d.bot) or
                          (DownloadSettings.objects.latest('id').queue_similar and
                           download_ongoing.filename.split(".")[0] == d.filename.split(".")[0])):
                        return JsonResponse(d.add_to_queue().format())
                    else:
                        # Same server exists but with a different channel: signal the bot to join a new channel and
                        # request the package.
                        self.irc_app_clients.get_client(d.server) \
                            .join_channel_and_request_package(irc_app_connection)
                        return HttpResponse("Joining the channel")

            # No download in progress or download in progress on another server: start a new client
            self.start_download(irc_app_connection=irc_app_connection)
            return HttpResponse("OK")

    def start_download(self, irc_app_connection: IRCAppConnection):
        """Start a download and save the client (server connection) to be able to call methods on it later."""
        # Make sure the objects are saved
        irc_app_connection.download.save()
        client = IRCAppClient(connection=irc_app_connection)
        self.irc_app_clients.add_client(client)
        thread = threading.Thread(target=self._start_daemon_download, args=(client, irc_app_connection))
        # Make the thread a daemon to make it stop when the ircapp shuts down
        thread.daemon = True
        thread.start()

    def _start_daemon_download(self, client: IRCAppClient, irc_app_connection: IRCAppConnection):
        """
        Establishing the server connection can fail for multiple reasons (like no internet connection), so we have
        to keep trying a few time before stopping. Since we don't want to block the ircapp, we need to create a separate
        thread the handle this process.
        """
        i = 1
        # Create an anonymous nickname
        nickname = ''.join(random.choice(string.ascii_lowercase) for i in range(8))
        # Remove any previous cancel signal
        if client in self.cancel_server_connection_signals:
            del self.cancel_server_connection_signals
        use_ssl = True
        while True:
            # Check if cancel was pressed
            if client in self.cancel_server_connection_signals:
                break
            # Try connecting to the server
            try:
                if use_ssl:
                    ssl_factory = Factory(wrapper=ssl.wrap_socket)
                    client.connect(irc_app_connection.download.server, 6697, nickname, connect_factory=ssl_factory)
                else:
                    client.connect(irc_app_connection.download.server, 6667, nickname)
                client.start()
                # The server connection has now been established, we can stop the loop.
                break
            except ServerConnectionError as e:
                log(f'Server connection error ({i}): {str(e)}')
                if 'unsupported protocol' in str(e):
                    # SSL not supported, switch to no SSL
                    use_ssl = False
                else:
                    irc_app_connection.history.update(status=Status.SERVER_CONNECTION_ERROR, end_date=utcnow(),
                                                      size=irc_app_connection.download.size)
                    irc_app_connection.download.update(status=Status.connecting_with_attempts(i))
                    i += 1
                    time.sleep(0.2)

    def stop_all(self):
        """Disconnect all existing server connections."""
        for k, client in self.irc_app_clients.clients.items():
            client.stop_all()
            self.cancel_server_connection_signals.add(client)

    def cancel_download(self, server: str, bot: str):
        """
        Cancel an ongoing or queued download.
        :param server: required to identify the server connection
        :param bot: required to identify the specific DCC connection
        :return:
        """
        client = self.irc_app_clients.get_client(server)
        self.cancel_server_connection_signals.add(client)

        if client:
            irc_app_connection = client.connections_cls.get_connection_by_bot(bot)
            irc_app_connection.download.update(active=False, canceled=True)
            dcc_connection = irc_app_connection.dcc_connection
            if dcc_connection:
                try:
                    dcc_connection.disconnect()
                except KeyError:
                    pass  # DCC connection not yet established
            else:
                # DCC connection not yet established
                irc_app_connection.on_dcc_disconnect()

        else:
            # In case there is no client or dcc_connection, simply delete any ongoing download with this info
            DownloadOngoing.objects.filter(server=server, bot=bot).delete()

    def check_queue(self, download: DownloadOngoing):
        """Check and manage the queue when a download finished or is canceled."""

        # Clean up any dcc connection registered with this info.
        client = self.irc_app_clients.get_client(server=download.server)
        c = client.connections_cls.get_connection_by_bot(bot=download.bot)
        if c:
            client.connections_cls.remove_connection(c)
        # Delete the DownloadOngoing object
        download.delete()
        # Next we check if there is a queue for this server
        if DownloadQueue.objects.filter(server=download.server).exists():
            # A Queue exists for this server, start the new download
            queue_obj = DownloadQueue.objects.filter(server=download.server).order_by("id").first()
            irc_app_connection = IRCAppConnection(
                download=DownloadOngoing(server=queue_obj.server, channel=queue_obj.channel, bot=queue_obj.bot,
                                         package_number=queue_obj.package_number, filename=queue_obj.filename,
                                         size=queue_obj.size),
                history=DownloadHistory(filename=queue_obj.filename, size=queue_obj.size)
            )
            # Delete the DownloadQueue object since it's consumed
            queue_obj.delete()
            # Request the queued package
            client.join_channel_and_request_package(irc_app_connection=irc_app_connection)
            return
        else:
            # There is no queue -at all or for this server-;
            # If no more DCCConnection is live for this server, quit the server.
            if not DownloadOngoing.objects.filter(server=download.server, active=True):
                client.stop_all()
                # Remove from items
                self.irc_app_clients.remove_client(irc_app_client=client)

                # Also check if shutdown option is checked
                _settings = DownloadSettings.get_object()
                if _settings.shutdown:
                    # Set option to False (consume it)
                    _settings.shutdown = False
                    _settings.save()
                    # Shutdown the computer
                    self.shutdown_computer()

    @staticmethod
    def shutdown_computer():
        """Shutdown the computer when the last download has finished."""
        cherrypy.engine.stop()
        if platform.system() == 'Windows':
            os.system("shutdown /s")
        elif platform.system() == 'Darwin':
            """Shutdown OSX system, never returns."""
            try:
                subprocess.call(['osascript', '-e', 'tell ircapp "System Events" to shut down'])
            except:
                log('Error while shutting down system')
            os._exit(0)
        else:
            try:
                import dbus
                sys_bus = dbus.SystemBus()
                ck_srv = sys_bus.get_object('org.freedesktop.ConsoleKit',
                                            '/org/freedesktop/ConsoleKit/Manager')
                ck_iface = dbus.Interface(ck_srv, 'org.freedesktop.ConsoleKit.Manager')
                stop_method = ck_iface.get_dbus_method("Stop")
                stop_method()
            except:
                log('DBus does not support Stop (shutdown)')
            os._exit(0)
