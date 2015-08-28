import datetime
import math

from colorama import Fore
import requests
import sqlalchemy

from models import Match, Champion, BannedChampion, BuiltItems, ChampionData
from database import db_session
from settings import API_KEY, URLS

def analyze_db():
    print("Analyzing database...")
    
    match_num = get_match_count()
    print(str(match_num) + " matches found in the database.")

    response = db_session.execute("""
        SELECT champion_id, role,
            SUM(kills) / COUNT(*),
            SUM(deaths) / COUNT(*),
            SUM(assists) / COUNT(*),
            SUM(damage) / COUNT(*),
            SUM(objective_score) / COUNT(*),
            SUM(tower_score) / COUNT(*),
            SUM(won) / COUNT(*),
            COUNT(*) / {match_num},
            COUNT(*)
            FROM champion GROUP BY champion_id, role
            """.format(match_num = str(match_num)))

    for row in response:
        # [0]: champion_id, [1]: role, [2]: kills, [3]: deaths, [4]: assists, [5]: damage, [6]: obj_score, [7]: tower_score [8]: won
        # [9]: pick rate, [10]: seen
        print("Analyzing champion: " + str(row[0]) + ".")
        print("Got data: " + str(row) + ".")

        found = ChampionData.query.filter(ChampionData.champion_id == row[0], ChampionData.role == row[1]).first()

        if found == None:
            print("Did not find " + str(row[0]) + ".")

            champion = ChampionData(champion_id = row[0], role = row[1], kills = row[2], deaths = row[3], assists = row[4],
                damage = row[5], objective_score = row[6], tower_score = row[7], won = row[8], pick_rate = row[9],
                num_seen = row[10], adjustment = 0)
            db_session.add(champion)
        else:
            print("Found " + str(row[0]) + ". Updating data....")

            found.kills = row[2]
            found.deaths = row[3]
            found.assists = row[4]
            found.damage = row[5]
            found.objective_score = row[6]
            found.tower_score = row[7]
            found.won = row[8]
            found.pick_rate = row[9]
            found.seen = row[10]

        db_session.commit()
    db_session.commit()

def get_match_count():
    print("Getting match count...")

    response = db_session.execute("SELECT COUNT(*) from `match`")

    for row in response:
        return row[0]

if __name__ == '__main__':
    analyze_db()
