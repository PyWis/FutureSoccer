import json
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.team import Team, Player
from app.models.game import FreeAgentListing, TeamFormation, ENGAGEMENT_OPTIONS
from app.utils.generators import generate_new_team_player
from app.utils.gameclock import (format_game_date, get_game_weekday, is_training_day,
                                 is_sponsor_day, get_game_day_number, get_game_week_id,
                                 get_prev_game_week_id, get_game_season, format_game_season,
                                 game_day_to_date, get_game_date)
from app.utils.validators import valid_hex_color
from app.utils import ledger
from app.utils import social

game_bp = Blueprint('game', __name__)

MAX_ROSTER = 12
MIN_ROSTER = 1

FACILITY_TYPES = ['training', 'stream', 'locker', 'ground']
FACILITY_LABELS = {
    'training': 'Impianto di allenamento',
    'stream':   'Servizi stream',
    'locker':   'Spogliatoi',
    'ground':   'Campo',
}
FACILITY_ICONS = {
    'training': '🏋️',
    'stream':   '📡',
    'locker':   '🚿',
    'ground':   '⚽',
}
FACILITY_EFFECTS = {
    'training': 'Allenamento gratuito al Sabato (p200k) per N giocatori pari alle stelle',
    'stream':   '— Effetto in arrivo',
    'locker':   'Ogni stella genera 1 sessione fisioterapia a settimana (visita Benessere per riscuotere)',
    'ground':   'Riduce il rischio infortuni in partita (-0.1% per stella)',
}
# Index = star level (0 = unbuilt). Upgrade cost = FACILITY_PRICES[n+1] - FACILITY_PRICES[n]
FACILITY_PRICES = [0, 1_000_000, 3_000_000, 5_000_000, 10_000_000, 25_000_000]


@game_bp.route('/dashboard')
@login_required
def dashboard():
    from app.routes.events import _process_sponsor_payments, _process_stadium_degradation
    if current_user.team:
        _process_sponsor_payments(current_user.team)
        _process_stadium_degradation(current_user.team)
    team = current_user.team
    weekday = get_game_weekday()
    return render_template('game/dashboard.html',
                           team=team,
                           game_date=format_game_date(),
                           weekday=weekday,
                           is_training=is_training_day(),
                           is_sponsor=is_sponsor_day())


def _process_team_freshness(team):
    """Add daily recovery (+0.2/day, cap 10) for all players based on days elapsed.

    During an active summer retreat (ritiro) freshness is frozen: players stay
    at 0 / negative until the retreat ends. We still advance last_freshness_day
    so recovery doesn't retroactively catch up once the retreat is over."""
    current_day = get_game_day_number()
    ritiro_active = team.ritiro_end_day > 0
    changed = False
    for player in team.players.all():
        days = max(0, current_day - player.last_freshness_day)
        if days > 0:
            if not ritiro_active:
                player.freshness = min(10.0, round(player.freshness + days * 0.2, 1))
            player.last_freshness_day = current_day
            changed = True
    if changed:
        db.session.commit()


