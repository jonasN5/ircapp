import os
import struct
import threading
from typing import Optional, IO, Any
from irc.client import DCCConnection, Event

import core.dispatcher as dispatcher  # Avoid circular import
from .models import *
from core.utils.directory import get_download_directory
from core.utils.logging import log
from core.managers.extraction import FileExtractor


class IRCAppConnection:
    """This class wraps an irc.DCCConnection instance and contains all information related to this specific
    DCCConnection, e.g. download. It also manages the dcc bytes and sending the acknowledgement to the peer."""

    dcc_connection: Optional[DCCConnection] = None  # The DCCConnection, once established
    peer_port: Optional[int] = None  # The port of the peer
    local_port: Optional[int] = None  # The local port opened for a reverse DCC or sending a file
    peer_ip: Optional[str] = None  # The IP address of the peer
    token: Optional[int] = None  # The token when the peer wants a reverse DCC
    file: Optional[IO[Any]] = None  # The actual file
    ack_queue = []  # Bytes received acknowledgement queue
    ack_lock = threading.Lock()  # Lock for `ack_queue`
    request_package_thread: Optional[threading.Timer]  # The daemon thread used to requet the package after a delay

    def __init__(self, download: DownloadOngoing, history: DownloadHistory):
        self.download = download
        self.history = history
        # Thread that will consume `self.ack_queue` and send them down the pipeline
        self.ack_thread = threading.Thread(target=self.send_bytes_received_acknowledgment)
        self.downloading = False

    @property
    def xdcc_msg(self) -> str:
        return f'xdcc send #{self.download.package_number}'

    @property
    def file_path(self) -> str:
        return os.path.join(get_download_directory(), self.download.filename)

    @property
    def is_reverse_dcc(self) -> bool:
        """Returns true if it's a reverse DCC."""
        return self.peer_port == 0

    def save_objects(self):
        self.download.save()
        self.history.save()

    def cancel_request_package(self):
        """If the package has not yet been requested (initial delay not over), cancel it."""
        if self.request_package_thread:
            self.request_package_thread.cancel()

    def on_dccmsg(self, event: Event):
        """
        Called when receiving bytes. We have to do 2 things:
            1. Write the bytes to the file
            2. Send a reply with the number of bytes received as an acknowledgement
        """
        data = event.arguments[0]
        self.file.write(data)
        chunk = len(data)
        # Update received_bytes and save only each second since on_dccmsg will be call a lot
        self.download.update_bytes(new_bytes=chunk)
        payload = struct.pack(b"!Q", self.download.received_bytes)
        self.ack_queue.append(payload)
        if self.download.received_bytes == self.download.size:
            # Download is complete, disconnect
            self.dcc_connection.disconnect()

    def send_bytes_received_acknowledgment(self):
        while self.downloading:
            self.ack_lock.acquire()
            try:
                if len(self.ack_queue) > 0:
                    self.dcc_connection.send_bytes(self.ack_queue.pop(0))
                else:
                    time.sleep(0.5)
            except:
                continue
            finally:
                self.ack_lock.release()

    def on_dcc_disconnect(self, shutdown=False):
        log(f'DCC connection closed for file: {self.download.filename}')
        self.downloading = False

        try:
            self.file.close()
            # Close the port if it was a reverse DCC
            if self.is_reverse_dcc and self.local_port:
                dispatcher.Dispatcher().delete_port(self.local_port)
        except:
            pass

        if shutdown:
            # When shutting down IRCApp, don't do any further processing.
            return

        if not self.download.canceled:
            self.download.update(status=Status.EXTRACTING, progress=None, speed=None)
            log(f'Received file {self.download.filename} {self.download.received_bytes} ' +
                f'bytes out of {self.download.size}.')
            self.history.update(status=Status.DOWNLOADED, duration=self.download.duration,
                                end_date=utcnow(), size=self.download.received_bytes)
            if os.path.exists(self.file_path):
                # Added to prevent extracting incomplete files (internet connection interrupted)
                if self.download.percentage > 99 / 100:
                    dispatcher.Dispatcher().extract_file(self)
                    self.check_queue()
                    return

            # At this point we have an error
            self.download.update(status=Status.FILE_TRANSFER_ERROR)
            self.history.update(status=Status.FILE_TRANSFER_ERROR, end_date=utcnow())
            log(f'Error during file transfer. Completed percentage: {int(self.download.percentage * 100)}')
        else:
            self.cancel_request_package()
            # Check the queue when the download is canceled
            self.check_queue()

    def check_queue(self):
        dispatcher.Dispatcher().check_queue(download=self.download)
