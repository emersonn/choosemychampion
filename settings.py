# API Settings
API_KEY = "45501fd5-d2b4-40a4-89c2-86b15b175904"
URLS = {'ids': 'https://na.api.pvp.net/api/lol/na/v1.4/summoner/by-name/',
        'stats': 'https://na.api.pvp.net/api/lol/na/v1.3/stats/by-summoner/%s/ranked',
        'champion': 'https://na.api.pvp.net/api/lol/static-data/na/v1.2/champion/',
        'featured': 'https://na.api.pvp.net/observer-mode/rest/featured?api_key=',
        'ids': 'https://na.api.pvp.net/api/lol/na/v1.4/summoner/by-name/',
        'matches': 'https://na.api.pvp.net/api/lol/na/v2.2/matchhistory/',
        'match': 'https://na.api.pvp.net/api/lol/na/v2.2/match/'}

# Database Settings
DATABASE = 'mysql://root@localhost/league'

# todo: MemCache?

# Cache Settings
from werkzeug.contrib.cache import SimpleCache
CACHE = SimpleCache()
