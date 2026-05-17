from flask import Blueprint, render_template
from flask_login import current_user
from app.models.team import Team, Player

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    top_teams = Team.query.order_by(Team.prestige.desc()).limit(5).all()
    total_players = Player.query.count()
    total_teams = Team.query.count()
    return render_template('index.html',
                           top_teams=top_teams,
                           total_players=total_players,
                           total_teams=total_teams)
