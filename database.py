from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

engine = create_engine('sqlite:///database/history.db', convert_unicode=True)
db_session = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()
Base.query = db_session.query_property()

# this is used to initialize the database when tables have been cleared or to initialize
# a clean database during restarts
def init_db():
    # this needs to be optimized and made more user friendly. this does not always
    # create a new database and maybe creating the file itself would be a good option
    import models
    Base.metadata.create_all(bind=engine)

# todo: implement this. make a clean tables for the player data!
def clean_db():
    import models
    # can only do this in interpreter?
    # db_session.query(models.BannedChampion).delete()
    # db_session.commit()
    # db_session.query(models.BuiltItems).delete()
    # db_session.commit()
    # db_session.query(models.Champion).delete()
    # db_session.commit()
    # db_session.query(models.Match).delete()
    # db_session.commit()

# def create_db():
#     db_session.commit()
#     init_db()
