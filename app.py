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

@app.route('/summoner/<username>/<location>/')
def username(username, location):
    return index()

@app.route('/about/')
def about():
    return index()

@app.route('/versions/')
def versions():
    return index()

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

        # TODO: restructure this so it doesn't make multiple query requests...
        analyzed_player = analyze_player(user_id, location)

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

            # TODO: implement role? is role not included in this calculation? check this.
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

            # DEPRICATED: remove this. not used in front anymore
            index += 1

        full_stats['popular_counters'] = [
            popular_counters("TOP"),
            popular_counters("MIDDLE"),
            popular_counters("BOTTOM"),
            popular_counters("JUNGLE")
        ]

        full_stats['analyzed_player'] = analyzed_player

        # returns the json of the stats as an array of scores
        CACHE.set('user_data_' + str(user_id), full_stats, timeout = 1 * 60)
        return jsonify(full_stats)
    else:
        return jsonify(rv)

# TODO: implement limiting for multiple champions of the same role
def popular_counters(role, limit = 1, counter_limit = 5):
    champion = db_session.query(ChampionData).filter_by(role = role).order_by(ChampionData.num_seen.desc()).limit(limit).first()
    return {
        'champion': {
            'champion_name': champion.get_name()
        },
        'counters': compile_sorted_champions(champion.get_compiled_weights("counters"))[:5]
    }

# TODO: consider exceptions that may occur

