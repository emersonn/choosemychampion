# Data analysis script
# Emerson Matson

# Used for moving the database into a more accessible size for analysis and
# data presentation

from sqlalchemy import func, Integer

from models import Match, Champion, ChampionData
from database import db_session
from prettylog import PrettyLog

LOGGING = PrettyLog()

# TODO: optimize this query for large databases. window the query.
#       http://stackoverflow.com/questions/7389759/memory-efficient-built-in-sqlalchemy-iterator-generator
#       filter the query to the most recent matches (30 days)
#       limit the query to a good amount ~10 mill?
#       prune the database every so often


def analyze():
    """ Analyzes the champion database and condenses the statistics for easy
    retrieval.
    """

    match_num = get_match_count()

    """
    NOTE: Multiple ways to go about this
        Group by champion/role and find distinct rows and then filter/aggragate
        Aggragate right away with a .query() with func.sum, func.count
        Filter then aggragate (order by date, limit by a large number)
    """
    champions = (db_session.query(
        Champion.champion_id.label("champion_id"),
        Champion.role.label("role"),
        func.avg(Champion.kills).label("kills"),
        func.avg(Champion.deaths).label("deaths"),
        func.avg(Champion.assists).label("assists"),
        func.avg(Champion.damage).label("damage"),
        (func.avg(Champion.objective_score)
            .label("objective_score")),
        func.avg(Champion.tower_score).label("tower_score"),
        func.avg(Champion.won, type_=Integer).label("won"),
        func.count(Champion.champion_id).label("seen"))
        .group_by(Champion.champion_id, Champion.role)
        .all())

    for champion in champions:
        LOGGING.push(
            "Analyzing champion *'" + str(champion.champion_id) +
            "'* with role @'" + champion.role + "'@."
        )

        found = (
            db_session.query(ChampionData)
            .filter(
                ChampionData.champion_id == champion.champion_id,
                ChampionData.role == champion.role
            )
            .first()
        )

        if found is None:
            LOGGING.push(
                "Did not find *'" + str(champion.champion_id) +
                "'*. Creating row."
            )

            new_champion = ChampionData(
                champion_id=champion.champion_id,
                role=champion.role,
                kills=champion.kills,
                deaths=champion.deaths,
                assists=champion.assists,
                damage=champion.damage,
                objective_score=champion.objective_score,
                tower_score=champion.tower_score,
                won=champion.won,
                pick_rate=(champion.seen / float(match_num)),
                num_seen = champion.seen,
                adjustment = 0
            )
            db_session.add(new_champion)

        else:
            LOGGING.push(
                "Found *'" + str(found.get_name()) + "'*. Updating data."
            )

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
    LOGGING.push("Getting match count.")
    match_num = db_session.query(Match).count()
    LOGGING.push("*'" + str(match_num) + "'* matches found in the database.")

    return match_num

if __name__ == '__main__':
    LOGGING.push("Analyzing database.")
    analyze()
    LOGGING.push("Database has been analyzed.")
