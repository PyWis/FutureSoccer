from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from dotenv import load_dotenv
import os
import secrets

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
migrate = Migrate()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address, default_limits=[])

_DEFAULT_SECRET = 'dev-secret-key'


def create_app():
    app = Flask(__name__)

    is_prod = os.environ.get('FLASK_ENV') == 'production'
    secret = os.environ.get('SECRET_KEY')
    if not secret:
        if is_prod:
            raise RuntimeError('SECRET_KEY must be set in production.')
        # Dev fallback: random per-process key (sessions reset on restart, never hard-coded)
        secret = secrets.token_hex(32)
    app.config['SECRET_KEY'] = secret
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///futuresoccer.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # ── Session / cookie hardening ──
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['SESSION_COOKIE_SECURE'] = is_prod
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'
    app.config['REMEMBER_COOKIE_SECURE'] = is_prod

    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Accedi per continuare.'
    login_manager.login_message_category = 'warning'

    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.game import game_bp
    from app.routes.events import events_bp
    from app.routes.match import match_bp
    from app.routes.private_league import league_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(game_bp, url_prefix='/game')
    app.register_blueprint(events_bp, url_prefix='/events')
    app.register_blueprint(match_bp, url_prefix='/match')
    app.register_blueprint(league_bp, url_prefix='/leagues')

    @app.before_request
    def _apply_due_team_events():
        """Process all matured day-tick events for the active manager's team,
        on every page, so sponsor/loan/etc. always fire when the game day advances."""
        from flask import request
        from flask_login import current_user
        if request.endpoint in (None, 'static'):
            return
        if not current_user.is_authenticated:
            return
        team = getattr(current_user, 'team', None)
        if not team:
            return
        from app.routes.events import process_due_team_events
        try:
            process_due_team_events(team)
        except Exception:
            # Never let event processing brick a page load; leave DB clean.
            db.session.rollback()
        try:
            from app.utils.league_engine import process_due_league_events
            process_due_league_events()
        except Exception:
            db.session.rollback()

    @app.context_processor
    def inject_game_globals():
        from app.utils.gameclock import (
            get_game_date, format_game_date,
            get_game_weekday, is_training_day, is_sponsor_day,
        )
        from flask_login import current_user
        try:
            gd = get_game_date()
            fed_streak = 0
            fed_weeks_left = 0
            if current_user.is_authenticated and getattr(current_user, 'team', None):
                fed_streak = current_user.team.federation_loan_streak or 0
                fed_weeks_left = max(0, 25 - fed_streak) if fed_streak > 0 else 0
            return dict(
                g_date=format_game_date(gd),
                g_weekday=get_game_weekday(),
                g_is_training=is_training_day(),
                g_is_sponsor=is_sponsor_day(),
                g_fed_streak=fed_streak,
                g_fed_weeks_left=fed_weeks_left,
            )
        except Exception:
            return dict(g_date='', g_weekday=0, g_is_training=False, g_is_sponsor=False,
                        g_fed_streak=0, g_fed_weeks_left=0)

    @app.before_request
    def _require_setup():
        from flask import request as req, redirect, url_for
        from app.models.user import User
        exempt = {'auth.setup', 'static'}
        if req.endpoint in exempt:
            return
        if not User.query.filter_by(role='superadmin').first():
            return redirect(url_for('auth.setup'))

    with app.app_context():
        db.create_all()
        _seed_admin()
        _init_game_clock()

    return app


_DEFAULT_ADMIN_PASSWORD = 'admin'


def _seed_admin():
    """Seeds superadmin from env vars only when ADMIN_PASSWORD is explicitly configured."""
    from app.models.user import User
    if User.query.filter_by(role='superadmin').first():
        return
    password = os.environ.get('ADMIN_PASSWORD', '')
    if not password or password == _DEFAULT_ADMIN_PASSWORD:
        # No env-var seed configured — the setup wizard will handle creation.
        return
    is_prod = os.environ.get('FLASK_ENV') == 'production'
    if is_prod and len(password) < 12:
        raise RuntimeError('ADMIN_PASSWORD must be at least 12 characters in production.')
    admin = User(
        username=os.environ.get('ADMIN_USERNAME', 'fusoccer'),
        email=os.environ.get('ADMIN_EMAIL', 'admin@futuresoccer.com'),
        role='superadmin',
        is_verified=True,
    )
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()


def _init_game_clock():
    from app.models.game import GameConfig, Investment  # Investment imported to register metadata
    import app.models.private_league  # register private league tables
    from datetime import datetime
    if not GameConfig.query.first():
        db.session.add(GameConfig(real_start=datetime.utcnow()))
        db.session.commit()
