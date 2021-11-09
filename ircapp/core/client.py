import os
import random
import shlex
import sys
import threading
import names
from dataclasses import dataclass, field
from typing import Dict, Optional

from irc.client import (ServerConnection, DCCConnection, SimpleIRCClient, ip_numstr_to_quad, ip_quad_to_numstr,
                        DCCConnectionError)

if sys.platform == "win32":
    os.environ['UNRAR_LIB_PATH'] = os.path.join(os.path.dirname(sys.executable), 'unrar.dll')
else:
    pass

from version import __version__
from core.utils.logging import log
import core.dispatcher as dispatcher  # Avoid circular import

from core.ircapp_connection import IRCAppConnection
from core.models import *


@dataclass
class IRCAppConnections:
    """A simple collection class that contains IRCAppConnection objects and provides methods to access them."""

    connections: Dict[str, IRCAppConnection] = field(default_factory=dict)

    def get_connection_by_bot(self, bot: str) -> Optional[IRCAppConnection]:
        """Get the IRCAppConnection by bot name."""
        return self.connections.get(bot, None)

    def get_connection_by_dcc_connection(self, connection: DCCConnection) -> Optional[IRCAppConnection]:
        """Get the IRCAppConnection by DCCConnection."""
        for k, v in self.connections.items():
            if v.dcc_connection == connection:
                return v
        return None

    def add_connection(self, irc_app_connection: IRCAppConnection):
        self.connections[irc_app_connection.download.bot] = irc_app_connection

    def remove_connection(self, irc_app_connection: IRCAppConnection):
        if irc_app_connection.download.bot in self.connections:
            del self.connections[irc_app_connection.download.bot]


