from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models.user import User
from app.models.team import Team, Player
from app.models.game import GameConfig
from app.utils.gameclock import (format_game_date, get_game_date,
                                  WEEKDAY_IT, MONTH_IT, advance_game_days,
                                  apply_time_mode, set_week_transition_hour,
                                  set_freeze_aug15)
from app.utils.validators import valid_hex_color, parse_float, parse_int
from functools import wraps

admin_bp = Blueprint('admin', __name__)

SKILLS = ['porta', 'difesa', 'attacco', 'resistenza']
PLAYER_TYPES = ['uomo', 'donna', 'cyber']
SKILL_MIN = 0.5
SKILL_MAX = 10.0
AGE_MIN = 15
AGE_MAX = 99
ROLES = ['superadmin', 'player']


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
    game_date = format_game_date()
    cfg = GameConfig.query.first()
    return render_template('admin/dashboard.html', users=users, teams=teams,
                           total_players=players, game_date=game_date, cfg=cfg)


@admin_bp.route('/clock/advance', methods=['POST'])
@login_required
@superadmin_required
def clock_advance():
    try:
        days = int(request.form.get('days', 1))
        if days < 1 or days > 365:
            raise ValueError
    except (ValueError, TypeError):
        flash('Numero di giorni non valido (1–365).', 'danger')
        return redirect(url_for('admin.dashboard'))

    cfg = GameConfig.query.first()
    if not cfg:
        flash('GameConfig non trovato. Avvia prima il gioco.', 'danger')
        return redirect(url_for('admin.dashboard'))

    advance_game_days(cfg, days)
    db.session.commit()
    flash(f'Data avanzata di {days} giorno/i. Nuova data: {format_game_date()}', 'success')
    return redirect(url_for('admin.dashboard'))


TIME_MODES = ('default', 'week', 'month')


@admin_bp.route('/clock/time-settings', methods=['POST'])
@login_required
@superadmin_required
def clock_time_settings():
    cfg = GameConfig.query.first()
    if not cfg:
        flash('GameConfig non trovato. Avvia prima il gioco.', 'danger')
        return redirect(url_for('admin.dashboard'))

    mode = request.form.get('time_mode', 'default')
    if mode not in TIME_MODES:
        flash('Modalità tempo non valida.', 'danger')
        return redirect(url_for('admin.dashboard'))

    try:
        hour = int(request.form.get('week_transition_hour', cfg.week_transition_hour))
        if hour < 0 or hour > 23:
            raise ValueError
    except (ValueError, TypeError):
        flash("Ora del server non valida (0–23).", 'danger')
        return redirect(url_for('admin.dashboard'))

    freeze = request.form.get('freeze_aug15') == 'on'
    fast_aug = request.form.get('fast_august') == 'on'

    # Order matters: set the transition hour first so a switch to week mode
    # aligns to it; then apply the mode; then the two checks.
    if hour != cfg.week_transition_hour:
        set_week_transition_hour(cfg, hour)
    if mode != cfg.time_mode:
        apply_time_mode(cfg, mode)
    cfg.fast_august = fast_aug
    set_freeze_aug15(cfg, freeze)

    db.session.commit()
    flash(f'Impostazioni tempo aggiornate. Data attuale: {format_game_date()}', 'success')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/gold/gift-all', methods=['POST'])
@login_required
@superadmin_required
def gold_gift_all():
    from app.utils import gold
    recipients = User.query.filter(User.role != 'superadmin').all()
    for u in recipients:
        gold.grant(u, 10, 'Regalo Federazione (admin)')
    db.session.commit()
    flash(f'🎁 Regalati 10 Gold a {len(recipients)} utenti.', 'success')
    return redirect(url_for('admin.dashboard'))


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
    # Teams with no manager OR already managed by this user
    free_teams = Team.query.filter(
        (Team.manager_id == None) | (Team.manager_id == user.id)
    ).order_by(Team.name).all()

    if request.method == 'POST':
        user.username = request.form.get('username', user.username).strip()
        user.email = request.form.get('email', user.email).strip().lower()
        new_role = request.form.get('role', user.role)
        if new_role in ROLES:
            user.role = new_role
        user.is_verified = request.form.get('is_verified') == 'on'
        new_pw = request.form.get('new_password', '').strip()
        if new_pw:
            if len(new_pw) < 8:
                flash('La nuova password deve avere almeno 8 caratteri.', 'danger')
                return render_template('admin/user_edit.html', user=user, free_teams=free_teams)
            user.set_password(new_pw)
        db.session.commit()
        flash(f'Utente {user.username} aggiornato.', 'success')
        return redirect(url_for('admin.users_list'))
    return render_template('admin/user_edit.html', user=user, free_teams=free_teams)


