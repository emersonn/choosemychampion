from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy import ForeignKey, Float, func
from sqlalchemy.orm import relationship, backref

from sqlalchemy.ext.associationproxy import association_proxy

from database import Base, db_session
from prettylog import PrettyLog
from riot import RiotSession
from settings import API_KEY, URLS

LOGGING = PrettyLog()
SESSION = RiotSession(API_KEY)


class Match(Base):
    """ Used to store basic information about the match.
    """

    __tablename__ = 'match'

    id = Column(Integer, primary_key=True)

    match_id = Column(Integer)
    match_time = Column(DateTime)
    match_duration = Column(Integer)

    def __repr__(self):
        return '<Match %r>' % (self.match_id)


class Champion(Base):
    """ Stores information about the player who played this champion in a game.
    """

    __tablename__ = 'champion'

    id = Column(Integer, primary_key=True)

    champion_id = Column(Integer)
    player_id = Column(Integer)

    team_id = Column(Integer)
    won = Column(Boolean)

    role = Column(String(30), nullable=False)
    kills = Column(Integer)
    deaths = Column(Integer)
    assists = Column(Integer)
    damage = Column(Integer)

    # objective_score is scored as the addition of
    # baron kills and dragon kills
    objective_score = Column(Integer)
    tower_score = Column(Integer)

    # references the champion to a particular match
    match_id = Column(Integer, ForeignKey("match.id"))
    match = relationship("Match", backref=backref("champion", order_by=id))

    def __repr__(self):
        return '<Champion %r>' % (self.champion_id)

    def get_kda(self):
        if self.deaths == 0:
            return (1.0 * self.kills + self.assists)
        else:
            return (1.0 * self.kills + self.assists) / (self.deaths)


class BannedChampion(Base):
    """ Basic information about a banned champion in a particular match.
    """

    __tablename__ = 'banned_champion'

    id = Column(Integer, primary_key=True)
    champion_id = Column(Integer)

    match_id = Column(Integer, ForeignKey("match.id"))
    match = relationship(
        "Match", backref=backref("banned_champion", order_by=id)
    )

    def __repr__(self):
        return '<Banned Champion %r>' % (self.champion_id)


class BuiltItems(Base):
    """ Stores basic information about built items for a particular player.
    """

    __tablename__ = 'built_items'

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer)

    champion_id = Column(Integer, ForeignKey("champion.id"))
    champion = relationship(
        "Champion", backref=backref("built_items", order_by=id)
    )

    def __repr__(self):
        return '<Item %r>' % (self.item_id)


