import datetime
from functools import wraps
import operator
import urllib

# TODO(Fix this. Related to SSL.)
import logging
logging.captureWarnings(True)

from flask import abort
from flask import jsonify
from flask import request
from flask import send_file

from sqlalchemy import func, Integer

from league import app
from league import db

from models import Champion
from models import ChampionData
from models import Match
from models import PlayerData

from leaguepy import RiotSession

from prettylog import PrettyLog

# TODO(Abstract out store_match to avoid this.)
from analysis.crawler import store_match

from settings import API_KEY
from settings import CACHE

LOGGING = PrettyLog()


@app.teardown_appcontext
def shutdown_session(exception=None):
    db.session.remove()


def cached(timeout=10 * 60, key='view/%s'):
    """Cache decorator for app functions.

    Args:
        timeout: Timeout for the cache.
        key: Storage key for the request.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            cache_key = key % request.path
            rv = CACHE.get(cache_key)
            if rv is not None:
                return rv
            rv = f(*args, **kwargs)
            CACHE.set(cache_key, rv, timeout=timeout)
            return rv
        return decorated_function
    return decorator


@app.route('/')
def index():
    return send_file('static/index.html')


@app.route('/api/champions/<username>/<location>/')
def profile(username, location):
    """Gathers champion statistics for a particular user.

    Args:
        username: The urlencoded username of the summoner.
        location: Riot abbreviation for regions.
    """

    try:
        LOGGING.push(
            "*'" + username + "'* from @'" + location +
            "'@ is requesting their user ID."
        )
        # TODO(Save the ID lookup in the database.)
        session = RiotSession(API_KEY, location)
        response = session.get_ids([urllib.pathname2url(username)])

        # TODO(Should use the username as the key to be consistent.)
        user_id = response[response.keys()[0]]['id']

    # TODO(Fix this to catch both 429 and 400 errors.)
    #       Use a new exception. Handle through Riot. Handle w/ status cocde.
    except ValueError:
        LOGGING.push(
            "Tried to get *'" + username +
            "'*'s id. Response did not have user id."
        )
        abort(400)

    return stats(username, user_id, location)

# Implement using @cached(). May need request URL?


def stats(username, user_id, location):
    """Gathers champion statistics given a particular user.

    Args:
        username: The actual username of the user.
        user_id (int): The summoner ID of the user.
        location: Riot abbreviated region.
    """

    rv = CACHE.get('user_data_' + str(user_id))
    if rv is None:
        query = (
            db.session.query(PlayerData)
            .filter_by(player_id=user_id, location=location)
            .all()
        )

        # TODO(Abstract this timer out into a constant.)
        thirty_minutes_ago = (
            datetime.datetime.now() - datetime.timedelta(minutes=30)
        )
        if len(query) > 0 and query[0].updated < thirty_minutes_ago:
            LOGGING.push("*'" + username + "'* has old data. Resetting stats.")
            reset_stats(username, user_id, location)
            query = []

        has_ranked = True

        if len(query) == 0:
            try:
                LOGGING.push(
                    "*'" + username + "'* from @'" + location +
                    "'@ does not exist in the database. Creating model."
                )

                session = RiotSession(API_KEY, location)

                try:
                    user_data = session.get_stats(user_id)
                except ValueError:
                    LOGGING.push(
                        "Looks like *" + username + "* doesn't" +
                        " have any ranked matches."
                    )

                    user_data = {'champions': []}
                    has_ranked = False

                build_stats(user_data, username, location)

                query = (
                    PlayerData.query
                    .filter_by(player_id=user_id, location=location)
                    .all()
                )

            # TODO(Make this a more descriptive error.)
            except KeyError:
                abort(429)

        # TODO(Restructure this so it doesn't make multiple query requests.)
        analyzed_player = (
            analyze_player(user_id, location) if has_ranked
            else "No analysis available."
        )

        full_stats = {'scores': []}
        index = 1

        query = ChampionData.query.all()

        # TODO(This is vastly inefficient.)

        # attempts to go through all the champion data and generate the
        # array of score information for each champion. this also appends
        # user data and user adjustments to the data.
        for champion in query:
            # attempts to go through each of the players champions when playing
            # this champion and gets their adjustment for the score

            # TODO(Implement role? is role not included in this calculation?)
            user_query = (
                PlayerData.query
                .filter_by(
                    player_id=user_id,
                    location=location,
                    champion_id=champion.champion_id
                )
                .first()
            )

            if user_query is None:
                adjustment = 0
            else:
                adjustment = user_query.get_adjustment()

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
                'calculated': (
                    champion.get_calculated_win(user_id, location) * 100
                ),
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
        CACHE.set('user_data_' + str(user_id), full_stats, timeout=1 * 60)
        return jsonify(full_stats)
    else:
        return jsonify(rv)

# TODO(Implement limiting for multiple champions of the same role.)


def popular_counters(role, limit=1, counter_limit=5):
    champion = (
        db.session.query(ChampionData)
        .filter_by(role=role)
        .order_by(ChampionData.num_seen.desc())
        .limit(limit)
        .first()
    )

    return {
        'champion': {
            'champion_name': champion.get_name()
        },
        'counters': compile_sorted_champions(
            champion.get_compiled_weights("counters")
        )[:5]
    }

# TODO(Consider exceptions that may occur, use a try/except when getting it.
#       also clean this up greatly. it can be cleaned up a lot.)


def analyze_player(player_id, location):
    """Analyzes a player for recent game statistics.

    Args:
        player_id: The Riot player_id for the player in question.
        location: The abbreviated location for the particular player.
    """

    LOGGING.push(
        "Player analysis for *'" +
        str(player_id) + "'* is being created."
    )

    flags = {}

    session = RiotSession(API_KEY, location)

    # TODO(Maybe reduce requests by storing the updated time?)
    match_list = session.get_match_list(player_id)
    match_list = match_list[:min(15, len(match_list))]
    match_ids = [match['matchId'] for match in match_list]

    for match in match_ids:
        check_match = (
            db.session.query(Match)
            .filter(Match.match_id == match)
            .count()
        )
        if check_match == 0:
            match_data = session.get_match(match)
            try:
                store_match(match_data)
            except KeyError:
                LOGGING.push("Could not store match *'" + str(match) + "'*.")
        else:
            LOGGING.push(
                "*'" + str(match) +
                "'* already exists in the database."
            )

    matches = (
        db.session.query(Champion)
        .join(Match)
        .filter(Match.match_id.in_(match_ids))
    )

    player_data = (
        db.session.query(PlayerData.champion_id)
        .filter_by(player_id=player_id, location=location)
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

    best_champ = (
        db.session.query(ChampionData)
        .filter_by(champion_id=flags['best_champ'])
        .first()
    )

    if flags['best_champ'] is not None:
        # TODO(Kind of arbitrary number of kda. only ensures they're positive.)
        flags['best_champ_well'] = flags['best_champ_kda'] > 1
    else:
        flags['best_champ_well'] = (
            db.session.query(PlayerData)
            .filter_by(champion_id=flags['best_champ'])
            .first()
            .get_kda() > 1
        )

    flags['average_duration'] = (
        reduce(lambda x, y: x + y, flags['durations']) /
        float(len(flags['durations']))
    )

    if flags['lose_kdas'] is not None:
        flags['average_lose_kda'] = (
            reduce(lambda x, y: x + y, flags['lose_kdas']) /
            float(len(flags['lose_kdas']))
        )

    flags['long_games'] = flags['average_duration'] > 30

    response = ""

    if flags['best_champs'] is not None:
        response += (
            "You seem to play " +
            html_surround(best_champ.get_name()) + " a lot. "
        )

        if flags['played_best_champ']:
            response += (
                "That's good, because you seem " +
                "to be winning with that champion. "
            )
            if flags['best_champ_well']:
                response += (
                    "Even better you end up with a great KDA at " +
                    html_surround(round(flags['best_champ_kda'], 2), "i") +
                    ". "
                )
        else:
            response += "However you haven't been playing them recently. "
            if flags['best_champ_well']:
                response += (
                    "That kind of sucks because you seem " +
                    "to do well with them with a KDA of " +
                    html_surround(round(flags['best_champ_kda'], 2), "i") +
                    ". "
                )
            else:
                response += (
                    "Consider, though, that your KDA is " +
                    "okay with them. "
                )

    if flags['won']:
        response += (
            "Looking at your most recent ranked matches, you " +
            "seem to be winning. You are going " +
            html_surround(str(flags['wins']) + "-" + str(flags['losses'])) +
            " right now. That's pretty good. "
        )

        if flags['lose_kdas'] is not None and flags['average_lose_kda'] > 1:
            response += (
                "Taking a look at your losses, you don't seem to be doing " +
                "too badly. Your average KDA in your lost games is " +
                html_surround(str(round(flags['average_lose_kda'], 2))) +
                " which isn't bad. Make sure you're capturing lots of " +
                "objectives in your games and working together " +
                "with your team. "
            )

        if flags['long_games']:
            response += (
                "You seem to be having " +
                html_surround("long games.") +
                " This can be a good thing and a bad thing. " +
                "If you are able to, make sure you close out your games " +
                "early. A mistake later in the game can be a lot of trouble! "
            )
    else:
        response += (
            "Your most recent ranked matches aren't " +
            "positive, sadly. You are going " +
            html_surround(str(flags['wins']) + "-" + str(flags['losses'])) +
            " right now. Consider trying out some new champions in these " +
            "lists that may spark for you! "
        )
        if flags['lose_kdas'] is not None and flags['average_lose_kda'] > 1:
            response += (
                "However, your average KDA is definitely not bad in " +
                "these losses. Make sure you're capturing lots of " +
                "objectives in your games and working " +
                "together with your team. "
            )
        else:
            response += (
                "Your average KDAs in these losing games " +
                "aren't too great. Make sure to play safe and always " +
                "ward up if you're getting ganked a lot! "
            )

        if flags['long_games']:
            response += (
                "You also seem to be having " +
                html_surround("long games. ") +
                "If you are ahead in lane, make sure you start " +
                "to close out the game if you can! If you wait too long, " +
                "you may be more susceptible to mistakes and " +
                "champions who scale really well late game, such as Nasus."
            )

    return response

# TODO(Temporary fix. Kind of unsafe?)


def html_surround(phrase, tag="strong"):
    """Surrounds a particular phrase in an HTML non-self-closing tag.

    Args:
        phrase: Phrase to put into the tags.
        tag: The HTML tag to surround the text with.

    Returns:
        String: The surrounded phrase in given HTML tag.
    """

    return "<" + tag + ">" + str(phrase) + "</" + tag + ">"

# TODO(Implement personal statistics over time, and team archetype.)


@app.route('/api/stats/<champion>/<role>/')
@cached()
def champion_stats(champion, role):
    """Gives detailed champion stats for a particular champion.

    Args:
        champion: Champion ID for the champion in question.
        role: The role that the champion players.

    Returns:
        json: JSON formatted response for the champion statistics.
    """

    champ = (
        db.session.query(ChampionData)
        .filter_by(champion_id=champion, role=role)
        .first()
    )

    days_ago = datetime.datetime.now() - datetime.timedelta(days=7)
    champ_list = (
        db.session.query(
            Champion.champion_id.label("champion_id"),
            func.count(Champion.id).label("num_seen"),
            func.avg(Champion.won, type_=Integer).label("won"),
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

        'counters': compile_sorted_champions(
            champ.get_compiled_weights("counters")
        ),
        'assists': compile_sorted_champions(
            champ.get_compiled_weights("assists")
        ),

        # TODO(Need to divide this by the number of matches collected.)
        #       This is for that particular day.
        'days_seen': {
            'labels': [data.match_time.strftime(
                "%b %d (%A)"
            ) for data in champ_list],
            'data': [data.num_seen for data in champ_list]
        },

        'days_won': {
            'labels': [data.match_time.strftime(
                "%b %d (%A)"
            ) for data in champ_list],
            'data': [round(data.won, 2) for data in champ_list]
        }
    }

    return jsonify(stats)

# TODO(Maybe do this at the model level?)


def compile_sorted_champions(listing, reverse=True):
    """Compiles the sorted champion list into detailed information.

    Args:
        listing: Sorted champion list.
        reverse: Whether the list should be sorted in reverse.
            Defaults to True.

    Returns:
        dict: Dictionary of champion data.
    """
    sorted_listing = sorted(
        listing.items(),
        key=operator.itemgetter(1),
        reverse=reverse
    )
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


# TODO(Call all new adjustments they may need.)

def reset_stats(username, user_id, location):
    """Resets user statistics in the database.

    Args:
        username: Username of the particular user.
        user_id: Riot's id for the summoner.
        location: Riot's abbreviation for the region.
    """

    (
        PlayerData.query
        .filter_by(player_id=user_id, location=location)
        .delete()
    )

    db.session.commit()

    CACHE.delete('user_data_' + str(user_id))

    LOGGING.push(
        "Resetting stats for *'" +
        username + "'* from @'" +
        location + "'@."
    )

# TODO(Improve loading times of this.)
#       Cache the numbers for longer? Preprocess the numbers?


@app.route('/api/numbers/')
@cached()
def numbers():
    """Gives a summary of champion statistics.

    Returns:
        json: JSON formatted champion statistic summary.
    """

    popular_champ = (
        db.session.query(ChampionData)
        .order_by(ChampionData.num_seen.desc())
        .first()
    )

    popular_champs = (
        db.session.query(ChampionData)
        .order_by(ChampionData.num_seen.desc())
        .limit(15)
        .all()
    )

    random_champ = (
        db.session.query(ChampionData)
        .order_by(func.rand())
        .first()
    )

    winning_champ = (
        db.session.query(ChampionData)
        .filter(ChampionData.num_seen > 10)
        .order_by(ChampionData.score.desc())
        .first()
    )

    winning_champ_roles = (
        db.session.query(
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
            'average_kills': round(
                db.session.query(
                    func.avg(ChampionData.kills)
                )
                .first()[0], 2
            ),
            'average_towers': round(
                db.session.query(
                    func.avg(ChampionData.tower_score)
                ).first()[0], 2
            )
        },

        'champion_picks': {
            'labels': [
                champ.get_name() + " (" +
                champ.role.capitalize() + ")" for champ in popular_champs
            ],
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
            'assists': compile_sorted_champions(
                champ.get_compiled_weights("assists")
            ),
            'kda': winning_champ.get_kda(),

            'role_distribution': {
                'labels': [
                    data.role.capitalize() for data in winning_champ_roles
                ],
                'data': [data.seen for data in winning_champ_roles]
            }
        }
    }
    return jsonify(stats)


def build_stats(data, username, location):
    """Builds stats based on a given player's performance.

    Args:
        data: Riot JSON response to the 'stats' query.
        username: Username for the particular player.
        location: Location abbreviation for region.
    """

    for champion in data['champions']:
        if champion['id'] != 0:
            total_stats = champion['stats']
            new_player = PlayerData(
                player_id=data['summonerId'],
                player_name=username,
                location=location,
                champion_id=champion['id'],
                updated=datetime.datetime.today(),
                sessions_played=total_stats['totalSessionsPlayed'],
                kills=total_stats['totalChampionKills'],
                deaths=total_stats['totalDeathsPerSession'],
                assists=total_stats['totalAssists'],
                won=total_stats['totalSessionsWon']
            )
            db.session.add(new_player)
    db.session.commit()
