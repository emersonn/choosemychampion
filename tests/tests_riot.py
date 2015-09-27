import mock
# from nose.tools import set_trace

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
            #       Maybe check if there is actual request headers?
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

    def test_get_match_list(self):
        with mock.patch.object(self.session, "get") as get:
            get.return_value.json.return_value = {}
            l = self.session.get_match_list(1234)
            assert l == []

            get.assert_called_once_with(
                URLS['match_list'].format(
                    location=self.session.location,
                    player=str(1234)
                ),
                params={'rankedQueues': 'RANKED_SOLO_5x5'}
            )

    def test_get_ids(self):
        with mock.patch.object(self.session, "get") as get:
            get.return_value.json.return_value = {}
            ids = self.session.get_ids([])
            assert ids == {}

            get.assert_called_once_with(
                URLS['ids'].format(
                    location=self.session.location,
                    players=''
                ),
                params={}
            )

    def test_get_champion(self):
        with mock.patch.object(self.session, "get") as get:
            get.return_value.json.return_value = {}
            champion_data = self.session.get_champion(1234)
            assert champion_data == {}

            get.assert_called_once_with(
                URLS['champion'].format(
                    location=self.session.location,
                    champion=str(1234)
                ),
                params={'champData': 'all'}
            )