class PlayerData(Base):
    """ Stores summary data for a particular champion a player played.
    """

    __tablename__ = 'player_data'

    id = Column(Integer, primary_key=True)
    player_id = Column(Integer)
    player_name = Column(String(40))
    location = Column(String(12))

    champion_id = Column(Integer)
    champion_name = Column(String(30))

    role = Column(String(30))

    updated = Column(DateTime)
    sessions_played = Column(Integer)

    kills = Column(Integer)
    deaths = Column(Integer)
    assists = Column(Integer)

    won = Column(Integer)

    adjustment = Column(Float)

    def get_name(self):
        if self.champion_name is None:
            query = (
                ChampionData.query
                .filter_by(champion_id=self.champion_id)
                .first()
            )

            if query is None:
                LOGGING.push(
                    "Did not find a champion name at all. Requesting name."
                )

                import requests

                import database

                # TODO: use the RiotSession
                try:
                    r = requests.get(
                        URLS['champion'] + str(self.champion_id),
                        params={'api_key': API_KEY}
                    )
                    self.champion_name = r.json()['name']
                    database.db_session.commit()

                # OLD: if the player data had been stored with the summary data
                # the champion is given as a "summary."
                except ValueError:
                    return "summary"
            else:
                import database
                self.champion_name = query.champion_name
                database.db_session.commit()
        return self.champion_name

    # kda is calculated as the addition of kills and
    # assists divided by the number of deaths by that particular player.
    def get_kda(self):
        if self.deaths == 0:
            return (1.0 * self.kills + self.assists)
        else:
            return (1.0 * self.kills + self.assists) / (self.deaths)

    # todo: fix this. this needs to be more in depth. temporary solution to the
    # adjustment of a player. played champions are more favored.
    # needs to be balanced. also figure out champions that do not fit
    # into the role, not many picks.

    def get_adjustment(self, force_update=False):
        """ Calculates the adjustment for a particular player in the database.

        Args:
            force_update: Decides whether to force update the current
                adjustment in the database. Defaults to False.
        """

        if self.adjustment is None or force_update:
            if self.adjustment is None:
                LOGGING.push(
                    "Did not find adjustment for *'" +
                    self.player_name + "'* with @'" +
                    str(self.champion_id) + "'@."
                )
            elif force_update:
                LOGGING.push(
                    "Forced update for *'" + self.player_name +
                    "'* on champion @'" + str(self.champion_id) + "'@."
                )

            adjustment = 0.0

            import statistics
            from scipy import stats

            """
            adjustment += .4 * self.get_kda()
            adjustment += .2 * self.sessions_played
            adjustment += ((self.won * 1.0) / self.sessions_played) * 10
            """

            player_champions = (
                PlayerData.query
                .filter_by(player_name=self.player_name)
            )

            # todo: temporary fix to the zero division error, and fix to MySQL
            # returning integers. MYSQL GIVES INTEGERS FOR
            # THIS AND THE GET SCORE! FURTHERMORE SOMETIMES THERE ARE
            # HUGELY NEGATIVE NUMBERS BEING RETURNED FOR THIS!!!!
            champions_seen = [
                data.sessions_played for data in player_champions
            ]
            try:
                zscore = (
                    (self.sessions_played - statistics.mean(champions_seen)) /
                    (statistics.stdev(champions_seen))
                )
                percentile = stats.norm.sf(zscore)
            except ZeroDivisionError:
                percentile = 1
            except statistics.StatisticsError:
                percentile = 1

            # todo: temporary fix to zero division error
            try:
                adjustment += (
                    (self.won * 1.0 / (self.sessions_played)) * 15 *
                    (1 - percentile)
                )
            except ZeroDivisionError:
                percentile = 0

            # todo: temporary fix to zero division error
            champions_kda = [data.get_kda() for data in player_champions]
            try:
                kda_zscore = (
                    self.get_kda() - statistics.mean(champions_kda) /
                    (statistics.stdev(champions_kda))
                )
                kda_percentile = stats.norm.sf(kda_zscore)
            except ZeroDivisionError:
                kda_percentile = 1
            except statistics.StatisticsError:
                kda_percentile = 1

            adjustment += 15 * (1 - kda_percentile) * (1 - percentile)

            # todo: temporary fix to zero division error
            try:
                adjustment += (
                    .49 * self.sessions_played /
                    (statistics.mean(champions_seen)) +
                    3.9 * self.sessions_played /
                    100
                )
            except ZeroDivisionError:
                pass

            import database
            self.adjustment = adjustment
            database.db_session.commit()

        return self.adjustment

    # TODO: implement this. make this into a paragraph and graphs
    #       that discuss how the player is at this
    #       champion compared to other people.
    #       show distributions and highlight where they are.
    #       such as tower scores or kda and such.
    def player_analysis(self):
        pass


