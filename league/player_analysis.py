"""
Player Analysis
Emerson Matson

Generates a textual output of analysis for a player.
"""

from prettylog import PrettyLog

from analysis.crawler import store_match

from league import db

from league.models import Champion
from league.models import Match
from league.models import PlayerData

from machination import StringMachination
from machination import StringState

LOGGING = PrettyLog()


def collect_matches(match_ids, session):
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


def generate_recent_flags(session, player_id, location):
    # Get the 15 most recent matches by the player
    match_list = session.get_match_list(player_id)
    match_list = match_list[:min(15, len(match_list))]

    # Collect the IDs for each match
    match_ids = [match['matchId'] for match in match_list]

    # Attempt to store each match in the database for future retrieval
    collect_matches(match_ids, session)

    # Get the matches that were just stored
    matches = (
        db.session.query(Champion)
        .join(Match)
        .filter(Match.match_id.in_(match_ids))
    )

    # Get the 5 best champions for the player
    player_data = (
        db.session.query(PlayerData.champion_id)
        .filter_by(player_id=player_id, location=location)
        .order_by(PlayerData.won.desc())
        .limit(5)
        .all()
    )

    # Set up basic flags
    flags = {
        'best_champs': [champ[0] for champ in player_data],

        'best_champ': player_data[0][0],
        'best_champ_kda': None,
        'best_champ_played': False,

        'won': {
            'wins': 0,
            'losses': 0
        },

        'durations': [],
        'lose_kdas': []
    }

    # Update flags based on the most recent matches
    for match in matches:
        if match.won:
            flags['won']['wins'] += 1
        else:
            flags['won']['losses'] += 1
            flags['lose_kdas'].append(match.get_kda())

        flags['durations'].append(match.match.match_duration / 60)

        # If the current champion is a 'best champ' store some information
        if match.champion_id in flags['best_champs']:
            flags['played_best_champ'] = True

            flags['best_champ'] = match.champion_id
            flags['best_champ_kda'] = match.get_kda()

    # NOTE: Compiled data from collected data

    # Get the average duration of games
    flags['average_duration'] = (
        reduce(lambda x, y: x + y, flags['durations']) /
        float(len(flags['durations']))
    )

    # If they have lost games store the average lost kda
    if flags['lose_kdas'] is not None:
        flags['average_lose_kda'] = (
            reduce(lambda x, y: x + y, flags['lose_kdas']) /
            float(len(flags['lose_kdas']))
        )

    return flags


def generate_recent_states():
    states = []

    # Won? Do wins > losses?
    def won(args):
        return "winner" if args['wins'] > args['losses'] else "loser"

    def winner(args):
        return "best"

    def loser(args):
        return "best"

    won_st = StringState("won", won, "")
    winner_st = StringState("winner", winner, "You are a winner.")
    loser_st = StringState("loser", loser, "You are a loser.")

    states.extend([
        won_st,
        winner_st,
        loser_st
    ])

    # Do they play their best champ well?


def generate_recent_machination(session, player_id, location):
    flags = generate_recent_flags(session, player_id, location)

    # NOTE: Analysis includes:
    #   Won? Do wins > losses for most recent games
    #   Do they play their best champ well?
    #       Is the best_champ_kda flag over 1? Otherwise if that doesn't exist
    #           we get the kda of the champion from our data instead.
    #   Do they play long games? (Over 30 to 40 minutes?)
    #   If they have lost kdas, is that minimized?
    states = generate_recent_states()
    mach = StringMachination(states, states[0])

    return mach.run(flags, " ")
