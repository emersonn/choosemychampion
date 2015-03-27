# API Settings
API_KEY = "a956dacd-09ed-49d2-a610-dc9597599af3"
URLS = {'ids': 'https://na.api.pvp.net/api/lol/na/v1.4/summoner/by-name/',
        'stats': 'https://na.api.pvp.net/api/lol/na/v1.3/stats/by-summoner/%s/ranked',
        'champion': 'https://na.api.pvp.net/api/lol/static-data/na/v1.2/champion/',
        'featured': 'https://na.api.pvp.net/observer-mode/rest/featured?api_key=',
        'ids': 'https://na.api.pvp.net/api/lol/na/v1.4/summoner/by-name/',
        'matches': 'https://na.api.pvp.net/api/lol/na/v2.2/matchhistory/',
        'match': 'https://na.api.pvp.net/api/lol/na/v2.2/match/'}

# Database Settings
DATABASE = 'sqlite:///database/history.db'

# todo: MemCache?
# Cache Settings
from werkzeug.contrib.cache import SimpleCache
CACHE = SimpleCache()
