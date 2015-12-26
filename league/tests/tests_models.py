from league import app
from league import db

from league.models import Champion
from league.models import ChampionData


class TestChampion(object):
    # TODO(Abstract out the setup and teardown.)
    def setup(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()

        db.create_all()
        self.db = db

    def teardown(self):
        self.db.session.remove()

    def test_create(self):
        champ = Champion(
            role="TOP",
        )

        self.db.session.add(champ)
        self.db.session.flush()

        assert champ.id == 1

    def test_get_kda(self):
        champ = Champion(
            kills=2,
            deaths=1,
            assists=0
        )

        assert champ.get_kda() == 2

        champ = Champion(
            kills=2,
            deaths=0,
            assists=2
        )

        assert champ.get_kda() == 4


class TestChampionData(object):
    def setup(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()

        db.create_all()
        self.db = db

    def teardown(self):
        self.db.session.remove()

    def test_get_name(self):
        champ = ChampionData(
            champion_name="cats"
        )

        assert champ.get_name() == "cats"

    def test_get_kda(self):
        champ = ChampionData(
            kills=1,
            deaths=0,
            assists=0
        )

        assert champ.get_kda() == 1

    def test_get_score(self):
        champ = ChampionData(
            kills=1,
            deaths=0,
            assists=0,
            role="TOP",
            num_seen=0,
            won=1,
            tower_score=1,
            objective_score=1,
            pick_rate=1,
            adjustment=1,
            champion_name="Annie",
            score=49
        )

        self.db.session.add(champ)
        self.db.session.commit()

        assert champ.get_score(False) == 49
