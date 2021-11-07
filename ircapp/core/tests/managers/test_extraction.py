import tempfile


from core.managers.extraction import *
from core.tests.test_views import PopulatedTest
from main import IRCApp


class TestFileExtractor(PopulatedTest):

    def setUp(self) -> None:
        # Populate the database
        IRCApp.populate_initial_database()

    def test_splitext_method(self):
        """file.tar.gz should be split into ('file.tar', '.gz')"""
        self.assertEqual(FileExtractor.splitext('file.rar'), ('file', '.rar'))
        self.assertEqual(FileExtractor.splitext('file.tar'), ('file', '.tar'))
        self.assertEqual(FileExtractor.splitext('file.tar.gz'), ('file', '.tar.gz'))
        self.assertEqual(FileExtractor.splitext('file.tar.bz2'), ('file', '.tar.bz2'))

    def test_extract_only_valid_tar_files(self):
        """Make sure only valid tar files are extracted and other files are kept."""
        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(suffix='.mkv')
        # Create test database objects
        from core.ircapp_connection import IRCAppConnection
        test_connection = IRCAppConnection(download=DownloadOngoing(filename=temp_file.name),
                                           history=DownloadHistory())
        test_connection.file = temp_file
        test_connection.save_objects()
        FileExtractor().extract(irc_app_connection=test_connection)
        self.assertTrue(os.path.exists(test_connection.file_path), 'Non tar like files should exists after extraction.')
        temp_file.close()
