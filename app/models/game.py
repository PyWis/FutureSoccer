from app import db
from datetime import datetime


class GameConfig(db.Model):
    __tablename__ = 'game_config'
    id = db.Column(db.Integer, primary_key=True)
    real_start = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


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
    type = db.Column(db.String(10), default='main')  # main | secondary
    last_paid_week_id = db.Column(db.Integer, default=-1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    team = db.relationship('Team', foreign_keys=[team_id], backref='active_sponsors')


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
