from core.tests.test_views import PopulatedTest
from core.managers.search import get_search_engine, SearchEngine, SearchEngineResponse, SearchEngineResponseItem


class TestSearchEngineResponse(PopulatedTest):

    def test_is_empty_property(self):
        _instance = SearchEngineResponse()
        self.assertTrue(_instance.is_empty, 'SearchEngineResponse is_empty should return True')
        _instance.results.append(SearchEngineResponseItem('', 0, '', '', '', '', 0))
        self.assertFalse(_instance.is_empty, 'SearchEngineResponse is_empty should return False')


class TestSearchEngine(PopulatedTest):

    def test_get_instance(self):
        """The entry point function should return an instance of SearchEngine."""
        self.assertIsInstance(get_search_engine(), SearchEngine,
                              'get_search_engine() must return an instance of SearchEngine')

    def test_search_engine_search(self):
        """The SearchEngineResponse should not be empty when searching 'linux'."""
        engine = get_search_engine()
        response = engine.search(query='linux')
        self.assertIsInstance(response, SearchEngineResponse)
        self.assertFalse(response.is_empty, 'SearchEngineResponse should not be empty when searching for "linux"')
        # Conversely, make sure there is not hit when searching for an impossible string
        response = engine.search(query='iureghkhliqejualhgqlcvaetuighaeol')
        self.assertTrue(response.is_empty,
                        'SearchEngineResponse should be empty when searching for an impossible string')
    #
    # def test_search_engine_quick_search(self):
    #     """The quick_search method should return an item when searching 'linux'."""
    #     engine = get_search_engine()
    #     item = engine.quick_search(query='linux')
    #     self.assertIsInstance(item, SearchEngineResponseItem,
    #                           'quick_search should return a hit when searching for "linux"')
