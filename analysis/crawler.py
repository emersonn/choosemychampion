import datetime
import random

# TODO: Fix this.
import logging
logging.captureWarnings(True)

# TODO: Make League into a package.
from league import db

from league.models import Match, Champion, BannedChampion, BuiltItems

from league.settings import API_KEY

from leaguepy import RiotSession

from league.prettylog import PrettyLog

# Crawler settings.
BREADTH = 15
DEPTH = 15

# Trackers
PLAYER_LIST = 0
MATCH_COUNT = 0

SESSION = RiotSession(API_KEY)
LOGGING = PrettyLog()


def get_featured():
    """ Grabs all featured games available.

    Returns:
        list: Summoners that participated in each of the featured games
    """

    featured = SESSION.get_featured()
    LOGGING.push("Success. Got featured games.")
    LOGGING.push("Getting participants of featured games...")

    matches = [match for match in featured]
    participants = []
    for match in matches:
        for participant in match['participants']:
            participants.append(participant['summonerName'].encode('utf-8'))

    return participants


def crawl_player(player, depth, breadth):
    """ Crawls a particular player.

    Args:
        player: Particular player's id.
        depth: How deep the crawler will explore in the matches.
        breadth: How many players in the same games the crawler will explore.
    """

    global PLAYER_LIST

    if depth != 0:
        LOGGING.push(
            "Crawling player *'" + str(player) +
            "'* at a depth of @" + str(DEPTH - depth) + "@."
        )

        matches = SESSION.get_match_list(player=player)
        LOGGING.push("Got match history. Logging matches.")

        players = set()

        for match in matches[:min(15, len(matches))]:
            # TODO: inefficient. checks every match, maybe check by player
            #       match history for all of them?
            check_match = (
                db.session.query(Match)
                .filter(Match.match_id == match['matchId'])
                .count()
            )

            match_data = SESSION.get_match(match['matchId'])

            if match_data == {}:
                break

            try:
                if check_match >= 1:
                    LOGGING.push(
                        "*" + str(match['matchId']) +
                        "* already exists in the database. Skipping storage."
                    )
                elif check_match == 0:
                    store_match(match_data)
            except KeyError:
                LOGGING.push("#Could not store match. Continuing.#")
                continue

            # adds the players in the match to the crawl list
            players.update(
                [
                    person['player']['summonerId'] for person
                    in match_data['participantIdentities']
                ]
            )

        # ensures that the current player does not get crawled again
        players.discard(player)

        global MATCH_COUNT
        PLAYER_LIST += BREADTH - 1
        MATCH_COUNT += len(matches)

        # TODO: implement player list count. player list is now: example.
        LOGGING.push(
            "Finished crawling player *'" +
            str(player) +
            "'*. Now crawling @" +
            str(len(players)) +
            "@ other players. ^" +
            str(MATCH_COUNT) +
            "^ matches have been counted."
        )

        for person in random.sample(players, min(BREADTH, len(players))):
            crawl_player(person, depth - 1, BREADTH)

    else:
        PLAYER_LIST -= 1


def store_match(given_match):
    """ Stores the match in the database.

    Args:
        given_match: Particular match data from Riot's Match API.
    """

    LOGGING.push("Made row for match *'" + str(given_match['matchId']) + "'*.")

    # generates the match and saves it in the database.
    match = Match(
        match_id=given_match['matchId'],
        match_time=datetime.datetime.fromtimestamp(
            given_match['matchCreation'] / 1000
        ),
        match_duration=given_match['matchDuration']
    )
    db.session.add(match)

    # the bans is created as a set of champion ids
    bans = set()

    # goes through each participant in the match participant list
    for participant in given_match['participants']:
        participant_identity = participant['participantId']

        # TODO: make this more clear. it is a search through identities
        #       to find the team and the actual player in the match data.

        # iterates through the participant identities and tries to find the
        # exact participant in the match, but also attempts
        # to find the exact team.
        person = (
            item for item in given_match['participantIdentities']
            if item['participantId'] == participant_identity
        ).next()

        team = (
            item for item in given_match['teams']
            if item['teamId'] == participant['teamId']
        ).next()

        # temporary stat variable to make typing easier
        stats = participant['stats']

        # creates a new champion instance and adds it to the database session
        champion = Champion(
            champion_id=participant['championId'],
            player_id=person['player']['summonerId'],
            team_id=participant['teamId'],
            won=team['winner'],
            role=participant['timeline']['lane'],
            kills=stats['kills'],
            deaths=stats['deaths'],
            assists=stats['assists'],
            damage=stats['totalDamageDealt'],
            objective_score=team['baronKills'] + team['dragonKills'],
            tower_score=team['towerKills'],
            match_id=match.match_id,
            match=match
        )

        db.session.add(champion)

        # iterates through the items built by this particular player
        # and saves it into the database
        for item_num in range(7):
            item = BuiltItems(
                item_id=stats['item' + str(item_num)],
                champion_id=champion.champion_id,
                champion=champion
            )
            db.session.add(item)

        # TODO: make this more efficient. although it is easy it is continually
        # attempting to add to the set a banned champion for every
        # single person. iterates through the bans and adds it to the set.
        # also this gives an error sometimes?
        for ban in team['bans']:
            bans.add(ban['championId'])

    # iterates through the ban set and adds them
    # to the database session as a BannedChampion
    for ban in bans:
        banned_champion = BannedChampion(
            champion_id=ban,
            match_id=match.match_id,
            match=match
        )
        db.session.add(banned_champion)
    db.session.commit()


def crawl_database():
    """ Crawls the Riot API using featured games as a starting point.
    """

    LOGGING.push("Attempting to request featured games.")
    participants = get_featured()
    LOGGING.push("Got @" + str(len(participants)) + "@ participants.")

    # only 40 summoners can be requested at a time
    participants = random.sample(participants, min(40, len(participants)))

    ids = SESSION.get_ids(participants)
    search_players = [ids[player]['id'] for player in ids.keys()]

    LOGGING.push(
        "Now attempting to crawl players with a breadth of @" +
        str(BREADTH) + "@ and depth of ^" + str(DEPTH) + "^."
    )

    # creates the original call stack to crawl players
    for player in search_players:
        crawl_player(player, DEPTH, BREADTH)

    LOGGING.push("Finished crawling database.")

if __name__ == '__main__':
    crawl_database()
