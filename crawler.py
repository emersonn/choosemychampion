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

# crawler settings
BREADTH = 5
DEPTH = 5

# trackers
PLAYER_LIST = 0
MATCH_COUNT = 0

SESSION = RiotSession(API_KEY)

# grabs all of the featured games available and returns an array of the
# summoners that participated in each of the games
def get_featured():
    featured = SESSION.get_featured()
    print(Fore.GREEN + "SUCCESS! Got featured games." + Fore.RESET)

    print("Gathering participants of featured games...")

    matches = [match for match in featured]
    participants = []
    for match in matches:
        for participant in match['participants']:
            participants.append(participant['summonerName'])

    return participants

# crawls a particular player by the depth and breadth. depth determines
# how deep into the tree that the crawler will go and breadth will determine
# how many matches of that player, and by relation, how many players the crawler
# will also crawl.
def crawl_player(player, depth, breadth):
    global PLAYER_LIST

    if depth != 0:
        print("Crawling player " + Fore.GREEN + str(player) + Fore.RESET + " at depth of " + Fore.BLUE + str(depth) + Fore.RESET + "...")

        matches = SESSION.get_matches(player = player, matches = breadth)
        print(Fore.GREEN + "Got match history. Crawling matches..." + Fore.RESET)

        players = set()

        for match in matches:
            # TODO: implement skipping matches if this match already exists in the database
            match_data = SESSION.get_match(match['matchId'])

            if match_data == []:
                pass

            try:
                store_match(match_data)
            except KeyError:
                print("Could not store match. Sleeping for 5 then breaking.")
                sleep(5)

                break

            # adds the players in the match to the crawl list
            players.update([person['player']['summonerId'] for person in match_data['participantIdentities']])

        # ensures that the current player does not get crawled again which would waste
        # processing time
        players.discard(player)

        global MATCH_COUNT
        PLAYER_LIST += BREADTH - 1
        MATCH_COUNT += len(matches)

        print("Finished crawling player " + Fore.GREEN + str(player) +
            Fore.RESET + ". Now crawling " +
            Fore.BLUE + str(len(players)) + Fore.RESET + " other players." +
            " Player list is now: " + Fore.YELLOW + str(PLAYER_LIST) + Fore.RESET +
            ". " + Fore.YELLOW + str(MATCH_COUNT) + Fore.RESET + " matches have been counted.")

        try:
            for person in random.sample(players, BREADTH):
                crawl_player(person, depth - 1, BREADTH)
        except ValueError:
            print("Reached sample error, sleeping for 5 then continuing...")
            sleep(5)

            pass

    else:
        PLAYER_LIST -= 1

# stores the given match data into the database.
def store_match(given_match):
    print("Made row for match: " + Fore.MAGENTA + str(given_match['matchId']) + Fore.RESET + ".")

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
    print("Attempting to request featured games...")
    participants = get_featured()
    print("Got " + Fore.GREEN + str(len(participants)) + Fore.RESET + " participants.")

    # only 40 summoners can be requested at a time
    del participants[40:]

    ids = SESSION.get_ids(participants)
    search_players = [ids[player]['id'] for player in ids.keys()]

    print("Now attempting to crawl players with breadth of " + str(BREADTH) + " and depth of " + str(DEPTH) + "...")

    # creates the original call stack to crawl players
    for player in search_players:
        crawl_player(player, DEPTH, BREADTH)

    print("Finished crawling database.")

if __name__ == '__main__':
     crawl_database()
