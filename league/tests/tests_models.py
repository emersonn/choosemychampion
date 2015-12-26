# from nose.tools import set_trace
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from league.models import Champion
from league.models import ChampionData

# TODO(Abstract out the setup and teardown.)


class TestChampion(object):
    def setup(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
        )

        self.db_session = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        )

        from league.models import Base
        Base.metadata.create_all(bind=self.engine)

    def teardown(self):
        self.db_session.remove()

    def test_create(self):
        champ = Champion(
            role="TOP",
        )

        self.db_session.add(champ)
        self.db_session.flush()

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
        self.engine = create_engine(
            "sqlite:///:memory:",
        )

        self.db_session = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        )

        from league.models import Base
        Base.metadata.create_all(bind=self.engine)

    def teardown(self):
        self.db_session.remove()

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

        self.db_session.add(champ)
        self.db_session.commit()

        assert champ.get_score(False) == 49
