# Champion Score Analysis
# Emerson Matson

# Analyzes each champions score

from models import ChampionData
from prettylog import PrettyLog

LOGGING = PrettyLog()


def make_adjustments():
    """Takes all champion data and creates a score."""

    champions = ChampionData.query.all()

    # TODO(Look at external sources for better analysis.)
    #   Look at pro players? Look at nerfplz.com and analyze their
    #       algorithm for assigning tier lists. Look at popularity on twitter?

    for champion in champions:
        # True forces the methods to force updates
        champion.get_score(True)
        champion.get_counters(True)
        champion.get_assists(True)

        # TODO(Use adjustments attribute to assign miscellaneous overall stats)
        #   ChampionDatas as verticies. Directed edges against champions to
        #       depict wins against that champion. Champion w/ highest out
        #       degree is the most likely to win in the meta.
        #   Can start storing specified MMR for games and create a single
        #       source shortest path to a desired MMR.
        #   Adjust all champions scores to model a normal distribution.
        #       Adjustment scores are used for this.


def approximate_normal():
    """Approximate the normal distribution with champion scores."""
    pass

if __name__ == "__main__":
    LOGGING.push("Starting adjustments.")
    make_adjustments()
    LOGGING.push("Adjustments have been completed.")

    LOGGING.push("Now starting to approximate normal.")
    approximate_normal()
    LOGGING.push("Finished approximating normal.")
