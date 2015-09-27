# Riot API Connection Manager
# Emerson Matson

# Used for all requests to the Riot API, including grabbing player data,
# creating a session with the riot server

# Temporary tips:
# My ID: 27284
# Random match: 1932421719

import requests

BASE_URL = "https://{location}.api.pvp.net/"
# https://{location}.api.pvp.net/api/lol/{location}/
BASE_API_URL = BASE_URL + "api/lol/{location}/"
# https://{location}.api.pvp.net/api/lol/static-data/{location}/
BASE_STATIC_URL = BASE_URL + "api/lol/static-data/{location}/"

URLS = {
    'ids': BASE_API_URL + 'v1.4/summoner/by-name/{players}',
    'stats': BASE_API_URL + 'v1.3/stats/by-summoner/{player}/ranked/',
    'champion': BASE_STATIC_URL + 'v1.2/champion/{champion}/',
    'featured': 'https://{location}.api.pvp.net/observer-mode/rest/featured/',
    'matches': BASE_API_URL + 'v2.2/matchhistory/{player}/',
    'match': BASE_API_URL + 'v2.2/match/{match}/',
    'match_list': BASE_API_URL + 'v2.2/matchlist/by-summoner/{player}/'
}

# TODO: Try abstracting with json.loads in object_hook to make consistent
# TODO: Add error checking, error codes, etc. r.status_code = 429
# TODO: Rate limiting throw errors.
# TODO: Streamline the .get() and .format() and add unit tests for
#       the requested URL.


class RiotSession(requests.Session):
    def __init__(self, api, location="na"):
        super(RiotSession, self).__init__()
        self.params.update({'api_key': api})
        self.location = location

    def _get_request(self, connection, formats):
        """ Builds a get request with the given API request

        Args:
            connection: Desired URL key in the URLS list.
            formats: Keyword arguments to format the string with.

        Returns:
            json: JSON loaded response from the server.

        Assumptions:
            Desired location for API server is the current Session's stored
                location.
        """

        return self.get(URLS[connection].format(**formats)).json()

    def get_featured(self):
        try:
            return self.get(URLS['featured'].format(
                location=self.location
            )).json()['gameList']
        except KeyError:
            return []

    def get_matches(self, player, matches=5, match_type='RANKED_SOLO_5x5'):
        import warnings
        warnings.warn("Riot will be depricating this URL.")

        try:
            return self.get(
                URLS['matches'].format(
                    location=self.location, player=str(player)
                ),
                params={'rankedQueues': match_type, 'endIndex': matches}
            ).json()['matches']
        except KeyError:
            return []

    def get_match(self, match):
        return self.get(
            URLS['match'].format(location=self.location, match=str(match))
        ).json()

    # TODO: UnicodeEncodeError: 'ascii' codec can't encode character u'\xfc'
    #       in position 218: ordinal not in range(128)
    def get_ids(self, players):
        return self.get(
            URLS['ids'].format(
                location=self.location,
                players=','.join(players)
            )
        ).json()

    def get_stats(self, player):
        return self.get(
            URLS['stats'].format(location=self.location, player=str(player))
        ).json()

    def get_match_list(self, player, match_type='RANKED_SOLO_5x5'):
        return self.get(
            URLS['match_list'].format(
                location=self.location, player=str(player)
            ),
            params={'rankedQueues': match_type}
        ).json()['matches']

    def get_champion(self, champion_id, champ_data="all"):
        return self.get(
            URLS['champion'].format(
                location=self.location, champion=str(champion_id)
            ),
            params={'champData': champ_data}
        ).json()