@admin_bp.route('/users/<int:user_id>/assign-team', methods=['POST'])
@login_required
@superadmin_required
def user_assign_team(user_id):
    user = User.query.get_or_404(user_id)
    team_id = parse_int(request.form.get('team_id'), 0)

    if not team_id:
        flash('Seleziona una squadra.', 'warning')
        return redirect(url_for('admin.user_edit', user_id=user_id))

    team = Team.query.get_or_404(team_id)

    # Unassign from previous manager if different
    if team.manager_id and team.manager_id != user_id:
        flash(f'La squadra {team.name} era già gestita da un altro manager: assegnazione aggiornata.', 'warning')

    # Remove old team from this user (one team per user)
    if user.team and user.team.id != team.id:
        user.team.manager_id = None

    team.manager_id = user.id
    db.session.commit()
    flash(f'Squadra "{team.name}" assegnata a {user.username}.', 'success')
    return redirect(url_for('admin.user_edit', user_id=user_id))


@admin_bp.route('/users/<int:user_id>/unassign-team', methods=['POST'])
@login_required
@superadmin_required
def user_unassign_team(user_id):
    user = User.query.get_or_404(user_id)
    if user.team:
        team_name = user.team.name
        user.team.manager_id = None
        db.session.commit()
        flash(f'Squadra "{team_name}" rimossa da {user.username}.', 'info')
    else:
        flash('Questo utente non ha una squadra assegnata.', 'warning')
    return redirect(url_for('admin.user_edit', user_id=user_id))


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
        budget = parse_float(request.form.get('budget'), 50_000_000)
        color_primary = valid_hex_color(request.form.get('color_primary'), '#00f5ff')
        color_secondary = valid_hex_color(request.form.get('color_secondary'), '#7b2fff')
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
        team.budget = parse_float(request.form.get('budget'), team.budget)
        team.color_primary = valid_hex_color(request.form.get('color_primary'), team.color_primary)
        team.color_secondary = valid_hex_color(request.form.get('color_secondary'), team.color_secondary)
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
        ptype = request.form.get('type', 'uomo')
        if ptype not in PLAYER_TYPES:
            ptype = 'uomo'
        from app.utils.social import roll_carisma
        player = Player(
            name=request.form.get('name', '').strip(),
            type=ptype,
            age=parse_int(request.form.get('age'), 20, AGE_MIN, AGE_MAX),
            porta=parse_float(request.form.get('porta'), 3.0, SKILL_MIN, SKILL_MAX),
            difesa=parse_float(request.form.get('difesa'), 3.0, SKILL_MIN, SKILL_MAX),
            attacco=parse_float(request.form.get('attacco'), 3.0, SKILL_MIN, SKILL_MAX),
            resistenza=parse_float(request.form.get('resistenza'), 3.0, SKILL_MIN, SKILL_MAX),
            carisma=roll_carisma(ptype),
        )
        team_id = parse_int(request.form.get('team_id'), 0)
        if team_id:
            player.team_id = team_id
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
        new_type = request.form.get('type', player.type)
        if new_type in PLAYER_TYPES:
            player.type = new_type
        player.age = parse_int(request.form.get('age'), player.age, AGE_MIN, AGE_MAX)
        player.porta = parse_float(request.form.get('porta'), player.porta, SKILL_MIN, SKILL_MAX)
        player.difesa = parse_float(request.form.get('difesa'), player.difesa, SKILL_MIN, SKILL_MAX)
        player.attacco = parse_float(request.form.get('attacco'), player.attacco, SKILL_MIN, SKILL_MAX)
        player.resistenza = parse_float(request.form.get('resistenza'), player.resistenza, SKILL_MIN, SKILL_MAX)
        team_id = parse_int(request.form.get('team_id'), 0)
        if team_id:
            player.team_id = team_id
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