def analyze_player(player_id, location):
    flags = {}

    session = RiotSession(API_KEY, location)
    # matches = session.get_matches(player = player_id, matches = )
    # STRATEGY: get match_list, store matches in Match/Champion
    #           filter by match_list. add match_list to player_data object manytomany.
    #           add updated list.

    # TODO: maybe reduce requests by storing the updated time?
    match_list = session.get_match_list(player_id)
    match_list = match_list[:min(15, len(match_list))]
    match_ids = [match['matchId'] for match in match_list]

    print("Match list has been requested for " + str(player_id) + ".")

    # TODO: abstract out store_match to avoid this interlinkage between app/crawler
    from crawler import store_match

    for match in match_ids:
        check_match = db_session.query(Match).filter(Match.match_id == match).count()
        if check_match == 0:
            match_data = session.get_match(match)
            try:
                store_match(match_data)
            except KeyError:
                print("Could not store match " + str(match) + ".")
        else:
            print(str(match) + " already exists in the database.")

    matches = db_session.query(Champion).join(Match).filter(Match.match_id.in_(match_ids))
    player_data = (db_session
        .query(PlayerData.champion_id)
        .filter_by(player_id = player_id, location = location)
        .order_by(PlayerData.won.desc())
        .limit(5)
        .all()
    )

    flags['best_champs'] = [champ[0] for champ in player_data]
    flags['best_champ'] = flags['best_champs'][0]
    flags['played_best_champ'] = False

    flags['wins'] = 0
    flags['losses'] = 0

    flags['durations'] = []

    flags['lose_kdas'] = []

    for match in matches.filter(Champion.player_id == player_id).all():
        if match.won:
            flags['wins'] += 1
        else:
            flags['losses'] += 1
            flags['lose_kdas'].append(match.get_kda())

        flags['durations'].append(match.match.match_duration / 60)

        if match.champion_id in flags['best_champs']:
            flags['played_best_champ'] = True
            flags['best_champ'] = match.champion_id
            flags['best_champ_kda'] = match.get_kda()

    flags['won'] = flags['wins'] > flags['losses']

    best_champ = db_session.query(ChampionData).filter_by(champion_id = flags['best_champ']).first()

    if flags['best_champ'] is not None:
        # TODO: kind of arbitrary number of kda. only ensures they're positive
        flags['best_champ_well'] = flags['best_champ_kda'] > 1
    else:
        flags['best_champ_well'] = db_session.query(PlayerData).filter_by(champion_id = flags['best_champ']).first().get_kda() > 1

    flags['average_duration'] = reduce(lambda x, y: x + y, flags['durations']) / float(len(flags['durations']))

    if flags['lose_kdas'] is not None:
        flags['average_lose_kda'] = reduce(lambda x, y: x + y, flags['lose_kdas']) / float(len(flags['lose_kdas']))

    flags['long_games'] = flags['average_duration'] > 30

    response = ""

    if flags['best_champs'] is not None:
        response += "You seem to play " + html_surround(best_champ.get_name()) + " a lot. "
        if flags['played_best_champ']:
            response += "That's good, because you seem to be winning with that champion. "
            if flags['best_champ_well']:
                response += "Even better you end up with a great KDA at " + html_surround(round(flags['best_champ_kda'], 2), "i") + ". "
        else:
            response += "However you haven't been playing them recently. "
            if flags['best_champ_well']:
                response += ("That kind of sucks because you seem to do well with them with a KDA of "
                    + html_surround(round(flags['best_champ_kda'], 2), "i") + ". "
                )
            else:
                response += ("Consider, though, that your KDA is okay with them. ")

    if flags['won']:
        response += ("Looking at your most recent ranked matches, you seem to be winning. You are going "
            + html_surround(str(flags['wins']) + "-" + str(flags['losses']))
            + " right now. That's pretty good. "
        )

        if flags['lose_kdas'] is not None and flags['average_lose_kda'] > 1:
            response += ("Taking a look at your losses, you don't seem to be doing too badly. Your average KDA in your lost games is "
                + html_surround(str(round(flags['average_lose_kda'], 2)))
                + " which isn't bad. Make sure you're capturing lots of objectives in your games and working together with your team. "
            )

        if flags['long_games']:
            response += "You seem to be having " + html_surround("long games.") + " This can be a good thing and a bad thing. If you are able to, make sure you close out your games early. A mistake later in the game can be a lot of trouble! "
    else:
        response += ("Your most recent ranked matches aren't positive, sadly. You are going "
            + html_surround(str(flags['wins']) + "-" + str(flags['losses']))
            + " right now. Consider trying out some new champions in these lists that may spark for you! "
        )
        if flags['lose_kdas'] is not None and flags['average_lose_kda'] > 1:
            response += "However, your average KDA is definitely not bad in these losses. Make sure you're capturing lots of objectives in your games and working together with your team. "
        else:
            response += "Your average KDAs in these losing games aren't to great. Make sure to play safe and always ward up if you're getting ganked a lot! "

        if flags['long_games']:
            response += "You also seem to be having " + html_surround("long games.") + " If you are ahead in lane, make sure you start to close out the game if you can! If you wait too long, "
            response += "you may be more susceptible to mistakes and champions who scale really well late game, such as Nasus."

    return response

    # return flags

    # TOPIC: You seem to do well on x. You also play a lot of x.

    # CASE: Good thing these are the same champion.

    # CASE: Different champions.
    # INNER CASE: Look at KDAs and see if the popular champion has a sufficient
    #             score, kda. Suggest playing winning champion instead.

    # TOPIC: Look at recent ranked games. How are they doing? What is happening?
    #        look at KDAs. Look at whether win > loss. What champions are they
    #        losing on? Are they playing against counters? Are they playing
    #        champions that they are supposed to do well on?

    # TOPIC: Consider trying a new champion they haven't played before.

    # STRATEGY: flags for certain topics and generate a response based on the flags?
    # STRATEGY: generate topics based responses and put it in the dictionary each moment
    #           for each flag individually

# TODO: temporary fix, unsafe
def html_surround(phrase, tag = "strong"):
    return "<" + tag + ">" + str(phrase) + "</" + tag + ">"

# TODO: implement personal statistics over time. implement counters to the champion
#       and good team archetype to have.
@app.route('/api/stats/<champion>/<role>/')
@cached()
def champion_stats(champion, role):
    champ = db_session.query(ChampionData).filter_by(champion_id = champion, role = role).first()

    days_ago = datetime.datetime.now() - datetime.timedelta(days = 7)
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
        .filter(Match.match_time > days_ago)
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

        # TODO: Need to divide this by the number of matches collected that particular day
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
                    'assists': compile_sorted_champions(champ.get_compiled_weights("assists")),
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
