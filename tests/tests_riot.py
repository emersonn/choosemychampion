import mock
from nose.tools import set_trace

from riot import RiotSession, URLS


class TestRiotSession(object):
    def setup(self):
        self.session = RiotSession(api="ASDF")

    def teardown(self):
        pass

    def test_get_stats(self):
        with mock.patch.object(self.session, "get") as get:
            get.return_value.json.return_value = "cats"
            stats = self.session.get_stats(1234)
            assert stats == "cats"

            get.assert_called_once_with(
                URLS['stats'].format(
                    location=self.session.location,
                    player=str(1234)
                ),
                params={}
            )

            """
            set_trace()
            """

    def test_get_featured(self):
        with mock.patch.object(self.session, "get") as get:
            get.return_value.json.return_value = {}
            featured = self.session.get_featured()
            assert featured == []

            get.assert_called_once_with(
                URLS['featured'].format(
                    location=self.session.location,
                ),
                params={}
            )

            # TODO: What if the featured is actually not None?
            #       Check if it actually made a request?
            #       Then we would be testing Riot's servers instead.
            # assert self.session.get_featured() is not None

    def test_get_matches(self):
        with mock.patch.object(self.session, "get") as get:
            get.return_value.json.return_value = {}
            matches = self.session.get_matches(1234)
            assert matches == []

            get.assert_called_once_with(
                URLS['matches'].format(
                    location=self.session.location,
                    player=str(1234)
                ),
                params={'rankedQueues': 'RANKED_SOLO_5x5', 'endIndex': 5}
            )

    def test_get_match(self):
        with mock.patch.object(self.session, "get") as get:
            get.return_value.json.return_value = {}
            match = self.session.get_match(1234)
            assert match == {}

            get.assert_called_once_with(
                URLS['match'].format(
                    location=self.session.location,
                    match=str(1234)
                ),
                params={}
            )
