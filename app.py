from flask import Flask, abort, jsonify, send_file
from time import sleep
import requests, datetime

from models import PlayerData, ChampionData
from database import db_session

app = Flask(__name__)

# todo: debugging is like... on. i repeat. DEBUGGING IS ON!
app.debug = True

# todo: fix this. like really. this deals with the warning
# given by python for not updating python and not installing
# the SSL library.
import logging
logging.captureWarnings(True)

# todo: MemCache?
from werkzeug.contrib.cache import SimpleCache
cache = SimpleCache()

# todo: these should be moved into a settings file.
API_KEY = "a956dacd-09ed-49d2-a610-dc9597599af3"
URLS = {'ids': 'https://na.api.pvp.net/api/lol/na/v1.4/summoner/by-name/',
        'stats': 'https://na.api.pvp.net/api/lol/na/v1.3/stats/by-summoner/%s/ranked'}

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

# todo: try to find a way to combine these two..

# if the user is in the index or the route /summoner/<username>/ it
# directs them to the index html page. their request is handled client
# side.
@app.route('/')
def index():
    return send_file('static/index.html')

@app.route('/summoner/<username>/')
def username(username):
    return index()

# todo: maybe try to find their username in the database if they already
# have been crawled by the database. maybe they might exist in it?

# defines the API route for the username. attempts to find their user_id
# and returns a json with ['user_id']
@app.route('/api/<username>/')
def profile(username):
    query = PlayerData.query.filter_by(player_name = username).all()

    if len(query) == 0:
        try:
            print(username + " does not exist in the system. Getting user id...")
            r = requests.get(URLS['ids'] + username, params = {'api_key': API_KEY})
            user_id = r.json()[username]['id']
        # todo: fix this. this catches both 429 and 400 errors. try to catch
        # the status code instead.
        except KeyError:
            print("Tried to get " + username + "'s id. Got 429.")
            abort(429)
    else:
        # todo: multiple usernames? maybe the person has already had the username taken
        # by someone else?
        user_id = query[0].player_id

    return jsonify({'user_id': user_id})

# todo: kind of not... clean. the only purpose of putting this as
# username and user_id was to know if their username has already
# been requested but that's handled client side. it would
# be cleaner to just have the ID. but maybe this handles multiple
# ids? maybe it can be used in the future to handle region?

# defines the API route in which the username and the user id has been
# supplied. returns a json of all of the player stats for every champion
# including non played champions
@app.route('/api/stats/<username>/<user_id>/')
def stats(username, user_id):
    rv = cache.get('user_data_' + user_id)
    if rv is None:
        query = PlayerData.query.filter_by(player_id = user_id).all()

        # todo: update user data if the data is old.
        if len(query) == 0:
            try:
                print(str(user_id) + " does not exist as a model. Attempting to create...")
                # todo: catching the errors!
                r = requests.get(URLS['stats'] % str(user_id), params = {'api_key': API_KEY})
                user_data = r.json()
                build_stats(user_data, username)

                query = PlayerData.query.filter_by(player_id = user_id).all()
            # todo: not very descriptive error. the name could not exist or maybe
            # there was an actual overload of requests!
            except KeyError:
                abort(429)

        full_stats = {'scores': []}
        query = ChampionData.query.all()

        # todo: depricated. remove this! no need for this anymore.
        index = 1

        # todo: this is vastly inefficient. it goes through a LOT of data to
        # generate this. maybe cache this? maybe not? it's user specific, so
        # maybe cache another function that just gets champion data and adjust
        # certain key values after it has been given?

        # attempts to go through all the champion data and generate the
        # array of score information for each champion. this also appends
        # user data and user adjustments to the data.
        for champion in query:
            # attempts to go through each of the players champions when playing
            # this champion and gets their adjustment for the score
            user_query = PlayerData.query.filter_by(player_id = user_id, champion_id = champion.champion_id).first()
            if user_query == None:
                adjustment = 0
            else:
                adjustment = user_query.get_adjustment()

            # todo: implement quick notes. quick information jabs of what they should play
            # what they like to play and some analysis about that.
            full_stats['scores'].append({'championName': champion.get_name(), 'championId': champion.champion_id,
                'score': champion.get_score(False) + adjustment,
                'role': champion.role, 'id': index, 'image': champion.get_image(),
                'playerAdjust': adjustment, 'uriname': champion.get_image().split('.')[0],
                'kills': champion.kills, 'deaths': champion.deaths, 'assists': champion.assists,
                'kda': champion.get_kda(), 'winRate': champion.won * 100, 'pickRate': champion.pick_rate * 100,
                'calculated': champion.get_calculated_win(), 'player': username})

            index += 1

        # returns the json of the stats as an array of scores
        cache.set('user_data_' + user_id, full_stats, timeout = 5 * 60)
        return jsonify(full_stats)
    else:
        return jsonify(rv)

# defines the API route to reset the user's stats. to be implemented as a button?
@app.route('/api/stats/<username>/<user_id>/reset/')
def reset_stats(username, user_id):
    pass

# builds the stats of a user to put into the PlayerData model. saves the data
# into the database from a parameter of champion data from the servers, and
# the username.
def build_stats(data, username):
    for champion in data['champions']:
        if champion['id'] != 0:
            total_stats = champion['stats']
            new_player = PlayerData(player_id = data['summonerId'],
                player_name = username, champion_id = champion['id'],
                updated = datetime.datetime.today(), sessions_played = total_stats['totalSessionsPlayed'],
                kills = total_stats['totalChampionKills'], deaths = total_stats['totalDeathsPerSession'],
                assists = total_stats['totalAssists'], won = total_stats['totalSessionsWon'])
            db_session.add(new_player)
    db_session.commit()

if __name__ == '__main__':
    app.run()
