import miniupnpc
import random
from django.conf import settings

from core.utils.logging import log
from core.models import UpnpPort


class UpnpManager:
    """Manage dynamic port forwarding using upnp. This is necessary for both reverse DCC and sending files."""

    external_ip_address = None  # Will hold the public IP address after __init__
    lan_ip_address = None  # Will hold the LAN IP address after __init__

    def __init__(self):
        self._upnp = miniupnpc.UPnP()
        log('Started UpnpManager successfully.')
        self._upnp.discoverdelay = 300
        devices = self._upnp.discover()
        # Select an igd
        self._upnp.selectigd()
        # Set the public IP
        self.external_ip_address = self._upnp.externalipaddress()
        # Set the LAN IP
        self.lan_ip_address = self._upnp.lanaddr
        log(f'Discovered the public IP address: {self.external_ip_address}.')
        # Check the database for previous port mappings the were not deleting cleanly;
        # Delete any existing ports.
        for remaining_port in UpnpPort.objects.all():
            self.delete_port(remaining_port)
            remaining_port.delete()

    def delete_port(self, port: int):
        try:
            self._upnp.deleteportmapping(port, 'TCP')
            log(f'Deleted port mapping for port {port}.')
        except Exception as e:
            log(f'Could not delete port mapping for port {port}: {str(e)}.')
            print(e)

    def get_new_port(self) -> int:
        """Find an available TCP port, add port mapping and return it."""

        if settings.PORT_FORWARDING:
            # No Upnp action required since the port was opened manually.
            log(f'No Upnp port mapping required since the port {settings.PORT_FORWARDING} was opened manually.' +
                f'\nUsing port {settings.PORT_FORWARDING} to proceed.')
            return settings.PORT_FORWARDING
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
                    raise PortMappingCreationException
            except Exception as e:
                log(f'UPnP exception: {str(e)}')


class PortMappingCreationException(Exception):
    """Raised when the specific port mapping could not be created."""
    pass
