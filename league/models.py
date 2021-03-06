from sqlalchemy import func

from sqlalchemy.ext.associationproxy import association_proxy

from prettylog import PrettyLog

from leaguepy import RiotSession

from league import db

from settings import API_KEY

LOGGING = PrettyLog()
SESSION = RiotSession(API_KEY)


def get_kda(data):
    """Gives the KDA of a particular object.

    Args:
        data: Class with the attributes kills, assists, and deaths.
    """

    overall = float(data.kills + data.assists)
    if data.deaths == 0:
        return overall
    else:
        return overall / (data.deaths)


class Match(db.Model):
    """Used to store basic information about the match."""

    __tablename__ = 'match'

    id = db.Column(db.Integer, primary_key=True)

    match_id = db.Column(db.BigInteger)

    match_time = db.Column(db.DateTime)
    match_duration = db.Column(db.Integer)

    """
    def __repr__(self):
        return '<Match %r>' % (self.match_id)
    """


class Champion(db.Model):
    """Stores information about the player's champion in a particular game."""

    __tablename__ = 'champion'

    id = db.Column(db.Integer, primary_key=True)

    # TODO(Maybe make a Champion reference instead?)
    champion_id = db.Column(db.Integer)
    player_id = db.Column(db.Integer)

    team_id = db.Column(db.Integer)
    won = db.Column(db.Boolean)

    role = db.Column(db.String(30), nullable=False)
    kills = db.Column(db.Integer)
    deaths = db.Column(db.Integer)
    assists = db.Column(db.Integer)
    damage = db.Column(db.Integer)

    # NOTE: Objective_score is the addition of dragon and baron kills
    objective_score = db.Column(db.Integer)
    tower_score = db.Column(db.Integer)

    match_id = db.Column(db.Integer, db.ForeignKey("match.id"))
    match = db.relationship(
        "Match",
        backref=db.backref("champion", order_by=id)
    )

    """
    def __repr__(self):
        return '<Champion %r>' % (self.champion_id)
    """

    def get_kda(self):
        return get_kda(self)


class BannedChampion(db.Model):
    """Basic information about a banned champion in a particular match."""

    __tablename__ = 'banned_champion'

    id = db.Column(db.Integer, primary_key=True)
    champion_id = db.Column(db.Integer)

    match_id = db.Column(db.Integer, db.ForeignKey("match.id"))
    match = db.relationship(
        "Match",
        backref=db.backref("banned_champion", order_by=id)
    )

    """
    def __repr__(self):
        return '<Banned Champion %r>' % (self.champion_id)
    """


class BuiltItems(db.Model):
    """Stores basic information about built items for a particular player."""

    __tablename__ = 'built_items'

    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer)

    champion_id = db.Column(db.Integer, db.ForeignKey("champion.id"))
    champion = db.relationship(
        "Champion", backref=db.backref("built_items", order_by=id)
    )

    """
    def __repr__(self):
        return '<Item %r>' % (self.item_id)
    """


