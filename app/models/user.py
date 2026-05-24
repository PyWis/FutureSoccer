from app import db, bcrypt, login_manager
from flask_login import UserMixin
from datetime import datetime
import secrets


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=True)
    role = db.Column(db.String(20), default='player')  # superadmin | player
    is_verified = db.Column(db.Boolean, default=False)
    verification_token = db.Column(db.String(100), nullable=True)
    verification_token_expires = db.Column(db.DateTime, nullable=True)
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)
    avatar = db.Column(db.String(200), default='default_avatar.png')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Premium currency (Gold) and pass tracking
    gold = db.Column(db.Integer, default=0, nullable=False)
    seasonal_pass_season = db.Column(db.Integer, default=-1)  # last season the Pass Stagionale was bought

    team = db.relationship('Team', back_populates='manager', uselist=False, lazy='select')

    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

    def generate_verification_token(self):
        from datetime import timedelta
        self.verification_token = secrets.token_urlsafe(32)
        self.verification_token_expires = datetime.utcnow() + timedelta(hours=24)
        return self.verification_token

    def generate_reset_token(self):
        self.reset_token = secrets.token_urlsafe(32)
        from datetime import timedelta
        self.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
        return self.reset_token

    @property
    def is_superadmin(self):
        return self.role == 'superadmin'

    def __repr__(self):
        return f'<User {self.username}>'
