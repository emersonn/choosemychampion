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
    """Takes match ids and stores those matches in the database

    Args:
        match_ids: List of ints which are match ids to store
        session: RiotSession object
    """

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
    """Creates a flags dictionary for the given player

    Args:
        session: RiotSession object
        player_id: int representing the Riot's given Player ID
        location: Riot's location representation

    Returns:
        dictionary: Dictionary of strings to any type of data
            See setup for more information.
    """

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
        # NOTE: State arguments
        'won': {
            'wins': 0,
            'losses': 0
        },

        'loser': {
            'best_champ_played': False
        },

        'long_games': {
            'average_duration': None
        },

        # NOTE: Intermediate calculations
        'durations': [],
        'lose_kdas': [],

        'best_champs': [champ[0] for champ in player_data],
        'best_champ': player_data[0][0],
        'best_champ_kda': None,

        # NOTE: Placeholders for states
        'winner': None,

        'best_yes': None,
        'best_no': None,

        'long_games_yes': None,
        'long_games_no': None
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
            flags['loser']['best_champ_played'] = True

            flags['best_champ'] = match.champion_id
            flags['best_champ_kda'] = match.get_kda()

    # NOTE: Compiled data from collected data

    # Get the average duration of games
    flags['long_games']['average_duration'] = (
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


def generate_won_states():
    """Generates won states.

    Returns:
        List: List of StringStates representing the won states.
            Default winner moves to 'long_games.'
            Default loser analyzes best champs and moves accordingly.
                'best_yes' otherwise 'best_no'
    """

    # Won? Do wins > losses?
    def won(args):
        """Move to winner if wins > losses, otherwise loser"""
        return "winner" if args['wins'] > args['losses'] else "loser"

    def winner(args):
        """Skip directly to long games if they have been winning"""
        return "long_games"

    def loser(args):
        """Move to a best champ state based on performance"""
        return "best_yes" if args['best_champ_played'] else "best_no"

    won_st = StringState("won", won, "")
    winner_st = StringState("winner", winner, "You are a winner.")
    loser_st = StringState("loser", loser, "You are a loser.")

    return [won_st, winner_st, loser_st]


def generate_best_states():
    # Do they play their best champ? Most importantly, do they play it well?
    def best_yes(args):
        return "long_games"

    def best_no(args):
        return "long_games"

    best_yes_st = StringState(
        "best_yes", best_yes, "You play your best champ."
    )

    best_no_st = StringState(
        "best_no", best_no, "You don't play your best champ."
    )

    return [best_yes_st, best_no_st]


def generate_time_states():
    def long_games(args):
        return (
            "long_games_yes" if args['average_duration'] > 40
            else "long_games_no"
        )

    def long_games_yes(args):
        return None

    def long_games_no(args):
        return None

    long_games_st = StringState(
        'long_games', long_games, ""
    )

    yes_st = StringState(
        'long_games_yes', long_games_yes, "You play long games."
    )

    no_st = StringState(
        'long_games_no', long_games_no, "You don't play long games."
    )

    return [long_games_st, yes_st, no_st]


def generate_recent_states():
    """Generates states for recent games.

    Returns:
        List: List of states where the states represent an analysis of
            the player's most recent games, and improvement
            strategies.
    """

    states = []

    states.extend(generate_won_states())
    states.extend(generate_best_states())

    return states


def generate_recent_machination(session, player_id, location):
    """Generates a Machination for the given player based on recent games.

    Args:
        session: RiotSession object.
        player_id: Player ID given by Riot.
        location: Riot abbreviation for location.

    Returns:
        string: String output of the Machination based on the player.
            This would be an analysis of the player's most recent games.
    """

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
