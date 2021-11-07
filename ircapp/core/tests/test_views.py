import json

from django.urls import reverse
from django.test import TestCase
from django.core.exceptions import ObjectDoesNotExist

from main import IRCApp
from core.models import DownloadOngoing


class TestIndex(TestCase):

    def test_index_initial_objects(self):
        """The index should only work when the database has been populated with the initial objects."""
        try:
            self.client.get(reverse('index'))
            # An exception should have been raised
            raise Exception
        except ObjectDoesNotExist:
            pass
        # Now populate the data and test again
        IRCApp.populate_initial_database()
        self.assertEqual(self.client.get(reverse('index')).status_code, 200)


class PopulatedTest(TestCase):

    def setUp(self) -> None:
        # Populate the database
        IRCApp.populate_initial_database()


# class TestDownload(PopulatedTest):
#
#     def test_download(self):
#         """The view should work only if the parameter 'query' is passed as a POST request."""
#         self.assertEqual(self.client.post(reverse('download'), data={'query': 'linux'}).status_code, 200)
#         self.assertEqual(self.client.get(reverse('download'), data={'query': 'linux'}).status_code, 405)
#         self.assertEqual(self.client.post(reverse('download')).status_code, 400)


class TestMonitor(PopulatedTest):

    def test_monitor(self):
        """The view should always return a json."""
        response = self.client.get(reverse('monitor'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('update_elements', json.loads(response.content))
        DownloadOngoing().save()
        response = self.client.get(reverse('monitor'))
        self.assertIn('download_ongoing_list', json.loads(response.content),
                      'The request response should contain "download_ongoing_list" if DownloadOngoing count > 0')
        self.assertGreater(len(json.loads(response.content)['download_ongoing_list']), 0)


class TestUpdateDownloadPath(PopulatedTest):

    def test_update_download_path_if_ongoing_download_exists(self):
        """The view should return an error message if a download is currently ongoing."""
        DownloadOngoing().save()
        response = self.client.post(reverse('download_path'))
        self.assertIn('error', json.loads(response.content))
