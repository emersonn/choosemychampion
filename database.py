from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from settings import DATABASE

engine = create_engine(DATABASE, convert_unicode=True)
db_session = scoped_session(
    sessionmaker(autocommit=False, autoflush=False, bind=engine)
)

Base = declarative_base()
Base.query = db_session.query_property()

# DEPRICATED: Alembic is used now.


def init_db():
    """ Initializes the database.
    """

    import models
    Base.metadata.create_all(bind=engine)

# TODO: implement this. may need to use to clean player data.


def clean_db():
    pass
