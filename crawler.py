from colorama import Fore, Back, Style
from time import sleep
import sqlalchemy, requests, datetime, random

# todo: fix this. there are warnings about python 2.7 and also
# SSL. maybe need to implement SSL because using HTTPS in the
# requests?
import logging
logging.captureWarnings(True)

# todo: make this into a module so these are imported less relatively
from database import db_session
from models import Match, Champion, BannedChampion, BuiltItems
from settings import API_KEY, URLS

# crawler settings
BREADTH = 5
DEPTH = 3

# trackers
PLAYER_LIST = 0
MATCH_COUNT = 0

# grabs all of the featured games available and returns an array of the
# summoners that participated in each of the games
def get_featured():
    full_url = URLS['featured'] + API_KEY
    r = requests.get(full_url)
    print(Fore.GREEN + "SUCCESS! Got featured games." + Fore.RESET)

    # todo: add error checking to see if the request was throttled w/
    # a 429 error. otherwise this will break.
    featured = r.json()['gameList']

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

# this method uses recursion. the base case is having a depth of 0 in which
# there will be no crawling and nothing is stored. the recursive case is
# when there is a player and the depth is not 0. the crawler will grab the matches
# and store data related to the matches
def crawl_player(player, depth, breadth):
    # this is to avoid overloading the servers and being timed out
    sleep(1)

    # if not the base case. we are in the recursive case
    if depth != 0:
        print("Crawling player " + Fore.GREEN + str(player) + Fore.RESET + " at depth of " + Fore.BLUE + str(depth) + Fore.RESET + "...")

        # add a try/except in which it catches if the request actually returned an error! do
        # not want to try to crawl if that happens, b/c program breaks, r.status_code == 429
        r = requests.get(URLS['matches'] + str(player), params = {'api_key': API_KEY, 'rankedQueues': 'RANKED_SOLO_5x5', 'endIndex': BREADTH})

        # todo: maybe modify these multiline crawler messages? they kind of take up
        # the whole console room...
        print("Projected processing time on this player: " + Fore.BLUE +
        str((breadth ** depth) * 15) + Fore.RESET + " seconds.")
        print(Fore.GREEN + "Got match history. Crawling matches: " + Fore.RESET + "["),

        # generates a set for the
        players = set()

        # todo: fix this. this is only a temporary fix to catch if there were no matches
        # want to check for an error code instead
        try:
            r.json()['matches']
        except KeyError:
            print("No matches found in this request. ]")
            print("Exiting this user and sleeping for 20 seconds.")

            sleep(20)
            return
        except ValueError:
            print("No JSON in this request. ]")
            print("Exiting this user and sleeping for 20 seconds.")

            sleep(20)
            return

        for match in r.json()['matches']:
            # print(Fore.GREEN + "Found match: " + Fore.RESET + str(match['matchId']) + " " +
            #    str(datetime.datetime.fromtimestamp(match['matchCreation'] / 1000)) + " " +
            #    str(match['matchDuration']))
            sleep(1)

            # todo: implement skipping matches if the match has already been crawled in this
            # session or another session. multiple matches may obscufate data. and match_data
            # returns an error if get_match_data.json() does not exist.
            get_match_data = requests.get(URLS['match'] + str(match['matchId']), params = {'api_key': API_KEY})
            try:
                match_data = get_match_data.json()
            except ValueError:
                print("Could not get match data, sleeping for 20 then breaking...")
                sleep(20)

                break

            # todo: separates the match printing. may need to fix w/ python 3+
            print("."),

            store_match(match_data)

            # adds the players in the match to the crawl list
            participants = match_data['participantIdentities']
            for person in participants:
                players.add(person['player']['summonerId'])

        # finishes the line of output for the match
        print("]")

        # ensures that the current player does not get crawled again which would waste
        # processing time
        players.discard(player)

        # todo: fix this. python gives a warning w/ global variables. furthermore
        # the numbers that it gives is sometimes incorrect and needs to be fixed.
        # the counting may not always be on.
        global PLAYER_LIST
        global MATCH_COUNT
        PLAYER_LIST += BREADTH - 1
        MATCH_COUNT += len(r.json()['matches'])

        print("Finished crawling player " + Fore.GREEN + str(player) +
            Fore.RESET + ". Now crawling " +
            Fore.BLUE + str(len(players)) + Fore.RESET + " other players." +
            " Player list is now: " + Fore.YELLOW + str(PLAYER_LIST) + Fore.RESET +
            ". " + Fore.YELLOW + str(MATCH_COUNT) + Fore.RESET + " matches have been counted.")

        # todo: error? ValueError, sample larger than population

        # recursive call. goes through a random sample of players in the breadth
        # and crawls those players.
        try:
            for person in random.sample(players, BREADTH):
                crawl_player(person, depth - 1, BREADTH)
        except ValueError:
            print("Reached sample error, sleeping for 20 then fixing...")
            sleep(20)

            pass

    else:
        global PLAYER_LIST
        PLAYER_LIST -= 1

# stores the given match data into the database. furthermore it stores all the items
# and banned champions.
def store_match(given_match):
    # todo: fix this. it doesn't print on a new line but this may be broken in
    # python 3.
    print("Made row for match: " + Fore.MAGENTA + str(given_match['matchId']) + Fore.RESET + "."),

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

        # todo: make this more efficient. although it is easy it is continually
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

# the called method when running the python file. attempts to crawl the database through
# featured games and using recursive branching in order to create a database file
# with match, and participant data for later analysis and usage.
def crawl_database():
    print("Attempting to request featured games...")
    participants = get_featured()
    print("Got " + Fore.GREEN + str(len(participants)) + Fore.RESET + " participants.")

    # todo: maybe put all requests in a particular method to regulate sleeping of the
    # program and make it more consistent. also it would be easier to catch if errors
    # had occurred and sleep because of that.
    sleep(1)

    # only 40 summoners can be requested at a time
    del participants[40:]

    # todo: fix all urls because API is as a parameter and it becomes repetitive to
    # write all the API_KEY parts
    r = requests.get(URLS['ids'] + ','.join(participants), params = {'api_key': API_KEY})

    # iterates through the array in the json file and adds the player ids to the list of
    # players to originally crawl.
    search_players = []
    for k in r.json():
        search_players.append(r.json()[k]['id'])

    print("Now attempting to crawl players with breadth of " + str(BREADTH) + " and depth of " + str(DEPTH) + "...")

    # creates the original call stack to crawl players
    for player in search_players:
        crawl_player(player, DEPTH, BREADTH)

    print("Finished crawling database.")

if __name__ == '__main__':
     crawl_database()
