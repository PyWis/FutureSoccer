from app import db
from datetime import datetime
import json


class GameConfig(db.Model):
    __tablename__ = 'game_config'
    id = db.Column(db.Integer, primary_key=True)
    real_start = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # ── Time control (superadmin) ──
    # 'default' (1 ora reale = 1 giorno), 'week' (1 giorno reale ≈ 1 settimana),
    # 'month' (1 giorno reale = 1 mese)
    time_mode = db.Column(db.String(10), nullable=False, default='default')
    # Ora del server (UTC, 0-23) a cui avviene il passaggio Domenica→Lunedì in week mode
    week_transition_hour = db.Column(db.Integer, nullable=False, default=0)
    # Anchor del modello a settimane allineate (week mode)
    week_anchor_real = db.Column(db.DateTime, nullable=True)
    week_anchor_day = db.Column(db.Integer, nullable=True)  # game-day-number di un Lunedì
    # Check: blocca il gioco al 15 agosto finché il flag resta attivo
    freeze_aug15 = db.Column(db.Boolean, nullable=False, default=False)
    freeze_target = db.Column(db.DateTime, nullable=True)
    # Check: mese veloce dal 3 agosto per 24 giorni (1 ora reale per giorno)
    fast_august = db.Column(db.Boolean, nullable=False, default=False)


class TeamWeeklyOffer(db.Model):
    """One player offer per team per ISO game week (generated on or after Monday)."""
    __tablename__ = 'team_weekly_offers'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    game_week_id = db.Column(db.Integer, nullable=False)
    # Offer stats stored here; Player row created only on purchase
    offer_name = db.Column(db.String(100), nullable=False)
    offer_type = db.Column(db.String(10), nullable=False)
    offer_age = db.Column(db.Integer, nullable=False)
    offer_porta = db.Column(db.Float, nullable=False)
    offer_difesa = db.Column(db.Float, nullable=False)
    offer_attacco = db.Column(db.Float, nullable=False)
    offer_resistenza = db.Column(db.Float, nullable=False)
    offer_avg = db.Column(db.Float, nullable=False)
    is_scouted = db.Column(db.Boolean, default=False)
    purchased = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('team_id', 'game_week_id', name='uq_team_week_offer'),
    )

    team = db.relationship('Team', foreign_keys=[team_id], backref='weekly_offers')


class TrainingRecord(db.Model):
    """Result of one player's training on a specific game day."""
    __tablename__ = 'training_records'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    game_day = db.Column(db.Integer, nullable=False)
    skill1 = db.Column(db.String(20), nullable=False)
    skill2 = db.Column(db.String(20), nullable=False)
    premium_type = db.Column(db.String(20), default='standard')  # standard | p50k | p200k
    skill_improved = db.Column(db.String(20), nullable=True)
    improvement = db.Column(db.Float, default=0.0)
    cost = db.Column(db.Float, default=0.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('player_id', 'game_day', name='uq_player_training_day'),
    )

    player = db.relationship('Player', foreign_keys=[player_id])


class SponsorOffer(db.Model):
    """Friday sponsor proposal (one per team per ISO game week)."""
    __tablename__ = 'sponsor_offers'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    game_week_id = db.Column(db.Integer, nullable=False)
    sponsor_name = db.Column(db.String(100), nullable=False)
    weekly_amount = db.Column(db.Float, nullable=False)
    duration_weeks = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending | accepted | rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('team_id', 'game_week_id', name='uq_team_week_sponsor'),
    )


class ActiveSponsor(db.Model):
    """Active sponsor contract for a team."""
    __tablename__ = 'active_sponsors'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    sponsor_name = db.Column(db.String(100), nullable=False)
    weekly_amount = db.Column(db.Float, nullable=False)
    remaining_weeks = db.Column(db.Integer, nullable=False)
    type = db.Column(db.String(10), default='main')  # main | secondary | dark | shoe | gold | stadium
    last_paid_week_id = db.Column(db.Integer, default=-1)
    locked = db.Column(db.Boolean, default=False)  # contratti bloccati (non rimovibili)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team = db.relationship('Team', foreign_keys=[team_id], backref='active_sponsors')


_ENGAGEMENT_MODS = {
    'basso': 0.75, 'moderato': 0.90, 'normale': 1.00,
    'aggressivo': 1.10, 'super_aggressivo': 1.15,
}
ENGAGEMENT_OPTIONS = [
    ('basso',           'Basso',           '−20% gol · −50% calo freschezza'),
    ('moderato',        'Moderato',        '−20% gol · −50% calo freschezza'),
    ('normale',         'Normale',         'nessun effetto'),
    ('aggressivo',      'Aggressivo',      '+10% gol · +3% infortuni/turno'),
    ('super_aggressivo','Super aggressivo','+10% gol · +3% infortuni/turno'),
]