class ChampionData(Base):
    """ Stores analyzed champion data.

    NOTE: All data is stored as averaged data.
    """

    __tablename__ = 'champion_data'

    id = Column(Integer, primary_key=True)
    champion_id = Column(Integer)
    champion_name = Column(String(40))
    role = Column(String(30), nullable=False)

    won = Column(Float)
    num_seen = Column(Integer)

    kills = Column(Float)
    deaths = Column(Float)
    assists = Column(Float)

    damage = Column(Float)
    objective_score = Column(Float)
    tower_score = Column(Float)

    pick_rate = Column(Float)

    adjustment = Column(Float)
    score = Column(Float)

    image = Column(String(100))

    counters = association_proxy('champion_counters', 'counter')
    assisters = association_proxy('champion_assists', 'assist')

    # TODO: combine this kda and name with the PlayerData
    def get_kda(self):
        """ Calculates the KDA of a particular champion.

        Returns:
            float: KDA of the champion. Adds kills and assists.
        """

        if self.deaths == 0:
            return (1.0 * self.kills + self.assists)
        else:
            return (1.0 * self.kills + self.assists) / (self.deaths)

    # todo: not only combine this with PlayerData, but also use the database
    # there are already records of a particular champion
    # so there's not need to try to search for the name again.

    def get_name(self):
        """ Finds the name in the database, otherwise requests it.

        Returns:
            String: Champion name.
        """

        if self.champion_name is None:
            LOGGING.push(
                "Did not find a champion name at all. Requesting name."
            )
            import requests

            import database

            # TODO: Use RiotSession
            r = requests.get(
                URLS['champion'] + str(self.champion_id),
                params={'api_key': API_KEY}
            )

            self.champion_name = r.json()['name']
            database.db_session.commit()
        return self.champion_name

    def get_score(self, force_update):
        """ Gets the score of the particular champion.

        Args:
            force_update: Whether the score should be forced to update.

        Returns:
            float: Score of the champion. Attempted to normalize around 100.
        """

        if self.score is None or force_update:
            if self.score is None:
                LOGGING.push(
                    "Did not find score for *'" +
                    self.get_name() +
                    "'*. Generating score."
                )
            else:
                LOGGING.push(
                    "*'" +
                    self.get_name() +
                    "'* was called for a force update of score."
                )

            calculated_score = 0

            import statistics
            from scipy import stats

            # calculates the percentile of the won statistics
            champions_seen = [
                data.num_seen for data in ChampionData.query.all()
            ]
            zscore = (
                (self.num_seen - statistics.mean(champions_seen)) /
                statistics.stdev(champions_seen)
            )
            percentile = stats.norm.sf(zscore)

            calculated_score += self.won * 45 * (1 - percentile)

            # calculates the percentile of the kda
            champions_kda = [
                data.get_kda() for data in ChampionData.query.all()
            ]
            kda_zscore = (
                (
                    self.get_kda() - statistics.mean(champions_kda) /
                    statistics.stdev(champions_kda)
                )
            )
            kda_percentile = stats.norm.sf(kda_zscore)
            calculated_score += 30 * (1 - kda_percentile) * (1 - percentile)

            # calculates the percentile of the objective score
            champions_objectives = [
                data.objective_score +
                data.tower_score for data in ChampionData.query.all()
            ]
            objectives_zscore = (
                (
                    (self.objective_score + self.tower_score) -
                    statistics.mean(champions_objectives)
                ) /
                statistics.stdev(champions_objectives)
            )
            objectives_percentile = stats.norm.sf(objectives_zscore)
            calculated_score += (
                15 * (1 - objectives_percentile) * (1 - percentile)
            )

            calculated_score += 10 * self.pick_rate

            calculated_score *= 1.15

            # bottom or middle roles are more likely to win so a higher score
            if self.role == "BOTTOM" or self.role == "MIDDLE":
                calculated_score *= 1.04

            calculated_score += self.adjustment

            # pushes the score to the database
            import database
            self.score = calculated_score
            database.db_session.commit()

        return self.score

    def get_image(self):
        if self.image is None:
            import requests

            import database

            # TODO: use the RiotSession for this
            r = requests.get(
                URLS['champion'] + str(self.champion_id),
                params={'api_key': API_KEY, 'champData': 'image'}
            )

            # DEPRICATED: Unnecessary logging.
            # print("Dont have the image for " + self.champion_name + "...")
            self.image = r.json()['image']['full']
            database.db_session.commit()
        return self.image

    def get_full_image(self):
        return (
            "http://ddragon.leagueoflegends.com" +
            "/cdn/5.15.1/img/champion/{image}".format(image=self.get_image())
        )

    def get_url(self):
        return (
            "http://gameinfo.na.leagueoflegends.com" +
            "/en/game-info/champions/{uri}"
            .format(uri=self.get_image().split('.')[0].lower())
        )

    # TODO: role, archetype of champion

    # calculates the percepted win for a particular player with this champion.
    def get_calculated_win(self, player_id, location):
        """
        wins = 0.0
        seen = 0.0
        multiplier = 1.18

        player = PlayerData.query.filter_by(
            player_id = user_id, location = location
        )

        for champion in player:
            wins += champion.won
            seen += champion.sessions_played
            # TODO: make this more efficient
            # multiplier += champion.get_adjustment() / 140

        if self.role == "MIDDLE" or self.role == "BOTTOM":
            multiplier = 1.18

        return (
            self.get_score(False) + self.get_kda() +
            self.objective_score + self.tower_score) *
            min(multiplier * (wins * 1.15 / seen), 1.0)
        )
        """

        """
        player = (
            db_session.query(PlayerData)
            .filter_by(player_id=player_id, location=location)
        )
        """

        return self.won

    def get_counters(self, force_update=False):
        # TODO: implement updating of old counters
        #       (or self.champion_counters[0].updated)
        counters = self.counters
        if counters == [] or force_update:
            LOGGING.push(
                "*'" + self.get_name() +
                "'* has been called for a force update, " +
                "or there are no counters existing at the moment."
            )

            Counter.query.filter(Counter.original == self).delete()
            db_session.commit()

            champions = (
                db_session.query(
                    Champion,
                    func.count(Champion.champion_id).label("num_seen")
                )
                .group_by(Champion.champion_id)
                .filter_by(won=True, role=self.role)  # counter champion
                .join(Match)
                .filter(Match.champion.any(
                    champion_id=self.champion_id, role=self.role, won=False
                ))  # self
                .all()
            )

            for champion in champions:
                champion_data = (
                    ChampionData.query
                    .filter_by(
                        champion_id=champion[0].champion_id,
                        role=champion[0].role
                    )
                    .first()
                )
                new_counter = Counter(
                    original=self,
                    counter=champion_data,
                    weight=champion.num_seen
                )
                db_session.add(new_counter)
            db_session.commit()

        return counters

    # TODO: kind of weird abstraction...
    def get_compiled_weights(self, process):
        compiled = {}

        for champion in getattr(self, "get_" + process)():
            # TODO: Abstract this out more
            if process == "counters":
                current_counter = Counter.query.filter_by(
                    original=self, **{process[:-1]: champion}
                ).first()
            else:  # elif process == "assists":
                current_counter = Assist.query.filter_by(
                    original=self, **{process[:-1]: champion}
                ).first()
            compiled[champion] = current_counter.weight

        return compiled

    def get_assists(self, force_update=False):
        assists = self.assisters
        if assists == [] or force_update:
            LOGGING.push(
                "*'" + self.get_name() +
                "'* has been called for a force update or assisters " +
                "do not exist."
            )

            Assist.query.filter(Assist.original == self).delete()
            db_session.commit()

            champions = (
                db_session.query(
                    Champion,
                    func.count(Champion.champion_id).label("num_seen")
                )
                .group_by(Champion.champion_id)
                .filter_by(won=True)
                .join(Match)
                .filter(Match.champion.any(
                    champion_id=self.champion_id, role=self.role, won=True
                ))
                .all()
            )

            for champion in champions:
                champion_data = ChampionData.query.filter_by(
                    champion_id=champion[0].champion_id,
                    role=champion[0].role
                ).first()
                if champion_data is not self:
                    new_assist = Assist(
                        original=self,
                        assist=champion_data,
                        weight=champion.num_seen
                    )
                    db_session.add(new_assist)
            db_session.commit()

        return assists

    # TODO: depricated. will delete soon.

    """
    def process_champion_query(self, champion, condition):
        matches = [champ.match for champ in champion]
        champions = []
        for match in matches:
            champions.extend(match.champion)

        teams = {}

        for champion in champions:
            if condition(champion):
                try:
                    teams[champion.champion_id] = (
                        teams[champion.champion_id] + 1
                    )
                except KeyError:
                    teams[champion.champion_id] = 1

        compiled = {}

        for champion in teams.keys():
            champ = (
                db_session.query(ChampionData)
                .filter_by(champion_id = champion, role = self.role)
                .first())
            # TODO: fixes error where a champion may show up as None?
            #       some champion is not created as a ChampionData yet?
            if champ is not None:
                compiled[champ] = teams[champion]

        return compiled
    """


class Counter(Base):
    __tablename__ = 'counter_champions'

    original_id = Column(
        Integer, ForeignKey('champion_data.id'), primary_key=True
    )
    counter_id = Column(
        Integer, ForeignKey('champion_data.id'), primary_key=True
    )

    weight = Column(Integer)
    updated = Column(DateTime, default=func.now())

    original = relationship(
        ChampionData,
        backref=backref("champion_counters"),
        foreign_keys=[original_id]
    )
    counter = relationship(
        ChampionData,
        backref=backref("countered"),
        foreign_keys=[counter_id]
    )


class Assist(Base):
    __tablename__ = 'assist_champions'

    original_id = Column(
        Integer, ForeignKey('champion_data.id'), primary_key=True
    )
    assist_id = Column(
        Integer, ForeignKey('champion_data.id'), primary_key=True
    )

    weight = Column(Integer)
    updated = Column(DateTime, default=func.now())

    original = relationship(
        ChampionData,
        backref=backref("champion_assists"),
        foreign_keys=[original_id]
    )
    assist = relationship(
        ChampionData,
        backref=backref("assisted"),
        foreign_keys=[assist_id]
    )
