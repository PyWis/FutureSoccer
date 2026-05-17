from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.team import Team, Player
from functools import wraps

admin_bp = Blueprint('admin', __name__)

SKILLS = ['porta', 'difesa', 'attacco', 'resistenza']
PLAYER_TYPES = ['uomo', 'donna', 'cyber']


def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_superadmin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@login_required
@superadmin_required
def dashboard():
    users = User.query.order_by(User.created_at.desc()).all()
    teams = Team.query.order_by(Team.name).all()
    players = Player.query.count()
    return render_template('admin/dashboard.html', users=users, teams=teams, total_players=players)


# ─── USERS ────────────────────────────────────────────────────────────────────

@admin_bp.route('/users')
@login_required
@superadmin_required
def users_list():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=users)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@superadmin_required
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    if request.method == 'POST':
        user.username = request.form.get('username', user.username).strip()
        user.email = request.form.get('email', user.email).strip().lower()
        user.role = request.form.get('role', user.role)
        user.is_verified = request.form.get('is_verified') == 'on'
        new_pw = request.form.get('new_password', '').strip()
        if new_pw:
            if len(new_pw) < 8:
                flash('La nuova password deve avere almeno 8 caratteri.', 'danger')
                return render_template('admin/user_edit.html', user=user)
            user.set_password(new_pw)
        db.session.commit()
        flash(f'Utente {user.username} aggiornato.', 'success')
        return redirect(url_for('admin.users_list'))
    return render_template('admin/user_edit.html', user=user)


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def user_delete(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash('Non puoi eliminare il tuo account.', 'danger')
        return redirect(url_for('admin.users_list'))
    db.session.delete(user)
    db.session.commit()
    flash('Utente eliminato.', 'success')
    return redirect(url_for('admin.users_list'))


@admin_bp.route('/users/<int:user_id>/toggle-verify', methods=['POST'])
@login_required
@superadmin_required
def user_toggle_verify(user_id):
    user = User.query.get_or_404(user_id)
    user.is_verified = not user.is_verified
    db.session.commit()
    status = 'verificato' if user.is_verified else 'non verificato'
    flash(f'{user.username} è ora {status}.', 'info')
    return redirect(url_for('admin.users_list'))


# ─── TEAMS ────────────────────────────────────────────────────────────────────

@admin_bp.route('/teams')
@login_required
@superadmin_required
def teams_list():
    teams = Team.query.order_by(Team.name).all()
    return render_template('admin/teams.html', teams=teams)


@admin_bp.route('/teams/new', methods=['GET', 'POST'])
@login_required
@superadmin_required
def team_new():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        city = request.form.get('city', '').strip()
        stadium = request.form.get('stadium', '').strip()
        budget = float(request.form.get('budget', 50_000_000))
        color_primary = request.form.get('color_primary', '#00f5ff')
        color_secondary = request.form.get('color_secondary', '#7b2fff')
        if not name or not city or not stadium:
            flash('Compila tutti i campi obbligatori.', 'danger')
            return render_template('admin/team_form.html', team=None)
        if Team.query.filter_by(name=name).first():
            flash('Squadra già esistente.', 'danger')
            return render_template('admin/team_form.html', team=None)
        team = Team(name=name, city=city, stadium=stadium, budget=budget,
                    color_primary=color_primary, color_secondary=color_secondary)
        db.session.add(team)
        db.session.commit()
        flash(f'Squadra {name} creata!', 'success')
        return redirect(url_for('admin.teams_list'))
    return render_template('admin/team_form.html', team=None)


@admin_bp.route('/teams/<int:team_id>/edit', methods=['GET', 'POST'])
@login_required
@superadmin_required
def team_edit(team_id):
    team = Team.query.get_or_404(team_id)
    if request.method == 'POST':
        team.name = request.form.get('name', team.name).strip()
        team.city = request.form.get('city', team.city).strip()
        team.stadium = request.form.get('stadium', team.stadium).strip()
        team.budget = float(request.form.get('budget', team.budget))
        team.color_primary = request.form.get('color_primary', team.color_primary)
        team.color_secondary = request.form.get('color_secondary', team.color_secondary)
        db.session.commit()
        flash(f'Squadra {team.name} aggiornata.', 'success')
        return redirect(url_for('admin.teams_list'))
    return render_template('admin/team_form.html', team=team)


@admin_bp.route('/teams/<int:team_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def team_delete(team_id):
    team = Team.query.get_or_404(team_id)
    db.session.delete(team)
    db.session.commit()
    flash('Squadra eliminata.', 'success')
    return redirect(url_for('admin.teams_list'))


# ─── PLAYERS ──────────────────────────────────────────────────────────────────

@admin_bp.route('/players')
@login_required
@superadmin_required
def players_list():
    players = Player.query.order_by(Player.team_id, Player.name).all()
    return render_template('admin/players.html', players=players)


@admin_bp.route('/players/new', methods=['GET', 'POST'])
@login_required
@superadmin_required
def player_new():
    teams = Team.query.order_by(Team.name).all()
    if request.method == 'POST':
        player = Player(
            name=request.form.get('name', '').strip(),
            type=request.form.get('type', 'uomo'),
            age=int(request.form.get('age', 20)),
            porta=float(request.form.get('porta', 3.0)),
            difesa=float(request.form.get('difesa', 3.0)),
            attacco=float(request.form.get('attacco', 3.0)),
            resistenza=float(request.form.get('resistenza', 3.0)),
        )
        team_id = request.form.get('team_id')
        if team_id:
            player.team_id = int(team_id)
            player.is_free_agent = False
        db.session.add(player)
        db.session.commit()
        flash(f'Giocatore {player.name} creato!', 'success')
        return redirect(url_for('admin.players_list'))
    return render_template('admin/player_form.html', player=None, teams=teams,
                           types=PLAYER_TYPES)


@admin_bp.route('/players/<int:player_id>/edit', methods=['GET', 'POST'])
@login_required
@superadmin_required
def player_edit(player_id):
    player = Player.query.get_or_404(player_id)
    teams = Team.query.order_by(Team.name).all()
    if request.method == 'POST':
        player.name = request.form.get('name', player.name).strip()
        player.type = request.form.get('type', player.type)
        player.age = int(request.form.get('age', player.age))
        player.porta = float(request.form.get('porta', player.porta))
        player.difesa = float(request.form.get('difesa', player.difesa))
        player.attacco = float(request.form.get('attacco', player.attacco))
        player.resistenza = float(request.form.get('resistenza', player.resistenza))
        team_id = request.form.get('team_id')
        if team_id:
            player.team_id = int(team_id)
            player.is_free_agent = False
        else:
            player.team_id = None
            player.is_free_agent = True
        db.session.commit()
        flash(f'Giocatore {player.name} aggiornato.', 'success')
        return redirect(url_for('admin.players_list'))
    return render_template('admin/player_form.html', player=player, teams=teams,
                           types=PLAYER_TYPES)


@admin_bp.route('/players/<int:player_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def player_delete(player_id):
    player = Player.query.get_or_404(player_id)
    db.session.delete(player)
    db.session.commit()
    flash('Giocatore eliminato.', 'success')
    return redirect(url_for('admin.players_list'))