@game_bp.route('/create-team', methods=['GET', 'POST'])
@login_required
def create_team():
    if current_user.team:
        return redirect(url_for('game.dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        city = request.form.get('city', '').strip()
        stadium = request.form.get('stadium', '').strip()
        color_primary = valid_hex_color(request.form.get('color_primary'), '#00f5ff')
        color_secondary = valid_hex_color(request.form.get('color_secondary'), '#7b2fff')

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
        db.session.flush()

        # Teams registering in August start in a paid SSS retreat.
        gd = get_game_date()
        if gd.month == 8:
            from app.routes.events import RITIRO_BASE_COST
            ledger.record(team, -RITIRO_BASE_COST, ledger.CAT_RETREAT,
                          'Iscrizione ad agosto: ritiro SSS')
            for p in team.players.all():
                if p.freshness > 0:
                    p.freshness = 0.0
            team.ritiro_type = 'sss'
            team.ritiro_year = gd.year
            team.ritiro_end_day = get_game_day_number() + 21

        db.session.commit()
        if gd.month == 8:
            flash(f'Squadra "{name}" fondata con 10 giocatori! 🚀 Iscrizione ad agosto: '
                  f'parti in ritiro alla SSS (costo addebitato).', 'success')
        else:
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
    if team.players.count() <= MIN_ROSTER:
        flash('Non puoi vendere il tuo ultimo giocatore: la rosa resterebbe vuota.', 'danger')
        return redirect(url_for('game.my_team'))
    list_game_day = get_game_day_number()
    base_price = round(player.avg_skill * 1_000_000, -3)
    listing = FreeAgentListing(
        player_id=player.id,
        seller_team_id=team.id,
        player_name=player.name,
        player_type=player.type,
        player_age=player.age,
        player_porta=player.porta,
        player_difesa=player.difesa,
        player_attacco=player.attacco,
        player_resistenza=player.resistenza,
        player_avg=player.avg_skill,
        list_game_day=list_game_day,
        base_price=base_price,
        expires_game_day=list_game_day + 90,
    )
    player.team_id = None
    player.is_free_agent = True
    db.session.add(listing)
    db.session.commit()
    flash('Giocatore messo sul mercato degli svincolati! Guadagnerai il 75% del prezzo se venduto entro 60 giorni, il 50% successivamente.', 'info')
    return redirect(url_for('game.my_team'))


@game_bp.route('/standings')
@login_required
def standings():
    teams = sorted(
        Team.query.all(),
        key=lambda t: (t.points, t.goals_diff, t.goals_for),
        reverse=True,
    )
    return render_template('game/standings.html', teams=teams)


@game_bp.route('/stadium')
@login_required
def stadium():
    if not current_user.team:
        return redirect(url_for('game.create_team'))
    team = current_user.team
    from app.routes.events import _process_stadium_degradation
    _process_stadium_degradation(team)
    return render_template('game/stadium.html',
                           team=team,
                           facility_types=FACILITY_TYPES,
                           facility_labels=FACILITY_LABELS,
                           facility_icons=FACILITY_ICONS,
                           facility_effects=FACILITY_EFFECTS,
                           facility_prices=FACILITY_PRICES)


@game_bp.route('/stadium/upgrade/<facility>', methods=['POST'])
@login_required
def stadium_upgrade(facility):
    if facility not in FACILITY_TYPES:
        flash('Struttura non valida.', 'danger')
        return redirect(url_for('game.stadium'))
    team = current_user.team
    if not team:
        return redirect(url_for('game.create_team'))
    attr = f'facility_{facility}'
    current_stars = getattr(team, attr)
    if current_stars >= 5:
        flash('Struttura già al massimo (5 stelle).', 'warning')
        return redirect(url_for('game.stadium'))
    upgrade_cost = FACILITY_PRICES[current_stars + 1] - FACILITY_PRICES[current_stars]
    if team.budget < upgrade_cost:
        flash(f'Budget insufficiente. Costo upgrade: €{upgrade_cost:,.0f}', 'danger')
        return redirect(url_for('game.stadium'))
    ledger.record(team, -upgrade_cost, ledger.CAT_STADIUM,
                  f'Upgrade {FACILITY_LABELS[facility]} → {current_stars + 1}⭐')
    setattr(team, attr, current_stars + 1)
    db.session.commit()
    flash(f'{FACILITY_LABELS[facility]} portato a {current_stars + 1} ⭐!', 'success')
    return redirect(url_for('game.stadium'))


# ─── FORMATION ─────────────────────────────────────────────────────────────────

@game_bp.route('/formation', methods=['GET', 'POST'])
@login_required
def formation():
    if not current_user.team:
        return redirect(url_for('game.create_team'))
    team = current_user.team
    _process_team_freshness(team)

    _sort_keys = {
        'avg':        lambda p: p.avg_skill,
        'porta':      lambda p: p.porta,
        'difesa':     lambda p: p.difesa,
        'attacco':    lambda p: p.attacco,
        'resistenza': lambda p: p.resistenza,
        'freshness':  lambda p: p.freshness,
    }
    sort_by = request.args.get('sort', 'avg')
    if sort_by not in _sort_keys:
        sort_by = 'avg'
    players = sorted(team.players.all(), key=_sort_keys[sort_by], reverse=True)
    players_by_id = {p.id: p for p in players}

    form_obj = team.formation
    if not form_obj:
        form_obj = TeamFormation(team_id=team.id)
        db.session.add(form_obj)
        db.session.commit()

    if request.method == 'POST':
        engagement = request.form.get('engagement', 'normale')
        if engagement not in dict([(e[0], e) for e in ENGAGEMENT_OPTIONS]):
            engagement = 'normale'

        goalkeeper_id = None
        defender_ids = []
        attacker_ids = []
        reserve_ids = []

        for p in players:
            role = request.form.get(f'role_{p.id}', '')
            if role == 'goalkeeper':
                goalkeeper_id = p.id
            elif role == 'defender':
                defender_ids.append(p.id)
            elif role == 'attacker':
                attacker_ids.append(p.id)
            elif role == 'reserve':
                reserve_ids.append(p.id)

        # Validate constraints
        n_starters = (1 if goalkeeper_id else 0) + len(defender_ids) + len(attacker_ids)
        errors = []
        if goalkeeper_id is not None and goalkeeper_id not in players_by_id:
            errors.append('Portiere non valido.')
        if len(defender_ids) > 3:
            errors.append('Massimo 3 difensori.')
        if len(attacker_ids) > 3:
            errors.append('Massimo 3 attaccanti.')
        if n_starters > 5:
            errors.append(f'Massimo 5 titolari (selezionati: {n_starters}).')
        if n_starters > 0 and len(defender_ids) == 0:
            errors.append('Seleziona almeno 1 difensore.')
        if n_starters > 0 and len(attacker_ids) == 0:
            errors.append('Seleziona almeno 1 attaccante.')
        if len(reserve_ids) > 3:
            errors.append('Massimo 3 riserve.')

        if errors:
            for e in errors:
                flash(e, 'danger')
        else:
            form_obj.engagement = engagement
            form_obj.goalkeeper_id = goalkeeper_id
            form_obj.defender_ids_json = json.dumps(defender_ids)
            form_obj.attacker_ids_json = json.dumps(attacker_ids)
            form_obj.reserve_ids_json = json.dumps(reserve_ids)
            form_obj.updated_at = __import__('datetime').datetime.utcnow()
            db.session.commit()
            flash('Formazione salvata!', 'success')

    strength = form_obj.compute_strength(players_by_id)
    current_roles = form_obj.current_roles()

    return render_template('game/formation.html',
                           team=team,
                           players=players,
                           formation=form_obj,
                           current_roles=current_roles,
                           strength=strength,
                           engagement_options=ENGAGEMENT_OPTIONS,
                           sort_by=sort_by)


def _aggregate_transactions(txs):
    """Split transactions into entrate/uscite grouped by category."""
    entrate, uscite = {}, {}
    for tx in txs:
        bucket = entrate if tx.amount >= 0 else uscite
        bucket[tx.category] = bucket.get(tx.category, 0.0) + abs(tx.amount)
    tot_in = sum(entrate.values())
    tot_out = sum(uscite.values())
    return {
        'entrate': sorted(entrate.items(), key=lambda kv: kv[1], reverse=True),
        'uscite':  sorted(uscite.items(), key=lambda kv: kv[1], reverse=True),
        'tot_in': tot_in,
        'tot_out': tot_out,
        'net': tot_in - tot_out,
    }


@game_bp.route('/bilancio')
@login_required
def bilancio():
    if not current_user.team:
        return redirect(url_for('game.create_team'))
    from app.models.game import BudgetTransaction
    team = current_user.team

    prev_week = get_prev_game_week_id()
    season = get_game_season()

    week_txs = BudgetTransaction.query.filter_by(
        team_id=team.id, game_week_id=prev_week).order_by(BudgetTransaction.created_at.desc()).all()
    season_txs = BudgetTransaction.query.filter_by(
        team_id=team.id, season=season).order_by(BudgetTransaction.created_at.desc()).all()

    return render_template('game/bilancio.html',
                           team=team,
                           game_date=format_game_date(),
                           prev_week_summary=_aggregate_transactions(week_txs),
                           season_summary=_aggregate_transactions(season_txs),
                           recent_txs=season_txs[:40],
                           season_label=format_game_season(season),
                           cat_label=ledger.category_label,
                           cat_icon=ledger.category_icon)


@game_bp.route('/calendario')
@login_required
def calendario():
    if not current_user.team:
        return redirect(url_for('game.create_team'))
    from app.models.game import FriendlyMatch, MatchChallenge
    team = current_user.team
    season = get_game_season()
    current_day = get_game_day_number()

    matches = FriendlyMatch.query.filter(
        db.or_(FriendlyMatch.home_team_id == team.id,
               FriendlyMatch.away_team_id == team.id)
    ).order_by(FriendlyMatch.game_day.desc()).all()

    played = []
    for m in matches:
        d = game_day_to_date(m.game_day)
        if get_game_season(d) != season:
            continue
        is_home = (m.home_team_id == team.id)
        opp = ('Squadra del Bar' if m.away_team_id is None
               else (m.away_team.name if is_home and m.away_team else
                     (m.home_team.name if not is_home and m.home_team else 'Avversario')))
        gf = m.home_score if is_home else m.away_score
        ga = m.away_score if is_home else m.home_score
        if m.status == 'completed':
            outcome = 'V' if gf > ga else ('P' if gf < ga else 'N')
        else:
            outcome = None
        played.append({
            'match': m, 'date': d, 'opponent': opp, 'is_home': is_home,
            'gf': gf, 'ga': ga, 'outcome': outcome,
        })

    week_monday = current_day - get_game_weekday()
    upcoming = MatchChallenge.query.filter(
        MatchChallenge.match_id == None,
        MatchChallenge.status.in_(('pending', 'accepted')),
        MatchChallenge.game_day >= week_monday,
        db.or_(MatchChallenge.challenger_id == team.id,
               MatchChallenge.challenged_id == team.id),
    ).all()
    upcoming_view = []
    for ch in upcoming:
        is_challenger = (ch.challenger_id == team.id)
        opp_team = Team.query.get(ch.challenged_id if is_challenger else ch.challenger_id)
        upcoming_view.append({
            'challenge': ch,
            'opponent': opp_team.name if opp_team else 'Avversario',
            'direction': 'inviata' if is_challenger else 'ricevuta',
        })

    return render_template('game/calendario.html',
                           team=team,
                           game_date=format_game_date(),
                           season_label=format_game_season(season),
                           played=played,
                           upcoming=upcoming_view,
                           fmt_date=format_game_date)


@game_bp.route('/social')
@login_required
def social_page():
    if not current_user.team:
        return redirect(url_for('game.create_team'))
    team = current_user.team
    players = sorted(team.players.all(), key=lambda p: p.avg_skill, reverse=True)
    state = social.compute_state(team)
    active = state['active']

    effects_view = []
    for key, spec in sorted(social.SOCIAL_EFFECTS.items(), key=lambda kv: kv[1]['threshold']):
        constraint_ok = social.meets_constraint(team, spec.get('requires'))
        is_active = key in active
        # Can activate if not active, slot free, constraint ok, and enough available influence
        can_activate = (not is_active and len(active) < social.MAX_ACTIVE_EFFECTS
                        and constraint_ok and state['available'] >= spec['threshold'])
        effects_view.append({
            'key': key, 'spec': spec,
            'is_active': is_active,
            'constraint_ok': constraint_ok,
            'can_activate': can_activate,
            'applies': state['applies'].get(key, False),
        })

    return render_template('game/social.html',
                           team=team,
                           game_date=format_game_date(),
                           players=players,
                           channels=social.SOCIAL_CHANNELS,
                           channel_count=social.channel_count,
                           points=state['total'],
                           committed=state['committed'],
                           available=state['available'],
                           multiplier=state['multiplier'],
                           active_count=len(active),
                           max_active=social.MAX_ACTIVE_EFFECTS,
                           effects=effects_view)


@game_bp.route('/social/channel/<int:player_id>/<channel>', methods=['POST'])
@login_required
def social_toggle_channel(player_id, channel):
    if not current_user.team:
        return redirect(url_for('game.create_team'))
    if channel not in social.CHANNEL_KEYS:
        flash('Canale non valido.', 'danger')
        return redirect(url_for('game.social_page'))
    player = Player.query.get_or_404(player_id)
    if player.team_id != current_user.team.id:
        flash('Giocatore non nella tua squadra.', 'danger')
        return redirect(url_for('game.social_page'))
    attr = f'social_{channel}'
    setattr(player, attr, not getattr(player, attr))
    db.session.commit()
    state = 'aperto' if getattr(player, attr) else 'chiuso'
    flash(f'Canale {channel} {state} per {player.name}.', 'info')
    return redirect(url_for('game.social_page'))


@game_bp.route('/social/effect/<key>/<action>', methods=['POST'])
@login_required
def social_effect(key, action):
    if not current_user.team:
        return redirect(url_for('game.create_team'))
    team = current_user.team
    if key not in social.SOCIAL_EFFECTS:
        flash('Effetto non valido.', 'danger')
        return redirect(url_for('game.social_page'))
    spec = social.SOCIAL_EFFECTS[key]
    active = social.get_active_effects(team)

    if action == 'deactivate':
        if key in active:
            active.remove(key)
            social.set_active_effects(team, active)
            db.session.commit()
            flash(f'{spec["label"]} disattivato.', 'info')
        return redirect(url_for('game.social_page'))

    if action == 'activate':
        if key in active:
            flash('Effetto già attivo.', 'warning')
            return redirect(url_for('game.social_page'))
        if len(active) >= social.MAX_ACTIVE_EFFECTS:
            flash(f'Puoi avere al massimo {social.MAX_ACTIVE_EFFECTS} effetti attivi.', 'danger')
            return redirect(url_for('game.social_page'))
        if not social.meets_constraint(team, spec.get('requires')):
            msg = {'women': 'squadra composta solo da donne',
                   'cyber': 'squadra composta solo da cyber',
                   'lite': f'squadra con {social.LITE_MAX_PLAYERS} o meno componenti'}.get(spec.get('requires'))
            flash(f'Questo effetto richiede una {msg}.', 'danger')
            return redirect(url_for('game.social_page'))
        state = social.compute_state(team)
        if state['available'] < spec['threshold']:
            flash(f'Influenza disponibile insufficiente: servono {spec["threshold"]} punti '
                  f'(disponibili {state["available"]}).', 'danger')
            return redirect(url_for('game.social_page'))
        active.append(key)
        social.set_active_effects(team, active)
        db.session.commit()
        flash(f'{spec["label"]} attivato! 🥂', 'success')
        return redirect(url_for('game.social_page'))

    flash('Azione non valida.', 'danger')
    return redirect(url_for('game.social_page'))


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
