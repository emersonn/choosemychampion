# Riot API Connection Manager
# Emerson Matson

# Used for all requests to the Riot API, including grabbing player data, instiating
# a session with the riot server

# Temporary tips:
# Matches: r = requests.get(URLS['matches'] + str(player), params = {'api_key': API_KEY, 'rankedQueues': 'RANKED_SOLO_5x5', 'endIndex': BREADTH})
# Match: get_match_data = requests.get(URLS['match'] + str(match['matchId']), params = {'api_key': API_KEY})
# Ids: r = requests.get(URLS['ids'] + ','.join(participants), params = {'api_key': API_KEY})
# My ID: 27284
# Random match: 1932421719

import requests

URLS = {'ids': 'https://{location}.api.pvp.net/api/lol/{location}/v1.4/summoner/by-name/{players}',
        'stats': 'https://{location}.api.pvp.net/api/lol/{location}/v1.3/stats/by-summoner/{player}/ranked/',
        'champion': 'https://{location}.api.pvp.net/api/lol/static-data/{location}/v1.2/champion/{champion}/',
        'featured': 'https://{location}.api.pvp.net/observer-mode/rest/featured/',
        'matches': 'https://{location}.api.pvp.net/api/lol/{location}/v2.2/matchhistory/{player}/',
        'match': 'https://{location}.api.pvp.net/api/lol/{location}/v2.2/match/{match}/'}

# TODO: maybe try abstracting out the games into json.loads with object_hook to make
#       consistent across the platform, also allowing for update of the riot API without
#       changing a lot of code

# TODO: add error checking, error codes, etc. r.status_code = 429
class RiotSession(requests.Session):
    def __init__(self, api, location = "na"):
        super(RiotSession, self).__init__()
        self.params.update({'api_key': api})

        self.location = location

    # TODO: KeyError
    def get_featured(self):
        try:
            return self.get(URLS['featured'].format(location = self.location)).json()['gameList']
        except KeyError:
            return []

    # TODO: r['matches'] exists (KeyError), and even if ValueError for if JSON exists
    def get_matches(self, player, matches = 5, match_type = 'RANKED_SOLO_5x5'):
        try:
            return self.get(URLS['matches'].format(location = self.location, player = str(player)),
                params = {'rankedQueues': match_type, 'endIndex': matches}).json()['matches']
        except:
            return []

    # TODO: r['matches'] exists (KeyError), and even if ValueError for if JSON exists
    def get_match(self, match):
        try:
            return self.get(URLS['match'].format(location = self.location, match = str(match))).json()
        except ValueError:
            return []

    def get_ids(self, players):
        return self.get(URLS['ids'].format(location = self.location, players = ','.join(players))).json()

    def get_stats(self, player):
        return self.get(URLS['stats'].format(location = self.location, player = str(player))).json()
