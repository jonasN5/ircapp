import miniupnpc
import random
import requests
import socket
from contextlib import closing
from django.conf import settings

from core.utils.logging import log
from core.models import UpnpPort


class PortManager:
    """Manage dynamic port forwarding using upnp. This is necessary for both reverse DCC and sending files.
    Uses config.ini ports instead if available."""

    _external_ip_address = None  # Will hold the public IP address
    _lan_ip_address = None  # Will hold the LAN IP address
    use_upnp = settings.PORT_FORWARDING is None

    def __init__(self):
        if self.use_upnp:
            self._upnp = miniupnpc.UPnP()
            self._upnp.discoverdelay = 300
            devices = self._upnp.discover()
            # Select an igd
            try:
                self._upnp.selectigd()
                log('Started UpnpManager successfully.')
                # Check the database for previous port mappings the were not deleting cleanly;
                # Delete any existing ports.
                for remaining_port in UpnpPort.objects.all():
                    self.delete_port(remaining_port)
                    remaining_port.delete()
            except Exception as e:
                log(f'Failed to select a UPnP IGD, please configure manual ports. Exception: {str(e)}')

    @property
    def lan_ip_address(self):
        if self.use_upnp:
            self._lan_ip_address = self._upnp.lanaddr
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self._lan_ip_address = s.getsockname()[0]
            s.close()
        return self._lan_ip_address

    @property
    def external_ip_address(self):
        if self.use_upnp:
            self._external_ip_address = self._upnp.externalipaddress()
            log(f'Discovered the public IP address: {self._external_ip_address}.')
        else:
            self._external_ip_address = requests.get('https://api.ipify.org').content.decode('utf8')
            log(f'Discovered the public IP address: {self._external_ip_address}.')
        return self._external_ip_address

    @staticmethod
    def _port_is_available(host, port) -> bool:
        """Check if a socket already exists on the specified port."""
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            return sock.connect_ex((host, port)) != 0

    def delete_port(self, port: int):
        if self.use_upnp:
            try:
                self._upnp.deleteportmapping(port, 'TCP')
                log(f'Deleted port mapping for port {port}.')
            except Exception as e:
                log(f'Could not delete port mapping for port {port}: {str(e)}.')
                print(e)

    def get_new_port(self) -> int:
        """Find an available TCP port, add port mapping and return it."""

        if settings.PORT_FORWARDING:
            # Use the manually opened ports
            if type(settings.PORT_FORWARDING) is int:
                # Single port, return it
                return settings.PORT_FORWARDING
            else:
                # Port range, get a free port
                start = settings.PORT_FORWARDING[0]
                end = settings.PORT_FORWARDING[1]
                for port in range(start, end + 1):
                    if self._port_is_available(self.lan_ip_address, port):
                        log(f'Using port {port} to proceed.')
                        return port
                log(f'No free port found.')
                raise PortException('All ports defined in config.ini are currently bound.')
        else:
            try:
                port = random.randint(30000, 40000)  # Starting port generated randomly
                port_mapping = None
                while port_mapping is not None and port < 65536:
                    port_mapping = self._upnp.getspecificportmapping(port, 'TCP')
                    if port_mapping:
                        port += 1

                new_mapping = self._upnp.addportmapping(port, 'TCP', self._upnp.lanaddr, port,
                                                        'UPnP IGD Tester port %u' % port, '')

                if new_mapping:
                    log(f'Successfully created port mapping for port {port}.')
                    return port
                else:
                    log(f'Could not create port mapping for port {port}.')
                    raise PortException
            except Exception as e:
                log(f'UPnP exception: {str(e)}')


class PortException(Exception):
    """Raised when the specific port mapping could not be created."""
    pass
