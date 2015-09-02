import datetime
from functools import wraps
import operator
from time import sleep
import urllib

# TODO: fix this.
import logging
logging.captureWarnings(True)

from flask import Flask, abort, jsonify, request, send_file
import requests
from sqlalchemy import func, Integer

from models import PlayerData, ChampionData, Champion, Match
from database import db_session
from riot import RiotSession
from settings import API_KEY, URLS, CACHE

app = Flask(__name__)
app.config.from_object('app_settings')

@app.teardown_appcontext
def shutdown_session(exception=None):
    db_session.remove()

def cached(timeout = 10 * 60, key = 'view/%s'):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache_key = key % request.path
            rv = CACHE.get(cache_key)
            if rv is not None:
                return rv
            rv = f(*args, **kwargs)
            CACHE.set(cache_key, rv, timeout = timeout)
            return rv
        return decorated_function
    return decorator

# TODO: try to find a way to combine these two..

# requests to both of these urls are handled client side
@app.route('/')
def index():
    return send_file('static/index.html')

@app.route('/summoner/<username>/')
def username(username):
    return index()

# TODO: maybe try to find their username in the database if they already
# have been crawled. reduce api load?

# gathers champion statistics given their username and location
@app.route('/api/champions/<username>/<location>/')
def profile(username, location):
    try:
        print(username + " from " + location + " is requesting their user ID.")
        session = RiotSession(API_KEY, location)
        response = session.get_ids([urllib.pathname2url(username)])
        # TODO: very dependent on API. abstract this out into the module?
        #       make a function for a single id?
        user_id = response[response.keys()[0]]['id']
    # TODO: fix this. this catches both 429 and 400 errors. try to catch
    #       the status code instead. or handle it through the module. KeyError?
    #       catch the error too. raise new exception! need more info about
    #       what riot responded.
    except ValueError:
        print("Tried to get " + username + "'s id. Got an error.")
        abort(400)

    return stats(username, user_id, location)

# gathers champion statistics given an username, user id, and location
def stats(username, user_id, location):
    rv = CACHE.get('user_data_' + str(user_id))
    if rv is None:
        query = db_session.query(PlayerData).filter_by(player_id = user_id, location = location).all()

        # TODO: abstract this timer out into a constant
        thirty_minutes_ago = datetime.datetime.now() - datetime.timedelta(minutes = 30)
        if len(query) > 0 and query[0].updated < thirty_minutes_ago:
            print("Player in question has old data. Resetting stats.")
            reset_stats(username, user_id, location)
            query = []

        if len(query) == 0:
            try:
                print(username + " (" + str(user_id) + ") from " + location + " does not exist as a model. Attempting to create...")

                session = RiotSession(API_KEY, location)
                user_data = session.get_stats(user_id)
                build_stats(user_data, username, location)

                query = PlayerData.query.filter_by(player_id = user_id, location = location).all()

            # TODO: make this a more descriptive error
            except KeyError:
                abort(429)

        full_stats = {'scores': []}
        index = 1

        query = ChampionData.query.all()

        # TODO: this is vastly inefficient.

        # attempts to go through all the champion data and generate the
        # array of score information for each champion. this also appends
        # user data and user adjustments to the data.
        for champion in query:
            # attempts to go through each of the players champions when playing
            # this champion and gets their adjustment for the score
            user_query = PlayerData.query.filter_by(player_id = user_id, location = location, champion_id = champion.champion_id).first()
            if user_query == None:
                adjustment = 0
            else:
                adjustment = user_query.get_adjustment()

            # TODO: implement quick notes. quick information jabs of what they should play
            # what they like to play and some analysis about that. add as a function for the model of
            # PlayerData. maybe even add general champion quick infos.
            full_stats['scores'].append({
                'championName': champion.get_name(),
                'championId': champion.champion_id,
                'score': champion.get_score(False) + adjustment,
                'role': champion.role,
                'id': index,
                'image': champion.get_full_image(),
                'playerAdjust': adjustment,
                'url': champion.get_url(),
                'kills': champion.kills,
                'deaths': champion.deaths,
                'assists': champion.assists,
                'kda': champion.get_kda(),
                'winRate': champion.won * 100,
                'pickRate': champion.pick_rate * 100,
                'calculated': champion.get_calculated_win(user_id, location) * 100,
                'player': username
            })

            index += 1

        # returns the json of the stats as an array of scores
        CACHE.set('user_data_' + str(user_id), full_stats, timeout = 1 * 60)
        return jsonify(full_stats)
    else:
        return jsonify(rv)

