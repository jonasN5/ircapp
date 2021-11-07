import os
import platform
import ctypes

from django.conf import settings
from core.models import DownloadSettings


def get_download_directory():
    """Return the download directory on the hard drive."""
    _settings = DownloadSettings.get_object()
    if _settings.path:
        return _settings.path
    else:
        # Temporary solution to get download path for english, german and french speaking users
        path = os.path.join(os.path.expanduser('~'), 'Downloads')
        if not os.path.exists(path):
            path = os.path.join(os.path.expanduser('~'), 'Téléchargements')
        # Config.ini file has priority
        with open(os.path.join(settings.BASE_DIR, "config.ini"), "r") as cfg:
            content = cfg.readlines()
            _path = content[4][1 + content[4].index("="):content[4].index("#")].strip(" ")
            if _path:
                path = _path
            cfg.close()

        if os.path.exists(path):
            _settings.path = path
            _settings.save()
            return path
        else:
            raise Exception("Error : could not find default download directory")


def get_free_space_mb():
    """Return folder/drive free space (in megabytes)."""
    _dir = get_download_directory()
    if os.path.exists(_dir):
        if platform.system() == 'Windows':
            free_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(ctypes.c_wchar_p(_dir), None, None,
                                                       ctypes.pointer(free_bytes))
            return round(free_bytes.value / (1000 ** 3), 2)
        else:
            st = os.statvfs(_dir)
            return round(st.f_bavail * st.f_frsize / (1000 ** 3), 2)
    else:
        return -1
