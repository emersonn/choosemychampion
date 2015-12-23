# Champion Score Analysis
# Emerson Matson

# Analyzes each champions score

from models import ChampionData
from prettylog import PrettyLog

LOGGING = PrettyLog()


def make_adjustments():
    """Takes all champion data and creates a score."""

    champions = ChampionData.query.all()

    # TODO(look at pro players? look at nerfplz.com and analyze their
    # algorithm for assigning tier lists. look at popularity on twitter?)

    for champion in champions:
        # True forces the methods to force updates
        champion.get_score(True)
        champion.get_counters(True)
        champion.get_assists(True)

if __name__ == "__main__":
    LOGGING.push("Starting adjustments.")
    make_adjustments()
    LOGGING.push("Adjustments have been completed.")
