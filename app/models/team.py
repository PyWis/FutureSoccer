from app import db
from datetime import datetime


class Team(db.Model):
    __tablename__ = 'teams'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    city = db.Column(db.String(100), nullable=False)
    stadium = db.Column(db.String(100), nullable=False)
    logo = db.Column(db.String(200), default='default_team.png')
    budget = db.Column(db.Float, default=50_000_000.0)
    prestige = db.Column(db.Integer, default=50)  # 0-100
    founded_year = db.Column(db.Integer, default=2099)
    wins = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    goals_for = db.Column(db.Integer, default=0)
    goals_against = db.Column(db.Integer, default=0)
    color_primary = db.Column(db.String(7), default='#00f5ff')
    color_secondary = db.Column(db.String(7), default='#7b2fff')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, unique=True)
    manager = db.relationship('User', back_populates='team')

    players = db.relationship('Player', back_populates='team', lazy='dynamic')

    @property
    def points(self):
        return self.wins * 3 + self.draws

    @property
    def goals_diff(self):
        return self.goals_for - self.goals_against

    def __repr__(self):
        return f'<Team {self.name}>'


class Player(db.Model):
    __tablename__ = 'players'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(30), nullable=False)  # GK, DEF, MID, FWD
    nationality = db.Column(db.String(50), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    overall = db.Column(db.Integer, default=70)   # 1-99
    potential = db.Column(db.Integer, default=75)  # 1-99
    market_value = db.Column(db.Float, default=1_000_000.0)
    salary = db.Column(db.Float, default=50_000.0)
    speed = db.Column(db.Integer, default=70)
    strength = db.Column(db.Integer, default=70)
    technique = db.Column(db.Integer, default=70)
    stamina = db.Column(db.Integer, default=70)
    cyber_enhancement = db.Column(db.Integer, default=0)  # 0-5 livello impianti cybernetici
    avatar = db.Column(db.String(200), default='default_player.png')
    is_free_agent = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    team = db.relationship('Team', back_populates='players')

    POSITIONS = ['GK', 'DEF', 'MID', 'FWD']

    def __repr__(self):
        return f'<Player {self.name} ({self.position})>'
