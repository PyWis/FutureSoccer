from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.team import Team, Player

game_bp = Blueprint('game', __name__)


@game_bp.route('/dashboard')
@login_required
def dashboard():
    team = current_user.team
    return render_template('game/dashboard.html', team=team)


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

        team = Team(
            name=name, city=city, stadium=stadium,
            color_primary=color_primary, color_secondary=color_secondary,
            manager_id=current_user.id,
        )
        db.session.add(team)
        db.session.commit()
        flash(f'Squadra "{name}" creata! Benvenuto, Manager!', 'success')
        return redirect(url_for('game.dashboard'))

    return render_template('game/create_team.html')


@game_bp.route('/my-team')
@login_required
def my_team():
    if not current_user.team:
        return redirect(url_for('game.create_team'))
    team = current_user.team
    players = team.players.order_by(Player.overall.desc()).all()
    return render_template('game/my_team.html', team=team, players=players)


@game_bp.route('/market')
@login_required
def market():
    free_agents = Player.query.filter_by(is_free_agent=True).order_by(Player.overall.desc()).all()
    return render_template('game/market.html', players=free_agents)


@game_bp.route('/market/buy/<int:player_id>', methods=['POST'])
@login_required
def buy_player(player_id):
    if not current_user.team:
        flash('Devi prima creare una squadra.', 'warning')
        return redirect(url_for('game.create_team'))

    player = Player.query.get_or_404(player_id)
    team = current_user.team

    if not player.is_free_agent:
        flash('Questo giocatore non è disponibile.', 'danger')
        return redirect(url_for('game.market'))

    if team.budget < player.market_value:
        flash('Budget insufficiente per questo acquisto.', 'danger')
        return redirect(url_for('game.market'))

    team.budget -= player.market_value
    player.team_id = team.id
    player.is_free_agent = False
    db.session.commit()
    flash(f'{player.name} acquistato per €{player.market_value:,.0f}!', 'success')
    return redirect(url_for('game.my_team'))


@game_bp.route('/market/sell/<int:player_id>', methods=['POST'])
@login_required
def sell_player(player_id):
    player = Player.query.get_or_404(player_id)
    team = current_user.team

    if not team or player.team_id != team.id:
        flash('Operazione non autorizzata.', 'danger')
        return redirect(url_for('game.my_team'))

    team.budget += player.market_value * 0.8
    player.team_id = None
    player.is_free_agent = True
    db.session.commit()
    flash(f'{player.name} ceduto per €{player.market_value * 0.8:,.0f}!', 'info')
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