class PlayerData(db.Model):
    """Stores summary data for a particular champion a player played."""

    __tablename__ = 'player_data'

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer)
    player_name = db.Column(db.String(40))
    location = db.Column(db.String(12))

    champion_id = db.Column(db.Integer)
    champion_name = db.Column(db.String(30))

    role = db.Column(db.String(30))

    updated = db.Column(db.DateTime)
    sessions_played = db.Column(db.Integer)

    kills = db.Column(db.Integer)
    deaths = db.Column(db.Integer)
    assists = db.Column(db.Integer)

    won = db.Column(db.Integer)

    adjustment = db.Column(db.Float)

    def get_name(self):
        """Gets the name of the champion in question.

        Returns:
            db.String: The champion name. (capitalized)
        """

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

                try:
                    self.champion_name = (
                        SESSION.get_champion(self.champion_id)['name']
                    )
                    db.session.commit()

                # DEPRICATED: if the player data had been
                #             stored with the summary data
                #             the champion is given as a "summary."
                except ValueError:
                    return "summary"
            else:
                self.champion_name = query.champion_name
                db.session.commit()
        return self.champion_name

    def get_kda(self):
        return get_kda(self)

    # TODO(Fix this. Needs to be more in depth. Temporary solution to adjust.
    #       Played champions are more favored.
    #       Needs to be balanced.
    #       Also figure out champions that do not fit into the role,
    #       not many picks.)

    def get_adjustment(self, force_update=False):
        """Calculates the adjustment for a particular player in the database.

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
            else:
                LOGGING.push(
                    "Forced update for *'" + self.player_name +
                    "'* on champion @'" + str(self.champion_id) + "'@."
                )

            adjustment = 0.0

            import statistics

            from scipy import stats

            player_champions = (
                PlayerData.query
                .filter_by(
                    player_name=self.player_name,
                    location=self.location
                )
                .all()
            )

            # TODO(Temporary fix to the zero division error,
            #       fix to MySQL returning db.Integers.
            #       MySQL gives db.Integers for this and getScore()
            #       negative numbers?)

            champions_seen = [
                data.sessions_played for data in player_champions
            ]
            try:
                zscore = (
                    (self.sessions_played - statistics.mean(champions_seen)) /
                    (statistics.stdev(champions_seen))
                )
                percentile = stats.norm.sf(zscore)
            except (ZeroDivisionError, statistics.StatisticsError) as e:
                LOGGING.push("Got error: #'" + e + "'# in compiling seen.")
                percentile = 1

            # TODO(Temporary fix to zero division error.)
            try:
                adjustment += (
                    (self.won * 1.0 / (self.sessions_played)) * 15 *
                    (1 - percentile)
                )
            except ZeroDivisionError:
                percentile = 0

            # TODO(Temporary fix to zero division error.)
            champions_kda = [data.get_kda() for data in player_champions]
            try:
                kda_zscore = (
                    self.get_kda() - statistics.mean(champions_kda) /
                    (statistics.stdev(champions_kda))
                )
                kda_percentile = stats.norm.sf(kda_zscore)
            except (ZeroDivisionError, statistics.StatisticsError) as e:
                LOGGING.push("Got error: #'" + e + "'# in compiling kda.")
                kda_percentile = 1

            adjustment += 15 * (1 - kda_percentile) * (1 - percentile)

            # TODO(Temporary fix to zero division error)
            try:
                adjustment += (
                    .49 * self.sessions_played /
                    (statistics.mean(champions_seen)) +
                    3.9 * self.sessions_played /
                    100
                )
            except ZeroDivisionError as e:
                LOGGING.push("Got error: #'" + e + "'# in compiling sessions.")

            self.adjustment = adjustment
            db.session.commit()

        return self.adjustment

    # TODO(Implement this. make this into a paragraph and graphs
    #       that discuss how the player is at this
    #       champion compared to other people.
    #       show distributions and highlight where they are.
    #       such as tower scores or kda and such.)
    def player_analysis(self):
        pass


class ChampionData(db.Model):
    """Stores analyzed champion data.

    NOTE: All data is stored as averaged data.
    """

    __tablename__ = 'champion_data'

    id = db.Column(db.Integer, primary_key=True)
    champion_id = db.Column(db.Integer)
    champion_name = db.Column(db.String(40))
    role = db.Column(db.String(30), nullable=False)

    won = db.Column(db.Float)
    num_seen = db.Column(db.Integer)

    kills = db.Column(db.Float)
    deaths = db.Column(db.Float)
    assists = db.Column(db.Float)

    damage = db.Column(db.Float)
    objective_score = db.Column(db.Float)
    tower_score = db.Column(db.Float)

    pick_rate = db.Column(db.Float)

    adjustment = db.Column(db.Float)
    score = db.Column(db.Float)

    image = db.Column(db.String(100))

    counters = association_proxy('champion_counters', 'counter')
    assisters = association_proxy('champion_assists', 'assist')

    def get_kda(self):
        return get_kda(self)

    # TODO(Combine this with PlayerData, but also use the database
    #       there are already records of a particular champion
    #       so there's not need to try to search for the name again.)
    def get_name(self):
        """Finds the name in the database, otherwise requests it.

        Returns:
            db.String: Champion name.
        """

        if self.champion_name is None:
            LOGGING.push(
                "Did not find a champion name at all. Requesting name."
            )

            self.champion_name = (
                SESSION.get_champion(self.champion_id)['name']
            )
            db.session.commit()

        return self.champion_name

    def get_score(self, force_update):
        """Gets the score of the particular champion.

        Args:
            force_update: Whether the current score should be force updated.

        Returns:
            db.Float: Score of the champion. Attempted to normalize around 100.
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
            champion_stats = {
                'champions_seen': [],
                'champions_kda': [],
                'champions_objectives': []
            }

            for champion in ChampionData.query.all():
                champion_stats['champions_seen'].append(champion.num_seen)
                champion_stats['champions_kda'].append(champion.get_kda())
                champion_stats['champions_objectives'].append(
                    champion.objective_score + champion.tower_score
                )

            from scipy import stats
            import statistics

            # Percentile of num seen
            champions_seen = champion_stats['champions_seen']
            zscore = (
                (self.num_seen - statistics.mean(champions_seen)) /
                statistics.stdev(champions_seen)
            )
            percentile = stats.norm.sf(zscore)

            # Adjusts score with respect to won and num seen percentile
            calculated_score += self.won * 45 * (1 - percentile)

            # Percentile of kda
            champions_kda = champion_stats['champions_kda']
            kda_zscore = (
                (
                    self.get_kda() - statistics.mean(champions_kda) /
                    statistics.stdev(champions_kda)
                )
            )
            kda_percentile = stats.norm.sf(kda_zscore)
            calculated_score += 30 * (1 - kda_percentile) * (1 - percentile)

            # Percentile of objective score
            champions_objectives = champion_stats['champions_objectives']
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

            # TODO(Depricate this for a more statistical approach.
            # bottom or middle roles are more likely to win so a higher score)
            if self.role == "BOTTOM" or self.role == "MIDDLE":
                calculated_score *= 1.04

            calculated_score += self.adjustment

            self.score = calculated_score
            db.session.commit()

        return self.score

    def get_image(self):
        if self.image is None:
            self.image = SESSION.get_champion(
                champion_id=self.champion_id,
                champ_data="image"
            )['image']['full']
            db.session.commit()

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

    # TODO(Role, archetype of champion)

    def get_calculated_win(self, player_id, location):
        """Calculates the percepted win for a player/champion combination.

        Returns:
            db.Float: Calculated win rate.
        """

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

        player = (
            db.session.query(PlayerData)
            .filter_by(player_id=player_id, location=location)
        )
        """

        return self.won

    # TODO(Implement updating of old counters
    #       (or self.champion_counters[0].updated)
    #       also find a way to combine counters and assists)

    def get_counters(self, force_update=False):
        counters = self.counters
        if counters == [] or force_update:
            LOGGING.push(
                "*'" + self.get_name() +
                "'* has been called for a force update, " +
                "or there are no counters existing at the moment."
            )

            Counter.query.filter(Counter.original == self).delete()
            db.session.commit()

            champions = (
                db.session.query(
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
                db.session.add(new_counter)
            db.session.commit()

        return counters

    # TODO(Kind of weird abstraction...)
    def get_compiled_weights(self, process):
        compiled = {}

        for champion in getattr(self, "get_" + process)():
            # TODO(Abstract this out more)
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
            db.session.commit()

            champions = (
                db.session.query(
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
                    db.session.add(new_assist)
            db.session.commit()

        return assists


class Counter(db.Model):
    __tablename__ = 'counter_champions'

    original_id = db.Column(
        db.Integer, db.ForeignKey('champion_data.id'), primary_key=True
    )
    counter_id = db.Column(
        db.Integer, db.ForeignKey('champion_data.id'), primary_key=True
    )

    weight = db.Column(db.Integer)
    updated = db.Column(db.DateTime, default=func.now())

    original = db.relationship(
        ChampionData,
        backref=db.backref("champion_counters"),
        foreign_keys=[original_id]
    )
    counter = db.relationship(
        ChampionData,
        backref=db.backref("countered"),
        foreign_keys=[counter_id]
    )


class Assist(db.Model):
    __tablename__ = 'assist_champions'

    original_id = db.Column(
        db.Integer, db.ForeignKey('champion_data.id'), primary_key=True
    )
    assist_id = db.Column(
        db.Integer, db.ForeignKey('champion_data.id'), primary_key=True
    )

    weight = db.Column(db.Integer)
    updated = db.Column(db.DateTime, default=func.now())

    original = db.relationship(
        ChampionData,
        backref=db.backref("champion_assists"),
        foreign_keys=[original_id]
    )
    assist = db.relationship(
        ChampionData,
        backref=db.backref("assisted"),
        foreign_keys=[assist_id]
    )
