"""
Player Analysis
Emerson Matson

Generates a textual output of analysis for a player.
"""

from league import db

from league.models import Champion
from league.models import Match
from league.models import PlayerData

from machination import StringMachination
from machination import StringState


def collect_matches(match_ids):
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


def generate_flags(session, player_id, location):
    # Get the 15 most recent matches by the player
    match_list = session.get_match_list(player_id)
    match_list = match_list[:min(15, len(match_list))]

    # Collect the IDs for each match
    match_ids = [match['matchId'] for match in match_list]

    # Attempt to store each match in the database for future retrieval
    collect_matches(match_ids)

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

    # Get all player matches
    player_matches = matches.filter(Champion.player_id == player_id).all()

    flags = {
        'best_champs': [champ[0] for champ in player_data],
        'best_champ': player_data[0][0],
        'best_champ_played': False,

        'wins': 0,
        'losses': 0

        'durations': []
        'lose_kdas': []
    }

    for match in player_matches:
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

    return flags

def generate_machination(session, player_id, location):
    flags = generate_flags(session, player_id, location)
    return flags