# TODO: implement personal statistics over time. implement counters to the champion
#       and good team archetype to have.
@app.route('/api/stats/<champion>/<role>/')
@cached()
def champion_stats(champion, role):
    champ = db_session.query(ChampionData).filter_by(champion_id = champion, role = role).first()

    seven_days_ago = datetime.datetime.now() - datetime.timedelta(days = 30)
    champ_list = (db_session
        .query(
            Champion.champion_id.label("champion_id"),
            func.count(Champion.id).label("num_seen"),
            func.avg(Champion.won, type_ = Integer).label("won"),
            Match.match_id.label("match_id"),
            Match.match_time.label("match_time")
        )
        .filter(Champion.champion_id == champion, Champion.role == role)
        .join(Champion.match)
        .filter(Match.match_time > seven_days_ago)
        .group_by(func.day(Match.match_time))
        .order_by(Match.match_time.desc())
        .all()
    )

    stats = {
        'champion_info': {
            'champion_id': champ.champion_id,
            'champion_name': champ.get_name()
        },

        'counters': compile_sorted_champions(champ.get_compiled_weights("counters")),
        'assists': compile_sorted_champions(champ.get_compiled_weights("assists")),

        'days_seen': {
            'labels': [data.match_time.strftime("%b %d (%A)") for data in champ_list],
            'data': [data.num_seen for data in champ_list]
        },

        'days_won': {
            'labels': [data.match_time.strftime("%b %d (%A)") for data in champ_list],
            'data': [round(data.won, 2) for data in champ_list]
        }
    }



    return jsonify(stats)

# TODO: maybe do this at the model level?
def compile_sorted_champions(listing, reverse = True):
    sorted_listing = sorted(listing.items(), key = operator.itemgetter(1), reverse = reverse)
    listing = []

    for champion in sorted_listing:
        num_seen = champion[1]
        champ = champion[0]

        listing.append({
            'champion_id': champ.champion_id,
            'champion_name': champ.get_name(),
            'num_seen': num_seen,
            'won': champ.won * 100,
            'kda': champ.get_kda(),
            'image': champ.get_full_image()
        })

    return listing


# TODO: call all new adjustments

# resets the users statistics in the database
def reset_stats(username, user_id, location):
    query = PlayerData.query.filter_by(player_id = user_id, location = location).delete()
    db_session.commit()

    rv = CACHE.delete('user_data_' + str(user_id))

    print("Resetting stats for " + username + " (" + str(user_id) + ") from " + location + ".")

@app.route('/api/numbers/')
def numbers():
    rv = CACHE.get('numbers')
    if rv is None:
        popular_champ = db_session.query(ChampionData).order_by(ChampionData.num_seen.desc()).first()
        popular_champs = db_session.query(ChampionData).order_by(ChampionData.num_seen.desc()).limit(15).all()
        random_champ = db_session.query(ChampionData).order_by(func.rand()).first()
        winning_champ = db_session.query(ChampionData).filter(ChampionData.num_seen > 10).order_by(ChampionData.score.desc()).first()
        winning_champ_roles = (
            db_session.query(
                Champion.role.label("role"),
                func.count(Champion.id).label("seen")
            )
            .filter(Champion.champion_id == winning_champ.champion_id)
            .group_by(Champion.role).all()
        )

        # Stats, Date Stats, Case Study of Popular or Highest Win Rate
        stats = {
            'stats': {
                    'match_count': Match.query.count(),
                    'popular_champ': popular_champ.get_name(),
                    'popular_champ_kda': round(popular_champ.get_kda(), 2),
                    'random_champ': random_champ.get_name(),
                    'random_champ_role': random_champ.role.capitalize(),
                    'random_champ_seen': random_champ.num_seen,
                    'average_kills': round(db_session.query(func.avg(ChampionData.kills)).first()[0], 2),
                    'average_towers': round(db_session.query(func.avg(ChampionData.tower_score)).first()[0], 2)
            },

            'champion_picks': {
                    'labels': [champ.get_name() + " (" + champ.role.capitalize() + ")" for champ in popular_champs],
                    'data': [champ.num_seen for champ in popular_champs],
                    'images': [champ.get_full_image() for champ in popular_champs]
            },

            # Time graph of pick rate over a week, group by date picked
            'winning_champ': {
                    'name': winning_champ.get_name(),
                    'role': winning_champ.role.capitalize(),
                    'image': winning_champ.get_full_image(),
                    'seen': winning_champ.num_seen,
                    'won': winning_champ.won * 100,
                    'assists': compile_sorted_champions(champ.get_assists()),
                    'kda': winning_champ.get_kda(),

                    'role_distribution': {
                        'labels': [data.role.capitalize() for data in winning_champ_roles],
                        'data': [data.seen for data in winning_champ_roles]
                    }
            }
        }
        CACHE.set('numbers', stats, timeout = 10 * 60)
        return jsonify(stats)

    return jsonify(rv)

# builds the stats of a user given a player's performance
def build_stats(data, username, location):
    for champion in data['champions']:
        if champion['id'] != 0:
            total_stats = champion['stats']
            new_player = PlayerData(
                player_id = data['summonerId'],
                player_name = username,
                location = location,
                champion_id = champion['id'],
                updated = datetime.datetime.today(),
                sessions_played = total_stats['totalSessionsPlayed'],
                kills = total_stats['totalChampionKills'],
                deaths = total_stats['totalDeathsPerSession'],
                assists = total_stats['totalAssists'],
                won = total_stats['totalSessionsWon']
            )
            db_session.add(new_player)
    db_session.commit()

if __name__ == '__main__':
    app.run()
