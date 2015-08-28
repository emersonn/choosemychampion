import datetime
import math

from colorama import Fore
import requests
from sqlalchemy import func, Integer
import sqlalchemy

from models import Match, Champion, BannedChampion, BuiltItems, ChampionData
from database import db_session
from settings import API_KEY, URLS

# TODO: optimize this query for large databases.
#       window the query. http://stackoverflow.com/questions/7389759/memory-efficient-built-in-sqlalchemy-iterator-generator
#       filter the query to the most recent matches (30 days)
#       limit the query to a good amount ~10 mill?
#       prune the database every so often
def analyze():
    print("Using new script...")

    match_num = get_match_count()

    # Multiple ways to go about this
    #   Group by champion/role and find distinct rows and then filter to aggragate
    #   Aggragate right away with a .query() with func.sum, func.count
    #   Filter then aggragate (order by date, limit by a large number)

    # champion_id, role, kills, deaths, assists, damage, objective_score, tower_score, won
    # pick_rate, num_seen, adjustment = 0

    # avg function

    champions = (db_session.query(
                        Champion.champion_id.label("champion_id"),
                        Champion.role.label("role"),
                        func.avg(Champion.kills).label("kills"),
                        func.avg(Champion.deaths).label("deaths"),
                        func.avg(Champion.assists).label("assists"),
                        func.avg(Champion.damage).label("damage"),
                        func.avg(Champion.objective_score).label("objective_score"),
                        func.avg(Champion.tower_score).label("tower_score"),
                        func.avg(Champion.won, type_=Integer).label("won"),
                        func.count(Champion.champion_id).label("seen")
                    ).group_by(Champion.champion_id, Champion.role)
                    .all())

    for champion in champions:
        print("Analyzing champion: " + str(champion.champion_id) + ", with role: " + champion.role + ".")
        # print("Got data " + str(champion) + ".")

        found = db_session.query(ChampionData).filter(ChampionData.champion_id == champion.champion_id,
            ChampionData.role == champion.role).first()

        if found is None:
            print("Did not find " + str(champion.champion_id) + ". Creating row...")

            new_champion = ChampionData(champion_id = champion.champion_id, role = champion.role,
                kills = champion.kills, deaths = champion.deaths, assists = champion.assists,
                damage = champion.damage, objective_score = champion.objective_score, tower_score = champion.tower_score,
                won = champion.won, pick_rate = (champion.seen / float(match_num)), num_seen = champion.seen,
                adjustment = 0)
            db_session.add(new_champion)

        else:
            print("Found " + str(champion.champion_id) + ". Updating data...")

            found.kills = champion.kills
            found.deaths = champion.deaths
            found.assists = champion.assists
            found.damage = champion.damage
            found.objective_score = champion.objective_score
            found.tower_score = champion.tower_score
            found.won = champion.won
            found.pick_rate = (champion.seen / float(match_num))
            found.num_seen = champion.seen

            db_session.add(found)
        db_session.commit()
    db_session.commit()

def get_match_count():
    print("Getting match count...")
    return db_session.query(Match).count()
    print(str(match_num) + " matches found in the database.")

if __name__ == '__main__':
    print("Analyzing database...")
    analyze()
