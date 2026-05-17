from flask import Blueprint, render_template
from flask_login import current_user
from app.models.team import Team, Player

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    all_teams = Team.query.all()
    top_teams = sorted(all_teams, key=lambda t: t.top7_avg_skill, reverse=True)[:5]
    total_players = Player.query.count()
    total_teams = Team.query.count()
    return render_template('index.html',
                           top_teams=top_teams,
                           total_players=total_players,
                           total_teams=total_teams)
