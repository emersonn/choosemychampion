import datetime
import random
from time import sleep

# TODO: fix this. there are warnings about python 2.7 and also
# SSL. maybe need to implement SSL because using HTTPS in the
# requests?
import logging
logging.captureWarnings(True)

from colorama import Fore, Back, Style
import requests
import sqlalchemy

# TODO: make this into a module so these are imported less relatively
from database import db_session
from models import Match, Champion, BannedChampion, BuiltItems
from settings import API_KEY, URLS
from riot import RiotSession
from prettylog import PrettyLog

# crawler settings
BREADTH = 15
DEPTH = 15

# trackers
PLAYER_LIST = 0
MATCH_COUNT = 0

SESSION = RiotSession(API_KEY)
LOGGING = PrettyLog()

# grabs all of the featured games available and returns an array of the
# summoners that participated in each of the games
def get_featured():
    featured = SESSION.get_featured()
    LOGGING.push("Success. Got featured games.")
    LOGGING.push("Getting participants of featured games...")

    matches = [match for match in featured]
    participants = []
    for match in matches:
        for participant in match['participants']:
            participants.append(participant['summonerName'].encode('utf-8'))

    return participants

# crawls a particular player by the depth and breadth. depth determines
# how deep into the tree that the crawler will go and breadth will determine
# how many matches of that player, and by relation, how many players the crawler
# will also crawl.
def crawl_player(player, depth, breadth):
    global PLAYER_LIST

    if depth != 0:
        LOGGING.push("Crawling player *'" + str(player) + "'* at a depth of @" + str(DEPTH - depth) + "@.")

        matches = SESSION.get_match_list(player = player)
        LOGGING.push("Got match history. Logging matches.")

        players = set()

        for match in matches[:min(15, len(matches))]:
            # TODO: inefficient. checks every match, maybe check by player match history for all of them?
            check_match = db_session.query(Match).filter(Match.match_id == match['matchId']).count()
            match_data = SESSION.get_match(match['matchId'])

            if match_data == {}:
                break

            try:
                if check_match >= 1:
                    LOGGING.push("*" + str(match['matchId']) + "* already exists in the database. Skipping storage.")
                elif check_match == 0:
                    store_match(match_data)
            except KeyError:
                LOGGING.push("#Could not store match. Continuing.#")
                continue

            # adds the players in the match to the crawl list
            players.update([person['player']['summonerId'] for person in match_data['participantIdentities']])

        # ensures that the current player does not get crawled again which would waste
        # processing time
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

# stores the given match data into the database.
def store_match(given_match):
    LOGGING.push("Made row for match *'" + str(given_match['matchId']) + "'*.")

    # generates the match and saves it in the database.
    match = Match(match_id = given_match['matchId'],
        match_time = datetime.datetime.fromtimestamp(given_match['matchCreation'] / 1000),
        match_duration = given_match['matchDuration'])
    db_session.add(match)

    # the bans is created as a set of champion ids
    bans = set()

    # goes through each participant in the match participant list
    for participant in given_match['participants']:
        participant_identity = participant['participantId']

        # TODO: make this more clear. it is a search through identities to find the team and the
        #       actual player in the match data.

        # iterates through the participant identities and tries to find the exact participant
        # in the match, but also attempts to find the exact team.
        person = (item for item in given_match['participantIdentities'] if item['participantId'] == participant_identity).next()
        team = (item for item in given_match['teams'] if item['teamId'] == participant['teamId']).next()

        # temporary stat variable to make typing easier
        stats = participant['stats']

        # creates a new champion instance and adds it to the database session
        champion = Champion(champion_id = participant['championId'],
            player_id = person['player']['summonerId'], team_id = participant['teamId'],
            won = team['winner'], role = participant['timeline']['lane'],
            kills = stats['kills'], deaths = stats['deaths'], assists = stats['assists'],
            damage = stats['totalDamageDealt'],
            objective_score = team['baronKills'] + team['dragonKills'],
            tower_score = team['towerKills'], match_id = match.match_id,
            match = match)
        db_session.add(champion)

        # iterates through the items built by this particular player
        # and saves it into the database
        for item_num in range(7):
            item = BuiltItems(item_id = stats['item' + str(item_num)],
                champion_id = champion.champion_id,
                champion = champion)
            db_session.add(item)

        # TODO: make this more efficient. although it is easy it is continually
        # attempting to add to the set a banned champion for every single person.
        # iterates through the bans and adds it to the set. also this gives an error
        # sometimes?
        for ban in team['bans']:
            bans.add(ban['championId'])

    # iterates through the ban set and adds them to the database session as a BannedChampion
    for ban in bans:
        banned_champion = BannedChampion(champion_id = ban, match_id = match.match_id,
            match = match)
        db_session.add(banned_champion)
    db_session.commit()

# attempts to crawl the API using the featured games as a starting point and going
# deeper through player matches and their relative coplayers
def crawl_database():
    LOGGING.push("Attempting to request featured games.")
    participants = get_featured()
    LOGGING.push("Got @" + str(len(participants)) + "@ participants.")

    # only 40 summoners can be requested at a time
    participants = random.sample(participants, min(40, len(participants)))

    ids = SESSION.get_ids(participants)
    search_players = [ids[player]['id'] for player in ids.keys()]

    LOGGING.push("Now attempting to crawl players with a breadth of @" + str(BREADTH) + "@ and depth of ^" + str(DEPTH) + "^.")

    # creates the original call stack to crawl players
    for player in search_players:
        crawl_player(player, DEPTH, BREADTH)

    LOGGING.push("Finished crawling database.")

if __name__ == '__main__':
     crawl_database()
