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
    wins = db.Column(db.Integer, default=0)
    draws = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    goals_for = db.Column(db.Integer, default=0)
    goals_against = db.Column(db.Integer, default=0)
    color_primary = db.Column(db.String(7), default='#00f5ff')
    color_secondary = db.Column(db.String(7), default='#7b2fff')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Game events tracking
    scouting_paid_week_id = db.Column(db.Integer, default=-1)   # ISO week_id of last paid scouting
    scouting_enabled = db.Column(db.Boolean, default=False)      # recurring scouting active
    last_processed_day = db.Column(db.Integer, default=-1)       # for daily event processing

    # Stadium facilities (0 = not built, 1-5 = stars)
    facility_training = db.Column(db.Integer, default=0)   # Impianto di allenamento
    facility_stream   = db.Column(db.Integer, default=0)   # Servizi stream
    facility_locker   = db.Column(db.Integer, default=0)   # Spogliatoi
    facility_ground   = db.Column(db.Integer, default=0)   # Ground
    last_degraded_month = db.Column(db.Integer, default=0) # year*100+month last degradation applied

    manager_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, unique=True)
    manager = db.relationship('User', back_populates='team')

    players = db.relationship('Player', back_populates='team', lazy='dynamic')

    @property
    def points(self):
        return self.wins * 3 + self.draws

    @property
    def goals_diff(self):
        return self.goals_for - self.goals_against

    @property
    def scouting_active(self):
        from app.utils.gameclock import get_game_week_id
        return self.scouting_paid_week_id == get_game_week_id()

    @property
    def scouting_pending_next_week(self):
        from app.utils.gameclock import get_next_game_week_id
        return self.scouting_enabled and self.scouting_paid_week_id == get_next_game_week_id()

    @property
    def top7_avg_skill(self):
        """Average skill of top-7 players by avg_skill (used for sponsor value)."""
        sorted_players = sorted(self.players.all(), key=lambda p: p.avg_skill, reverse=True)
        top = sorted_players[:7]
        if not top:
            return 0.0
        return round(sum(p.avg_skill for p in top) / len(top), 2)

    def __repr__(self):
        return f'<Team {self.name}>'


class Player(db.Model):
    __tablename__ = 'players'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    type = db.Column(db.String(10), default='uomo')   # uomo | donna | cyber
    age = db.Column(db.Integer, default=19)

    # Skills — range 0.5 to 6.5
    porta = db.Column(db.Float, default=3.0)
    difesa = db.Column(db.Float, default=3.0)
    attacco = db.Column(db.Float, default=3.0)
    resistenza = db.Column(db.Float, default=3.0)

    is_free_agent = db.Column(db.Boolean, default=True)
    freshness = db.Column(db.Float, default=10.0)          # 0–10, starts at 10
    last_freshness_day = db.Column(db.Integer, default=0)  # game day of last freshness update
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)
    team = db.relationship('Team', back_populates='players')

    @property
    def avg_skill(self):
        return round((self.porta + self.difesa + self.attacco + self.resistenza) / 4, 2)

    @property
    def type_icon(self):
        return {'uomo': '👨', 'donna': '👩', 'cyber': '🤖'}.get(self.type, '👤')

    @property
    def type_badge(self):
        return {'uomo': 'badge-cyan', 'donna': 'badge-purple', 'cyber': 'badge-gold'}.get(self.type, 'badge-cyan')

    def __repr__(self):
        return f'<Player {self.name}>'
