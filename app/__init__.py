from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_migrate import Migrate
from dotenv import load_dotenv
import os

load_dotenv()

db = SQLAlchemy()
login_manager = LoginManager()
bcrypt = Bcrypt()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///futuresoccer.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)
    bcrypt.init_app(app)
    migrate.init_app(app, db)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Accedi per continuare.'
    login_manager.login_message_category = 'warning'

    from app.routes.main import main_bp
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.game import game_bp
    from app.routes.events import events_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(game_bp, url_prefix='/game')
    app.register_blueprint(events_bp, url_prefix='/events')

    with app.app_context():
        db.create_all()
        _seed_admin()
        _init_game_clock()

    return app


def _seed_admin():
    from app.models.user import User
    if not User.query.filter_by(role='superadmin').first():
        admin = User(
            username=os.environ.get('ADMIN_USERNAME', 'fusoccer'),
            email=os.environ.get('ADMIN_EMAIL', 'admin@futuresoccer.com'),
            role='superadmin',
            is_verified=True,
        )
        admin.set_password(os.environ.get('ADMIN_PASSWORD', 'admin'))
        db.session.add(admin)
        db.session.commit()


def _init_game_clock():
    from app.models.game import GameConfig
    from datetime import datetime
    if not GameConfig.query.first():
        db.session.add(GameConfig(real_start=datetime.utcnow()))
        db.session.commit()
