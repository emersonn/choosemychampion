"""
Data analysis script
Emerson Matson

Moves the large data set into a more compact, workable dataset for analysis.
"""

from sqlalchemy import func, Integer

from league import db

from league.models import Champion
from league.models import ChampionData
from league.models import Match

from prettylog import PrettyLog

LOGGING = PrettyLog()

"""
TODO(Optimize this query for large databases.)
    Window the query.
        http://stackoverflow.com/
            questions/7389759/
            memory-efficient-built-in-sqlalchemy-iterator-generator
    Filter the query to the most recent matches (30 days?)
    Limit the query to a good amount (10 million?)
    Prune the database every so often.
"""


def analyze():
    """Analyzes the champion database and condenses the statistics."""

    match_num = get_match_count()

    """
    NOTE: Multiple ways to go about this
        Group by champion/role and find distinct rows and then filter/aggragate
        Aggragate right away with a .query() with func.sum, func.count
        Filter then aggragate (order by date, limit by a large number)
    """

    champions = (db.session.query(
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
            db.session.query(ChampionData)
            .filter(
                ChampionData.champion_id == champion.champion_id,
                ChampionData.role == champion.role
            )
            .first()
        )

        # TODO(Can simplify this by combining both branches by creating an
        #   empty champion otherwise and filling all of this info for 'found.')

        # TODO(Can be is not found.)
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
            db.session.add(new_champion)

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

            db.session.add(found)
        db.session.commit()
    db.session.commit()


def get_match_count():
    LOGGING.push("Getting match count.")
    match_num = db.session.query(Match).count()
    LOGGING.push("*'" + str(match_num) + "'* matches found in the database.")

    return match_num

if __name__ == '__main__':
    LOGGING.push("Analyzing database.")
    analyze()
    LOGGING.push("Database has been analyzed.")
