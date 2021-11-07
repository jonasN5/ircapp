import requests
import json

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json
from typing import List, Optional
from django.utils.module_loading import import_string

from core.utils.logging import log
from core.models import *


@dataclass_json
@dataclass
class SearchEngineResponseItem:
    filename: str
    size: int  # Raw size in bytes
    size_str: str  # String representation of file_size
    network: str  # IRC server/network
    channel: str
    bot: str
    pack_number: int  # Package number


@dataclass_json
@dataclass
class SearchEngineResponse:
    results: List[SearchEngineResponseItem] = field(default_factory=list)
    page_number: int = 0
    can_fetch_more_results: bool = False

    @property
    def is_empty(self):
        return len(self.results) == 0


class SearchEngine(ABC):
    """
    This class is the interface with the underlying search engine.
    Extend it to provide your own search engine. See SunXdccSearchEngine for an example.
    """

    def __init__(self):
        self.results = None

    def search(self, query: str, page_number: int = 0, args=None, kwargs=None) -> SearchEngineResponse:
        """Search the query using the configured api and return a SearchEngineResponse."""
        try:
            self.results = self._fetch_results(query, page_number, args, kwargs)
        except ConnectionError:
            log('Couldn"t access the search engine, exiting')
            raise ConnectionError

        response = self._process_response()
        if response.is_empty:
            log(f'No match for {query} on the search engine')

        response.page_number = page_number

        return response

    def quick_search(self, query: str) -> Optional[SearchEngineResponseItem]:
        """Returns the first search result that matches the configured parameters and the query string."""
        page_number = 0
        while True:
            print(page_number)
            response = self.search(query, page_number=page_number)
            page_number += 1

            if response.is_empty:
                return None
            else:
                _settings = DownloadSettings.get_object()
                quality_words = [i[0] for i in DownloadSettings.priority_choices]
                print(_settings.priority)
                quality_index = quality_words.index(_settings.priority)
                if quality_index > 0:
                    quality_words = quality_words[quality_index:]
                    quality_words = quality_words if quality_words else [] + quality_words[:quality_index].reverse()

                for item in response.results:
                    name = item.filename.lower()
                    is_valid = True
                    for element in query.split(' '):
                        if element not in name:
                            is_valid = False

                    for obj in _settings.contains.all():
                        if obj.text.lower() not in name:
                            is_valid = False
                    for obj in _settings.excludes.all():
                        if obj.text.lower() in name:
                            is_valid = False

                    # First loop through all the keywords
                    for word in quality_words:
                        # For each keyword, loop through all the elements to find a match before doing the same for
                        # the next keyword.
                        if word in name:
                            if word == "hd":
                                # also, if word is "hd", exclude other words since x["name"] might be like "720p.HDTV"
                                other_words = quality_words.copy()
                                other_words.remove(word)
                                for other_word in other_words:
                                    if other_word in name:
                                        is_valid = False
                        else:
                            is_valid = False
                    if is_valid:
                        return item

    @abstractmethod
    def _fetch_results(self, query: str, page_number=0, args=None, kwargs=None) -> object:
        """Query the search engine."""
        pass

    @abstractmethod
    def _process_response(self) -> SearchEngineResponse:
        """Transform the api response string into a usable SearchEngineResponse."""
        pass


class SunXdccSearchEngine(SearchEngine):
    """
    SunXdcc search engine, also the default one. Check https://sunxdcc.com/ for more information.
    Current docs state:
    Use the url http://sunxdcc.com/deliver.php?sterm= followd by your search term.
    You'll get a JSON string consisting of the arrays below with a maximum of 50 results.
    Add the page variable to the GET request to select a page.
    http://sunxdcc.com/deliver.php?sterm=moviegods -tar -rar&page=3
    network	for the - you guessed it - irc network.
    channel	for the channel.
    bot	for the bot.
    fsize	for the filesize.
    fname	for the filename.
    gets	for the number of times the file was downlaoded.
    botrec	for the bot's max upload speed. Will be "Na" if not available.
    """

    BASE_URL = "http://sunxdcc.com/deliver.php?"

    def _fetch_results(self, query: str, page_number=0, *args, **kwargs):
        parameters = {"sterm": query, "page": page_number}
        return requests.get(self.BASE_URL, params=parameters)

    def _process_response(self) -> SearchEngineResponse:
        data = json.loads(self.results.text)
        response = SearchEngineResponse()

        for i in range(len(data["network"])):
            # Construct a proper json where each item has all the data, instead of list separation
            try:
                # This is the string file size given by the server
                fsize = data['fsize'][i].replace("[", "").replace("]", "").strip()
                # This is the raw file size computed from the string size given by the server
                fsizeraw = int(float(fsize[:-1]) * (1000 ** 3 if fsize[-1] == "G" else 1000 ** 2))
                item = SearchEngineResponseItem(
                    filename=data['fname'][i],
                    size=fsizeraw,
                    size_str=fsize,
                    network=data['network'][i],
                    channel=data['channel'][i],
                    bot=data['bot'][i],
                    pack_number=int(data['packnum'][i].split('#')[1])
                )
                response.results.append(item)
            except (KeyError, IndexError):
                # Item is not valid since a parameter is missing
                continue

        if len(data["network"]) == 50:
            # More results can most likely be fetched since current page is maxed out
            response.can_fetch_more_results = True
        return response


def get_search_engine() -> SearchEngine:
    """
    Top level function to get an instance of the SearchEngine.
    Specify your custom engine in settings.IRCAPP_SEARCH_ENGINE.
    """
    try:
        from ircapp.settings import IRCAPP_SEARCH_ENGINE
        CustomEngine = import_string(IRCAPP_SEARCH_ENGINE)
        return CustomEngine()
    except ImportError:
        return SunXdccSearchEngine()