class TeamFormation(db.Model):
    """Saved formation and engagement for a team."""
    __tablename__ = 'team_formations'

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), unique=True, nullable=False)
    engagement = db.Column(db.String(20), default='normale')
    # Raw player IDs — no FK constraints to avoid cascade complexity
    goalkeeper_id   = db.Column(db.Integer, nullable=True)
    defender_ids_json = db.Column(db.Text, default='[]')   # JSON list[int]
    attacker_ids_json = db.Column(db.Text, default='[]')
    reserve_ids_json  = db.Column(db.Text, default='[]')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

    team = db.relationship('Team', backref=db.backref('formation', uselist=False))

    # ── helpers ──────────────────────────────────────────────────────────────

    @property
    def defender_ids(self):
        return json.loads(self.defender_ids_json or '[]')

    @property
    def attacker_ids(self):
        return json.loads(self.attacker_ids_json or '[]')

    @property
    def reserve_ids(self):
        return json.loads(self.reserve_ids_json or '[]')

    def all_starter_ids(self):
        ids = []
        if self.goalkeeper_id:
            ids.append(self.goalkeeper_id)
        ids.extend(self.defender_ids)
        ids.extend(self.attacker_ids)
        return ids

    def current_roles(self):
        """Returns {player_id: role_str} for all assigned players."""
        roles = {}
        if self.goalkeeper_id:
            roles[self.goalkeeper_id] = 'goalkeeper'
        for pid in self.defender_ids:
            roles[pid] = 'defender'
        for pid in self.attacker_ids:
            roles[pid] = 'attacker'
        for pid in self.reserve_ids:
            roles[pid] = 'reserve'
        return roles

    def compute_strength(self, players_by_id):
        """
        players_by_id: dict {player_id: Player}.
        Returns {'porta', 'difesa', 'attacco', 'total', 'mod', 'engagement'}.
        """
        gk = players_by_id.get(self.goalkeeper_id)
        defenders = [players_by_id[i] for i in self.defender_ids if i in players_by_id]
        attackers = [players_by_id[i] for i in self.attacker_ids if i in players_by_id]

        starters = ([gk] if gk else []) + defenders + attackers

        # Porta
        porta = gk.porta if gk else 2.0

        # Difesa: defenders' difesa + 50% from every other starter's difesa
        others_for_def = [p for p in starters if p not in defenders]
        difesa = sum(p.difesa for p in defenders) + 0.5 * sum(p.difesa for p in others_for_def)

        # Attacco: attackers' attacco + 50% from every other starter's attacco
        others_for_att = [p for p in starters if p not in attackers]
        attacco = sum(p.attacco for p in attackers) + 0.5 * sum(p.attacco for p in others_for_att)

        # Engagement no longer scales raw strength; its effects (goals, injuries,
        # freshness) are applied per turn in the match engine.
        return {
            'porta':   round(porta, 2),
            'difesa':  round(difesa, 2),
            'attacco': round(attacco, 2),
            'total':   round(porta + difesa + attacco, 2),
            'mod':     1.0,
            'engagement': self.engagement,
        }


class FreeAgentListing(db.Model):
    __tablename__ = 'free_agent_listings'
    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id', ondelete='SET NULL'), nullable=True)
    seller_team_id = db.Column(db.Integer, db.ForeignKey('teams.id', ondelete='SET NULL'), nullable=True)

    # Snapshot columns
    player_name = db.Column(db.String(100), nullable=False)
    player_type = db.Column(db.String(10), nullable=False)
    player_age = db.Column(db.Integer, nullable=False)
    player_porta = db.Column(db.Float, nullable=False)
    player_difesa = db.Column(db.Float, nullable=False)
    player_attacco = db.Column(db.Float, nullable=False)
    player_resistenza = db.Column(db.Float, nullable=False)
    player_avg = db.Column(db.Float, nullable=False)

    list_game_day = db.Column(db.Integer, nullable=False)
    base_price = db.Column(db.Float, nullable=False)
    expires_game_day = db.Column(db.Integer, nullable=False)

    bid_window_start = db.Column(db.Integer, nullable=True)
    bid_window_end = db.Column(db.Integer, nullable=True)

    status = db.Column(db.String(20), default='active')  # active | sold | expired
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    seller_team = db.relationship('Team', foreign_keys=[seller_team_id], backref='free_agent_listings')
    player = db.relationship('Player', foreign_keys=[player_id], backref='free_agent_listing')
    bids = db.relationship('FreeAgentBid', back_populates='listing', cascade='all, delete-orphan')


