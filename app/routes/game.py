from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.team import Team, Player
from app.utils.generators import generate_new_team_player
from app.utils.gameclock import format_game_date, get_game_weekday, is_training_day, is_sponsor_day

game_bp = Blueprint('game', __name__)

MAX_ROSTER = 12


@game_bp.route('/dashboard')
@login_required
def dashboard():
    from app.routes.events import _process_sponsor_payments
    if current_user.team:
        _process_sponsor_payments(current_user.team)
    team = current_user.team
    weekday = get_game_weekday()
    return render_template('game/dashboard.html',
                           team=team,
                           game_date=format_game_date(),
                           weekday=weekday,
                           is_training=is_training_day(),
                           is_sponsor=is_sponsor_day())


@game_bp.route('/create-team', methods=['GET', 'POST'])
@login_required
def create_team():
    if current_user.team:
        return redirect(url_for('game.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        city = request.form.get('city', '').strip()
        stadium = request.form.get('stadium', '').strip()
        color_primary = request.form.get('color_primary', '#00f5ff')
        color_secondary = request.form.get('color_secondary', '#7b2fff')

        if not name or not city or not stadium:
            flash('Compila tutti i campi.', 'danger')
            return render_template('game/create_team.html')
        if Team.query.filter_by(name=name).first():
            flash('Nome squadra già in uso.', 'danger')
            return render_template('game/create_team.html')

        team = Team(name=name, city=city, stadium=stadium,
                    color_primary=color_primary, color_secondary=color_secondary,
                    manager_id=current_user.id)
        db.session.add(team)
        db.session.flush()   # get team.id before generating players

        for _ in range(10):
            db.session.add(generate_new_team_player(team.id))

        db.session.commit()
        flash(f'Squadra "{name}" fondata con 10 giocatori! Buona fortuna, Manager.', 'success')
        return redirect(url_for('game.dashboard'))

    return render_template('game/create_team.html')


@game_bp.route('/my-team')
@login_required
def my_team():
    if not current_user.team:
        return redirect(url_for('game.create_team'))
    team = current_user.team
    players = sorted(team.players.all(), key=lambda p: p.avg_skill, reverse=True)
    return render_template('game/my_team.html', team=team, players=players)


@game_bp.route('/sell/<int:player_id>', methods=['POST'])
@login_required
def sell_player(player_id):
    player = Player.query.get_or_404(player_id)
    team = current_user.team
    if not team or player.team_id != team.id:
        flash('Operazione non autorizzata.', 'danger')
        return redirect(url_for('game.my_team'))
    proceeds = round(player.avg_skill * 400_000, -3)
    team.budget += proceeds
    player.team_id = None
    player.is_free_agent = True
    db.session.commit()
    flash(f'{player.name} ceduto per €{proceeds:,.0f}.', 'info')
    return redirect(url_for('game.my_team'))


@game_bp.route('/standings')
@login_required
def standings():
    teams = Team.query.order_by(
        Team.wins.desc(), Team.draws.desc(), Team.goals_for.desc()
    ).all()
    return render_template('game/standings.html', teams=teams)


@game_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        new_username = request.form.get('username', '').strip()
        if new_username and len(new_username) >= 3:
            from app.models.user import User
            existing = User.query.filter_by(username=new_username).first()
            if existing and existing.id != current_user.id:
                flash('Nome utente già in uso.', 'danger')
            else:
                current_user.username = new_username
                db.session.commit()
                flash('Profilo aggiornato!', 'success')
        else:
            flash('Nome utente non valido.', 'danger')
        return redirect(url_for('game.profile'))
    return render_template('game/profile.html')
