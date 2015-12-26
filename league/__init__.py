from flask import Flask

from flask_sqlalchemy import SQLAlchemy

from league import settings

app = Flask(__name__)

# TODO(Modify this to put into an app_settings.py)
app.config['SQLALCHEMY_DATABASE_URI'] = settings.DATABASE
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['DEBUG'] = settings.DEBUG
app.config['SECRET_KEY'] = settings.SECRET_KEY

# app.config.from_object('league.app_settings')

db = SQLAlchemy(app)

from league import models  # NOQA
from league import views  # NOQA