class IRCAppClient(SimpleIRCClient):
    """
    A single-server IRC client class, customized to accept dcc_send messages directly.
    Since one IRCAppClient object can have multiple DCC Connections, we need to be able differentiate the information;
    The lists here will be used and read thanks to the unique server identifier: the nickname.
    Call irc_app_client.connect() and then irc_app_client.start() to launch the server connection.
    """

    # Store all DCC connections for this client (server connection)
    connections_cls: IRCAppConnections = IRCAppConnections()

    # True if the client should should down without further processing
    shutdown = False

    """Delay before requesting a package after joining a server."""
    DELAYS_IN_S = {
        'irc.scenep2p.net': 60
    }

    """Some servers require joining a specific channel to be able to request a package."""
    ADDITIONAL_CHANNELS = {
        'irc.abjects.net': '#MG-CHAT'
    }

    # The list of channels that are currently joined.
    joined_channels: [str] = []

    # True if the delay after the server connection has been established is over.
    initial_join_delay_over = False

    def __init__(self, connection: IRCAppConnection):
        super().__init__()
        # When creating a new object, also add the first connection
        self.connections_cls.add_connection(connection)
        # Keep track of the initial connection for convenience
        self.initial_connection = connection
        # Store the server. When all other information is deleted, the server name is still required to find the
        # key/value pair in the DownloadManager
        self.server = connection.download.server
        # Random plausible nickname
        self.nickname = names.get_first_name() + names.get_last_name() + str(random.randint(10, 100))

    def join_channel_and_request_package(self, irc_app_connection: IRCAppConnection = None):
        if not irc_app_connection:
            irc_app_connection = self.initial_connection
        else:
            irc_app_connection.download.save()
            # Add the new connection to the list
            self.connections_cls.add_connection(irc_app_connection)

        # Join the channel
        self._join_channel(irc_app_connection.download.channel)
        # Request the package after checking delays
        delay = 0
        if not self.initial_join_delay_over:
            delay = self.DELAYS_IN_S.get(self.connection.server, random.randint(2, 5))
            log(f'Waiting {delay} seconds before requesting the package...')
        thread = threading.Timer(delay, self._request_package, args=(self.initial_connection,))
        # Make the thread a daemon to make it stop when the ircapp shuts down
        thread.daemon = True
        thread.start()

        irc_app_connection.download.update(status=Status.waiting_for_seconds(delay))

    def _join_channel(self, channel: str):
        """Join a channel if not already done."""
        if channel not in self.joined_channels:
            self.connection.join(channel)
            self.joined_channels.append(channel)
            log(f'Channel {channel} joined')

    def _request_package(self, ircapp_connection: IRCAppConnection):
        """Request a package by send a </msg `bot` send xdcc `pack`> message."""
        if not self.initial_join_delay_over:
            self.initial_join_delay_over = True
        self.connection.privmsg(ircapp_connection.download.bot, ircapp_connection.xdcc_msg)
        log(f'Package {ircapp_connection.download.filename} requested')
        ircapp_connection.download.update(status=Status.WAITING)

    def stop_all(self):
        """Cancel all downloads and disconnect from the server."""
        self.shutdown = True
        for k, v in self.connections_cls.connections.items():
            self.cancel_download(v)
        self.connection.close()

    def cancel_download(self, irc_app_connection: IRCAppConnection):
        """Signal the bot to cancel the download."""
        self.connection.ctcp('DCC', irc_app_connection.download.bot, 'CANCEL')

    def on_welcome(self, c, e):
        """Called when the client successfully connected to a server. The channel should now be joined."""
        log(f'Successfully connected to the server: {c.server}')
        self.join_channel_and_request_package()

    def on_ctcp(self, c, e):
        """Process a CTCP message."""
        if e.arguments[0] == 'DCC':
            self.on_dccsend(c, e)
        else:
            if e.arguments[0] == 'VERSION':
                message = f'VERSION IRCApp {__version__}'
                c.ctcp_reply(e.source.nick, message)
                print(f'VERSION msg received, replied "{message}"')

    # def on_all_raw_messages(self, c, e):  # Raw server messages
    #     print(e.arguments)

    def on_dccsend(self, c, e):
        """Called when we're receiving a file."""
        bot = e.source.nick
        # If the user cancels the download right away and then we're getting the DCC Send message,
        # we will still connect, which is bad, so we need to catch that canceled state.
        ircapp_c = self.connections_cls.get_connection_by_bot(bot)
        if not ircapp_c.download.canceled:
            payload = shlex.split(e.arguments[1])
            if payload[0] == 'SEND':
                filename = payload[1]
                # Only accept the file if it's the same filename (package_number can be outdated)
                if filename == ircapp_c.download.filename:
                    # Save information needed to accept the file
                    ircapp_c.peer_port = int(payload[3])
                    ircapp_c.peer_ip = ip_numstr_to_quad(payload[2])
                    # Update the size with the real one
                    ircapp_c.download.size = int(payload[4])
                    if ircapp_c.peer_port == 0:
                        # Reverse DCC, get the token
                        ircapp_c.token = int(payload[5])
                else:
                    log(f'Discarding download due to filename mismatch: requested {ircapp_c.download.filename} ' +
                        f'and received {filename}, proceeding to next item in queue if existing.')
                    c.ctcp('DCC', e.source.nick, 'REJECT')
                    ircapp_c.history.update(status=Status.DEAD_LINK, time=utcnow())
                    ircapp_c.download.update(status=Status.INVALID_PACK_NUMBER, active=False)
                    ircapp_c.check_queue()
                    return

                if os.path.exists(ircapp_c.file_path):
                    received_bytes = os.path.getsize(ircapp_c.file_path)
                    ircapp_c.download.update(received_bytes=received_bytes)
                    # Send a message to resume the file instead of starting from scratch. If the resume is accepted,
                    # on_dccsend will be called again, this time with an 'ACCEPT' parameter instead of 'SEND'.
                    c.ctcp('DCC', e.source.nick,
                           f'RESUME {ircapp_c.download.filename} {ircapp_c.peer_port} {received_bytes}')
                else:
                    self._process_dcc_send(c, ircapp_c)
            elif payload[0] == 'ACCEPT':
                self._process_dcc_send(c, ircapp_c, resume=True)

    def _process_dcc_send(self, c: ServerConnection, ircapp_c: IRCAppConnection, resume=False):
        """When receiving a file with DCC, accept it."""

        try:
            ircapp_c.dcc_connection = self.dcc('raw')
            log('Establishing the DCC connection...')
            if ircapp_c.peer_port == 0:
                # Reverse DCC
                # First we open a port
                ircapp_c.local_port = dispatcher.Dispatcher().local_port
                # Create the listening socket
                ircapp_c.dcc_connection.listen((dispatcher.Dispatcher().lan_ip, ircapp_c.local_port))
                ip_quad = ip_quad_to_numstr(dispatcher.Dispatcher().external_ip)
                message = (f'SEND {ircapp_c.download.filename} {ip_quad} {ircapp_c.local_port} ' +
                           f'{ircapp_c.download.size} {ircapp_c.token}')
                log(f'Reverse DCC, replying with {message}')
                c.ctcp('DCC', ircapp_c.download.bot, message)
            else:
                # Normal DCC process, connect to the server
                ircapp_c.dcc_connection.connect(ircapp_c.peer_ip, ircapp_c.peer_port)

            # Start the bytes received acknowledgement thread
            ircapp_c.ack_thread.start()
            ircapp_c.downloading = True

        except DCCConnectionError as e:
            log(f'Couldn\'t connect to DCC peer: {e}')
            ircapp_c.history.update(status=Status.CONNECTION_ERROR, end_date=utcnow())
            ircapp_c.check_queue()
            return

        # Open the IO file
        if resume:
            ircapp_c.file = open(ircapp_c.file_path, 'ab')
            ircapp_c.download.update(status=Status.RESUMING)
            log(f'Resuming download of {ircapp_c.download.filename}')
        else:
            ircapp_c.file = open(ircapp_c.file_path, 'wb')
            ircapp_c.download.update(status=Status.STARTING)
            log(f'Starting download of {ircapp_c.download.filename}')

        ircapp_c.history.end_date = utcnow()

    def on_disconnect(self, c, _):
        log(f'Disconnected from server: {self.server}')

    def on_nicknameinuse(self, c, e):
        """On the rare case the generated nickname is already in use, append a '_'."""
        self.nickname = self.nickname + "_"
        c.nick(self.nickname)
        log(f'Nickname already used. Now using "{self.nickname}"')

    def on_privnotice(self, c, e):
        msg = e.arguments[0].split(":", 1)
        ircapp_c = self.connections_cls.get_connection_by_bot(e.source.nick)
        log(f'Received a private notice: {e.arguments}')
        if 'invalid pack number' in str(msg).lower():
            ircapp_c.history.update(status=Status.DEAD_LINK, end_date=utcnow())
            ircapp_c.download.update(status=Status.INVALID_PACK_NUMBER, active=False)
            log('Discarding download due to invalid pack number, proceeding to next item in queue if existing.')
            ircapp_c.check_queue()
        elif 'already requested' in str(msg).lower():
            ircapp_c.download.update(status='Package already requested', active=False)
            log('Package already requested.')
            ircapp_c.check_queue()

    """From here on out we have dcc specific events.
    The connection is not a ServerConnection: it's a DCCConnection.
    """

    def on_dccmsg(self, c, e):
        """We forward the information to the specific IRCAppConnection instance."""
        self.connections_cls.get_connection_by_dcc_connection(c).on_dccmsg(e)

    def on_dcc_disconnect(self, c, _):
        """We forward the information to the specific IRCAppConnection instance."""
        self.connections_cls.get_connection_by_dcc_connection(c).on_dcc_disconnect(shutdown=self.shutdown)
