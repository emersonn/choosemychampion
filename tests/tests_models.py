# from nose.tools import set_trace
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from models import Champion
from models import ChampionData

# TODO(Abstract out the setup and teardown.)


class TestChampion(object):
    def setup(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
        )

        self.db_session = scoped_session(
            sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        )

        from models import Base
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

        from models import Base
        Base.metadata.create_all(bind=self.engine)

    def teardown(self):
        self.db_session.remove()

    def test_get_name(self):
        # TODO(Test if the name does exist, it just returns it
        #       and nothing else happens)
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