class FreeAgentBid(db.Model):
    __tablename__ = 'free_agent_bids'
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('free_agent_listings.id'), nullable=False)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    bid_game_day = db.Column(db.Integer, nullable=False)
    bid_timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # pending | won | lost

    __table_args__ = (
        db.UniqueConstraint('listing_id', 'team_id', name='uq_listing_team_bid'),
    )

    listing = db.relationship('FreeAgentListing', back_populates='bids')
    team = db.relationship('Team', foreign_keys=[team_id], backref='free_agent_bids')


class FriendlyMatch(db.Model):
    __tablename__ = 'friendly_matches'
    id = db.Column(db.Integer, primary_key=True)
    home_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=True)  # null = bot
    game_day = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='active')  # active | completed
    current_turn = db.Column(db.Integer, default=0)      # 0=pre-match, 1-6=regular, 7=extra
    home_score = db.Column(db.Integer, default=0)
    away_score = db.Column(db.Integer, default=0)
    last_turn_at = db.Column(db.DateTime, nullable=True)
    # Per-match lineup snapshots (JSON). Don't touch the saved TeamFormation.
    home_lineup_json = db.Column(db.Text, default='{}')
    away_lineup_json = db.Column(db.Text, default='{}')  # bot data when away_team_id is null
    # Pending substitutions submitted by user (applied next turn)
    home_pending_subs_json = db.Column(db.Text, default='{}')
    away_pending_subs_json = db.Column(db.Text, default='{}')
    # Accumulated injury penalties (applied to Player.freshness at match end)
    injuries_json = db.Column(db.Text, default='[]')
    # Turn-by-turn log
    turns_json = db.Column(db.Text, default='[]')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    home_team = db.relationship('Team', foreign_keys=[home_team_id],
                                backref=db.backref('home_matches', lazy='dynamic'))
    away_team = db.relationship('Team', foreign_keys=[away_team_id],
                                backref=db.backref('away_matches', lazy='dynamic'))


class MatchChallenge(db.Model):
    __tablename__ = 'match_challenges'
    id = db.Column(db.Integer, primary_key=True)
    challenger_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    challenged_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    game_day = db.Column(db.Integer, nullable=False)
    game_week_id = db.Column(db.Integer, nullable=True)   # ISO week the match is scheduled for
    status = db.Column(db.String(20), default='pending')  # pending | accepted | rejected
    match_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    challenger = db.relationship('Team', foreign_keys=[challenger_id],
                                 backref='sent_challenges')
    challenged = db.relationship('Team', foreign_keys=[challenged_id],
                                 backref='received_challenges')


class Loan(db.Model):
    __tablename__ = 'loans'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    loan_type = db.Column(db.String(20), nullable=False)   # green | yellow | red | black | federation
    principal = db.Column(db.Float, nullable=False)         # amount borrowed
    total_due = db.Column(db.Float, nullable=False)         # principal + interest
    weekly_payment = db.Column(db.Float, nullable=False)    # total_due / weeks_total
    weeks_total = db.Column(db.Integer, nullable=False)     # 25 | 50 | 75 | 100 (1 for federation)
    weeks_paid = db.Column(db.Integer, default=0)
    last_paid_week_id = db.Column(db.Integer, default=-1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team = db.relationship('Team', foreign_keys=[team_id], backref='loans')


class BudgetTransaction(db.Model):
    """Signed ledger entry for every change to a team's budget.

    amount > 0 = entrata (income), amount < 0 = uscita (expense).
    Lets us reconstruct entrate/uscite per week and per season.
    """
    __tablename__ = 'budget_transactions'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(30), nullable=False)
    description = db.Column(db.String(200), default='')
    game_day = db.Column(db.Integer, nullable=False)
    game_week_id = db.Column(db.Integer, nullable=False, index=True)
    season = db.Column(db.Integer, nullable=False, index=True)   # year the season started (Sep 1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team = db.relationship('Team', foreign_keys=[team_id], backref='transactions')


class GoldTransaction(db.Model):
    """Registro delle movimentazioni della valuta premium (Gold).

    amount > 0 = Gold accreditati (acquisto/pass/regalo), amount < 0 = Gold spesi.
    """
    __tablename__ = 'gold_transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    reason = db.Column(db.String(120), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id], backref='gold_transactions')


class Investment(db.Model):
    """Bond/cedola investment by a team."""
    __tablename__ = 'investments'
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    bond_type = db.Column(db.String(20), nullable=False)       # white|green|yellow|red|black
    original_type = db.Column(db.String(20), nullable=False)   # type purchased (before degradation)
    degraded = db.Column(db.Boolean, default=False)
    cost = db.Column(db.Float, nullable=False)
    payout = db.Column(db.Float, nullable=False)
    weeks_total = db.Column(db.Integer, nullable=False)
    game_week_id_bought = db.Column(db.Integer, nullable=False)
    game_week_id_maturity = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team = db.relationship('Team', foreign_keys=[team_id], backref='investments')
