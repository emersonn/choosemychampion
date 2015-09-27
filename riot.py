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

    def _get_request(self, connection, formats={}, parameters={}):
        """ Builds a get request with the given API request

        Args:
            connection: Desired URL key in the URLS list.
            formats: Keyword arguments to format the string with.
            parameters: Extra parameters for the .get() request.

        Returns:
            json: JSON loaded response from the server.

        Assumptions:
            Desired location for API server is the current Session's stored
                location.
        """

        if 'location' not in formats:
            formats['location'] = self.location

        return self.get(
            URLS[connection].format(**formats),
            params=parameters
        ).json()

    def get_featured(self):
        """ Performs a request to get the featured games from Riot.

        Returns:
            list: List of featured games. If there are no games in the list,
                an empty list is returned.
        """

        try:
            return self._get_request('featured')['gameList']
        except KeyError:
            return []

    def get_matches(self, player, matches=5, match_type='RANKED_SOLO_5x5'):
        import warnings
        warnings.warn("Riot will be depricating this URL.")

        try:
            parameters = {'rankedQueues': match_type, 'endIndex': matches}
            return self._get_request(
                'matches',
                {'player': str(player)},
                parameters
            )['matches']
        except KeyError:
            return []

    def get_match(self, match):
        """ Performs a request to get match data from Riot.

        Returns:
            json: JSON loaded data in dictionary format.
        """

        return self._get_request(
            'match',
            {'match': str(match)}
        )

    # TODO: UnicodeEncodeError: 'ascii' codec can't encode character u'\xfc'
    #       in position 218: ordinal not in range(128)
    def get_ids(self, players):
        """ Performs a request to get the ID lists from a list of usernames.

        Args:
            players (list): List of players to perform the lookup on.

        Returns:
            json: JSON loaded data in dictionary format.
        """

        return self._get_request(
            'ids',
            {'players': ','.join(players)}
        )

    def get_stats(self, player):
        """ Performs a request to get the stats of a particular player.

        Args:
            player: Player ID.

        Returns:
            json: JSON loaded data of the player champion statistics
                in dictionary format.
        """

        return self._get_request(
            'stats',
            {'player': str(player)}
        )

    def get_match_list(self, player, match_type='RANKED_SOLO_5x5'):
        """ Performs a request to get the match list of a player.

        Args:
            player: ID of the player.
            match_type: Riot specified argument of the match types to look up.
                Defaults to Ranked Solo matches.

        Returns:
            list: List of match data.
        """

        parameters = {'rankedQueues': match_type}
        try:
            return self._get_request(
                'match_list',
                {'player': str(player)},
                parameters
            )['matches']
        except KeyError:
            return []

    def get_champion(self, champion_id, champ_data="all"):
        """ Performs a request to get static champion data.

        Args:
            champion_id: Champion ID.
            champ_data: Riot specific argument.
                Defaults to ALL champion data returned.

        Returns:
            json: JSON formatted data in dictionary format.
        """

        parameters = {'champData': champ_data}
        return self._get_request(
            'champion',
            {'champion': str(champion_id)},
            parameters
        )
