# Champion Score Analysis
# Emerson Matson

# Analyzes each champions score

import requests

from models import ChampionData

# takes all the champion data and creates a score
def make_adjustments():
    champions = ChampionData.query.all()

    # TODO: look at pro players? look at nerfplz.com and analyze their
    # algorithim for assigning tier lists. look at popularity on twitter?

    for champion in champions:
        # true is important as it forces an update of the champion data
        # file with respect to the score
        champion.get_score(True)

if __name__ == "__main__":
    make_adjustments()
