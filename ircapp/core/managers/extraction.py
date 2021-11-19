import os
import sys
import tarfile
import errno
import shutil
import struct

from django.conf import settings

if sys.platform == 'win32':
    if struct.calcsize('P') * 8 == 64:
        os.environ['UNRAR_LIB_PATH'] = os.path.join(settings.BASE_DIR, 'unrar64.dll')
    else:
        os.environ['UNRAR_LIB_PATH'] = os.path.join(settings.BASE_DIR, 'unrar.dll')
    from unrar import rarfile
else:
    import rarfile

from core.utils.directory import get_download_directory
from core.utils.logging import log
from core.models import *


class FileExtractor:
    """Extract a file (usually untar)."""

    @staticmethod
    def splitext(path):
        """Small method to account for .tar followed by gz or bz2."""
        for extension in ['.tar.gz', '.tar.bz2']:
            if path.endswith(extension):
                return path[:-len(extension)], path[-len(extension):]
        return os.path.splitext(path)

    def extract(self, irc_app_connection):
        download = irc_app_connection.download
        history = irc_app_connection.history

        log(f'Extracting {irc_app_connection.download.filename}...')

        # The tar file to extract
        _file = irc_app_connection.file.name

        # Create a temp _UNPACK_ directory to extract the file
        temp_path = (os.path.join(get_download_directory(), '_UNPACK_' +
                                  self.splitext(irc_app_connection.download.filename)[0]))
        print(tarfile.is_tarfile(irc_app_connection.file_path))
        if os.path.exists(irc_app_connection.file_path) and tarfile.is_tarfile(irc_app_connection.file_path):
            # Extract all contents
            try:
                # Unpack the rar blocks from the tar file
                with tarfile.open(_file) as f:
                    f.extractall(temp_path)
                os.remove(_file)
                # Extract rar files unpacked from the original tar files
                x = 0
                is_file_complete = False
                # This test is added in case some txt is extracted with the folder
                while not os.path.isdir(os.path.join(temp_path, os.listdir(temp_path)[x])):
                    # Sometimes the file extracted is the final file, so no further rar extraction is needed; in this
                    # case, test for its size and finish.
                    if os.path.getsize(os.path.join(temp_path, os.listdir(temp_path)[x])) > 90 / 100 * history.size:
                        is_file_complete = True
                        break
                    x += 1
                if not is_file_complete:
                    origin = os.path.join(temp_path, os.listdir(temp_path)[x])
                    # log(origin)
                    for fl in os.listdir(origin):
                        shutil.move(os.path.join(origin, fl), temp_path)
                    shutil.rmtree(origin)
                    for archive_file in os.listdir(temp_path):
                        if '.rar' in archive_file:
                            arch_ref = rarfile.RarFile(os.path.join(temp_path, archive_file), 'r')
                            arch_ref.extractall(temp_path)
                    # Remove the rest
                    for fl in os.listdir(temp_path):
                        ext = self.splitext(fl)[1].lower()
                        path_to_delete = os.path.join(temp_path, fl)
                        if os.path.isdir(path_to_delete):
                            # Do not delete non-empty dirs, could contain useful files.
                            try:
                                os.rmdir(path_to_delete)
                            except OSError as ex:
                                if ex.errno == errno.ENOTEMPTY:
                                    log(f'Did not delete non-empty directory: {path_to_delete}')
                                else:
                                    log(f'An error occurred deleting directory: {path_to_delete}')
                        else:
                            if ext[:2] == '.r' or ext in ['.sfv', '.nfo', '.png', '.jpg'] or 'sample' in fl:
                                os.remove(os.path.join(temp_path, fl))
                # Remove UNPACK from name when done
                os.rename(temp_path, os.path.join(get_download_directory(),
                                                  self.splitext(irc_app_connection.download.filename)[0]))
            except Exception as e:
                log(f'An error occurred during file extraction: {e}')
                history.update(status=Status.FILE_TRANSFER_ERROR, time=utcnow())
                download.update(status=Status.FILE_TRANSFER_ERROR, size=None, active=False)
                return
        else:
            log(f'{_file} does not exist or is not a tarfile, no extraction operation performed.')

        history.update(status=Status.DOWNLOADED_AND_EXTRACTED, time=utcnow())
        download.update(status=Status.DOWNLOADED_AND_EXTRACTED, size=None, active=False)
