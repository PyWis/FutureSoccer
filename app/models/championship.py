"""Public monthly championship: division pyramid, groups, standings, matches.

One ChampionshipSeason exists per competition game-month (Sep–Jun). Each season
holds groups of 6 teams across the tiers (elite|gold|silver|bronze|iron); bot
teams fill any empty slot so every group is always exactly 6.
"""
from app import db
from datetime import datetime


class ChampionshipSeason(db.Model):
    __tablename__ = 'championship_seasons'

    id = db.Column(db.Integer, primary_key=True)
    month_id = db.Column(db.Integer, unique=True, nullable=False)  # year*100+month
    status = db.Column(db.String(20), default='forming')           # forming | active | completed

    # Absolute game-day numbers (days since GAME_START_DATE)
    start_game_day = db.Column(db.Integer, nullable=True)
    last_matchday_game_day = db.Column(db.Integer, nullable=True)   # the fixed "28th" matchday
    end_game_day = db.Column(db.Integer, nullable=True)             # last calendar day of month

    tiebreak_seed = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    groups = db.relationship('ChampionshipGroup', back_populates='season',
                             cascade='all, delete-orphan')
    memberships = db.relationship('ChampionshipMembership', back_populates='season',
                                  cascade='all, delete-orphan')
    matches = db.relationship('ChampionshipMatch', back_populates='season',
                              cascade='all, delete-orphan',
                              order_by='ChampionshipMatch.scheduled_game_day')

    def __repr__(self):
        return f'<ChampionshipSeason {self.month_id} {self.status}>'


class ChampionshipGroup(db.Model):
    __tablename__ = 'championship_groups'

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('championship_seasons.id'), nullable=False)
    tier = db.Column(db.String(10), nullable=False)        # elite|gold|silver|bronze|iron
    group_index = db.Column(db.Integer, nullable=False)    # 0-based within tier

    season = db.relationship('ChampionshipSeason', back_populates='groups')
    memberships = db.relationship('ChampionshipMembership', back_populates='group')
    matches = db.relationship('ChampionshipMatch', back_populates='group')

    @property
    def label(self):
        return f'{self.tier.capitalize()} {self.group_index + 1}'

    def __repr__(self):
        return f'<ChampionshipGroup {self.tier}#{self.group_index} season={self.season_id}>'


class ChampionshipMembership(db.Model):
    __tablename__ = 'championship_memberships'

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('championship_seasons.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('championship_groups.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)

    wins = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    goals_for = db.Column(db.Integer, default=0)
    goals_against = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=0)
    tiebreak_random = db.Column(db.Integer, default=0)

    final_position = db.Column(db.Integer, nullable=True)
    outcome = db.Column(db.String(10), nullable=True)      # promoted | relegated | stay

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('season_id', 'team_id', name='uq_cm_season_team'),
    )

    season = db.relationship('ChampionshipSeason', back_populates='memberships')
    group = db.relationship('ChampionshipGroup', back_populates='memberships')
    team = db.relationship('Team', foreign_keys=[team_id],
                           backref=db.backref('championship_memberships', lazy='dynamic'))

    @property
    def goals_diff(self):
        return self.goals_for - self.goals_against

    def __repr__(self):
        return f'<ChampionshipMembership team={self.team_id} season={self.season_id}>'


class ChampionshipMatch(db.Model):
    __tablename__ = 'championship_matches'

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('championship_seasons.id'), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('championship_groups.id'), nullable=False)
    home_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)

    round_number = db.Column(db.Integer, nullable=False)
    is_final_round = db.Column(db.Boolean, default=False)

    scheduled_game_day = db.Column(db.Integer, nullable=False, index=True)
    status = db.Column(db.String(20), default='scheduled')  # scheduled | played

    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)

    home_lineup_json = db.Column(db.Text, default='{}')
    away_lineup_json = db.Column(db.Text, default='{}')
    turns_json = db.Column(db.Text, default='[]')
    injuries_json = db.Column(db.Text, default='[]')

    played_game_day = db.Column(db.Integer, nullable=True)

    season = db.relationship('ChampionshipSeason', back_populates='matches')
    group = db.relationship('ChampionshipGroup', back_populates='matches')
    home_team = db.relationship('Team', foreign_keys=[home_team_id],
                                backref=db.backref('champ_home_matches', lazy='dynamic'))
    away_team = db.relationship('Team', foreign_keys=[away_team_id],
                                backref=db.backref('champ_away_matches', lazy='dynamic'))

    def __repr__(self):
        return (f'<ChampionshipMatch {self.home_team_id}v{self.away_team_id} '
                f'day={self.scheduled_game_day} {self.status}>')


# ── July annual finals: knockout tournaments + Supercoppa ───────────────────────

class Tournament(db.Model):
    __tablename__ = 'tournaments'

    id = db.Column(db.Integer, primary_key=True)
    season = db.Column(db.Integer, nullable=False, index=True)   # year the season started (Sep)
    kind = db.Column(db.String(12), nullable=False)              # main | secondary | supercoppa
    status = db.Column(db.String(20), default='active')          # active | completed

    bracket_size = db.Column(db.Integer, default=0)
    start_game_day = db.Column(db.Integer, nullable=True)
    days_between_rounds = db.Column(db.Integer, default=7)
    winner_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    matches = db.relationship('TournamentMatch', back_populates='tournament',
                              cascade='all, delete-orphan',
                              order_by='TournamentMatch.round_index, TournamentMatch.slot_index')
    winner_team = db.relationship('Team', foreign_keys=[winner_team_id])

    __table_args__ = (
        db.UniqueConstraint('season', 'kind', name='uq_tournament_season_kind'),
    )

    def __repr__(self):
        return f'<Tournament {self.kind} {self.season} {self.status}>'


class TournamentMatch(db.Model):
    __tablename__ = 'tournament_matches'

    id = db.Column(db.Integer, primary_key=True)
    tournament_id = db.Column(db.Integer, db.ForeignKey('tournaments.id'), nullable=False)

    round_index = db.Column(db.Integer, nullable=False)    # 0 = first round
    slot_index = db.Column(db.Integer, nullable=False)     # 0-based within the round

    home_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    away_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)

    scheduled_game_day = db.Column(db.Integer, nullable=False, index=True)
    status = db.Column(db.String(20), default='scheduled')  # scheduled | played

    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    decided_by_penalties = db.Column(db.Boolean, default=False)
    winner_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)

    home_lineup_json = db.Column(db.Text, default='{}')
    away_lineup_json = db.Column(db.Text, default='{}')
    turns_json = db.Column(db.Text, default='[]')
    injuries_json = db.Column(db.Text, default='[]')
    played_game_day = db.Column(db.Integer, nullable=True)

    tournament = db.relationship('Tournament', back_populates='matches')
    home_team = db.relationship('Team', foreign_keys=[home_team_id])
    away_team = db.relationship('Team', foreign_keys=[away_team_id])
    winner_team = db.relationship('Team', foreign_keys=[winner_team_id])

    def __repr__(self):
        return (f'<TournamentMatch t={self.tournament_id} r{self.round_index}s{self.slot_index} '
                f'{self.status}>')
