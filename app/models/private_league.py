from app import db
from datetime import datetime


class PrivateLeague(db.Model):
    __tablename__ = 'private_leagues'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    capacity = db.Column(db.Integer, default=4)     # starts at 4, +2/season, max 24
    loan_id = db.Column(db.Integer, db.ForeignKey('loans.id'), nullable=True)
    status = db.Column(db.String(20), default='open')   # open | suspended
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship('User', foreign_keys=[owner_id],
                            backref=db.backref('owned_league', uselist=False))
    loan = db.relationship('Loan', foreign_keys=[loan_id])
    seasons = db.relationship('PrivateLeagueSeason', back_populates='league',
                               order_by='PrivateLeagueSeason.season_number',
                               cascade='all, delete-orphan')

    @property
    def current_season(self):
        return PrivateLeagueSeason.query.filter_by(
            league_id=self.id
        ).filter(
            PrivateLeagueSeason.status.in_(['forming', 'active'])
        ).first()

    @property
    def last_completed_season(self):
        return PrivateLeagueSeason.query.filter_by(
            league_id=self.id, status='completed'
        ).order_by(PrivateLeagueSeason.season_number.desc()).first()

    @property
    def next_season_number(self):
        last = PrivateLeagueSeason.query.filter_by(league_id=self.id).order_by(
            PrivateLeagueSeason.season_number.desc()).first()
        return (last.season_number + 1) if last else 1

    def __repr__(self):
        return f'<PrivateLeague {self.name}>'


class PrivateLeagueSeason(db.Model):
    __tablename__ = 'private_league_seasons'

    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer, db.ForeignKey('private_leagues.id'), nullable=False)
    season_number = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='forming')
    # forming | active | completed | cancelled

    num_teams = db.Column(db.Integer, nullable=True)        # snapshot at season start
    capacity_at_start = db.Column(db.Integer, nullable=True)

    # Absolute game-day numbers (days since GAME_START_DATE)
    start_game_day = db.Column(db.Integer, nullable=True)
    end_game_day = db.Column(db.Integer, nullable=True)

    # Prestige
    prestige_base = db.Column(db.Float, default=0.0)
    prestige_coefficient = db.Column(db.Float, default=1_000_000.0)
    prestige_random = db.Column(db.Float, default=1.0)     # 0.70-1.00, fixed at start
    prestige = db.Column(db.Float, default=0.0)
    sponsor_amount = db.Column(db.Float, default=0.0)      # = prestige (already in M)

    # League wallet (single budget)
    total_budget = db.Column(db.Float, default=0.0)

    # Payout tracking
    last_payout_week_id = db.Column(db.Integer, default=0)

    # Deterministic RNG seed for tiebreak and calendar randomisation
    tiebreak_seed = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    league = db.relationship('PrivateLeague', back_populates='seasons')
    matches = db.relationship('PrivateLeagueMatch', back_populates='season',
                               cascade='all, delete-orphan',
                               order_by='PrivateLeagueMatch.scheduled_game_day')
    memberships = db.relationship('PrivateLeagueMembership', back_populates='season',
                                   cascade='all, delete-orphan')

    @property
    def duration_weeks(self):
        return self.num_teams or 0

    def __repr__(self):
        return f'<PrivateLeagueSeason league={self.league_id} s={self.season_number} {self.status}>'


class PrivateLeagueMembership(db.Model):
    __tablename__ = 'private_league_memberships'

    id = db.Column(db.Integer, primary_key=True)
    league_id = db.Column(db.Integer, db.ForeignKey('private_leagues.id'), nullable=False)
    season_id = db.Column(db.Integer, db.ForeignKey('private_league_seasons.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)

    status = db.Column(db.String(20), default='active')
    # active | excluded_auto | excluded_owner

    entry_fee_paid = db.Column(db.Boolean, default=False)
    permanence_fee_paid = db.Column(db.Boolean, default=False)

    # Season running stats
    wins = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    goals_for = db.Column(db.Integer, default=0)
    goals_against = db.Column(db.Integer, default=0)
    points = db.Column(db.Integer, default=0)
    tiebreak_random = db.Column(db.Integer, default=0)

    # End-of-season
    final_position = db.Column(db.Integer, nullable=True)
    force_snapshot = db.Column(db.Float, nullable=True)     # top7_avg_skill at season end

    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('season_id', 'team_id', name='uq_plm_season_team'),
    )

    season = db.relationship('PrivateLeagueSeason', back_populates='memberships')
    team = db.relationship('Team', foreign_keys=[team_id],
                           backref=db.backref('league_memberships', lazy='dynamic'))
    league = db.relationship('PrivateLeague', foreign_keys=[league_id],
                             backref=db.backref('all_memberships', lazy='dynamic'))

    @property
    def goals_diff(self):
        return self.goals_for - self.goals_against

    def __repr__(self):
        return f'<PrivateLeagueMembership team={self.team_id} season={self.season_id}>'


class PrivateLeagueMatch(db.Model):
    __tablename__ = 'private_league_matches'

    id = db.Column(db.Integer, primary_key=True)
    season_id = db.Column(db.Integer, db.ForeignKey('private_league_seasons.id'), nullable=False)
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

    season = db.relationship('PrivateLeagueSeason', back_populates='matches')
    home_team = db.relationship('Team', foreign_keys=[home_team_id],
                                backref=db.backref('league_home_matches', lazy='dynamic'))
    away_team = db.relationship('Team', foreign_keys=[away_team_id],
                                backref=db.backref('league_away_matches', lazy='dynamic'))

    def __repr__(self):
        return (f'<PrivateLeagueMatch {self.home_team_id}v{self.away_team_id} '
                f'day={self.scheduled_game_day} {self.status}>')
