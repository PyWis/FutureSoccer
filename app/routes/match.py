import json
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from app import db
from app.models.game import FriendlyMatch, MatchChallenge, TeamFormation
from app.models.team import Team
from app.utils.gameclock import (get_game_day_number, get_game_weekday, format_game_date,
                                  get_game_week_id, get_seconds_into_game_day)
from datetime import datetime, timedelta

match_bp = Blueprint('match', __name__)
TURN_DURATION = 30  # seconds per turn


def _get_team_or_redirect():
    """Return current user's team or None (caller should redirect if None)."""
    return current_user.team if current_user.is_authenticated else None


def _require_sunday():
    """Flash + return False if not Sunday (weekday == 6)."""
    if get_game_weekday() != 6:
        flash('Le partite amichevoli si giocano solo la Domenica.', 'warning')
        return False
    return True


def _week_monday_game_day():
    """Returns the game_day of this week's Monday."""
    return get_game_day_number() - get_game_weekday()


@match_bp.route('/')
@login_required
def lobby():
    team = _get_team_or_redirect()
    if not team:
        return redirect(url_for('game.create_team'))

    weekday = get_game_weekday()
    is_sunday = (weekday == 6)
    current_day = get_game_day_number()
    week_id = get_game_week_id()
    week_monday = _week_monday_game_day()

    # Check for active match
    active_match = FriendlyMatch.query.filter(
        FriendlyMatch.status == 'active',
        db.or_(
            FriendlyMatch.home_team_id == team.id,
            FriendlyMatch.away_team_id == team.id,
        )
    ).first()
    if active_match:
        return redirect(url_for('match.view', match_id=active_match.id))

    # Pending challenges received this week
    pending_challenges = MatchChallenge.query.filter(
        MatchChallenge.challenged_id == team.id,
        MatchChallenge.game_day >= week_monday,
        MatchChallenge.status == 'pending',
    ).all()

    # Accepted challenges this week — shown on Sunday as "start" buttons,
    # shown Mon-Sat as "confirmed upcoming match" info
    accepted_challenges = MatchChallenge.query.filter(
        MatchChallenge.game_day >= week_monday,
        MatchChallenge.match_id == None,
        MatchChallenge.status == 'accepted',
        db.or_(
            MatchChallenge.challenger_id == team.id,
            MatchChallenge.challenged_id == team.id,
        )
    ).all()

    # Completed match this week (for result display)
    completed_match = FriendlyMatch.query.filter(
        FriendlyMatch.game_day >= week_monday,
        FriendlyMatch.status == 'completed',
        db.or_(
            FriendlyMatch.home_team_id == team.id,
            FriendlyMatch.away_team_id == team.id,
        )
    ).first()

    # Teams already challenged this week by this team
    already_challenged_ids = {
        c.challenged_id for c in MatchChallenge.query.filter(
            MatchChallenge.challenger_id == team.id,
            MatchChallenge.game_day >= week_monday,
        ).all()
    }

    # All other teams (exclude own, exclude already challenged this week)
    can_challenge = not is_sunday  # challenges only Mon-Sat
    other_teams = []
    if can_challenge:
        other_teams = Team.query.filter(
            Team.id != team.id,
            ~Team.id.in_(already_challenged_ids),
        ).all()

    # Sunday match auto-start logic: matches start 60 real seconds after Sunday begins
    SUNDAY_DELAY = 60  # seconds
    seconds_into_sunday = get_seconds_into_game_day() if is_sunday else 0
    sunday_unlocked = is_sunday and seconds_into_sunday >= SUNDAY_DELAY
    sunday_countdown = max(0, int(SUNDAY_DELAY - seconds_into_sunday)) if is_sunday else 0

    # Auto-start accepted challenges once Sunday is unlocked
    if sunday_unlocked:
        from app.utils.match_engine import build_home_lineup
        for ch in list(accepted_challenges):
            if ch.match_id is not None:
                continue
            challenger_team = Team.query.get(ch.challenger_id)
            challenged_team = Team.query.get(ch.challenged_id)
            if not challenger_team or not challenged_team:
                continue
            cf = TeamFormation.query.filter_by(team_id=challenger_team.id).first()
            df = TeamFormation.query.filter_by(team_id=challenged_team.id).first()
            if not cf or not df:
                continue
            match = FriendlyMatch(
                home_team_id=challenger_team.id,
                away_team_id=challenged_team.id,
                game_day=current_day,
                home_lineup_json=json.dumps(build_home_lineup(challenger_team, cf)),
                away_lineup_json=json.dumps(build_home_lineup(challenged_team, df)),
                last_turn_at=datetime.utcnow(),
                status='active',
                current_turn=0,
            )
            db.session.add(match)
            db.session.flush()
            ch.match_id = match.id
        db.session.commit()
        # Re-query accepted_challenges to reflect updated match_ids
        accepted_challenges = MatchChallenge.query.filter(
            MatchChallenge.game_day >= week_monday,
            MatchChallenge.match_id != None,
            MatchChallenge.status == 'accepted',
            db.or_(
                MatchChallenge.challenger_id == team.id,
                MatchChallenge.challenged_id == team.id,
            )
        ).all()
        # Redirect directly to match if this team's match just started
        for ch in accepted_challenges:
            if ch.match_id and (ch.challenger_id == team.id or ch.challenged_id == team.id):
                m = FriendlyMatch.query.get(ch.match_id)
                if m and m.status == 'active':
                    return redirect(url_for('match.view', match_id=m.id))

    return render_template(
        'match/lobby.html',
        team=team,
        is_sunday=is_sunday,
        sunday_unlocked=sunday_unlocked,
        sunday_countdown=sunday_countdown,
        can_challenge=can_challenge,
        pending_challenges=pending_challenges,
        accepted_challenges=accepted_challenges,
        completed_match=completed_match,
        other_teams=other_teams,
        current_day=current_day,
    )


@match_bp.route('/start-bot', methods=['POST'])
@login_required
def start_bot():
    team = _get_team_or_redirect()
    if not team:
        return redirect(url_for('game.create_team'))
    if not _require_sunday():
        return redirect(url_for('match.lobby'))

    current_day = get_game_day_number()

    # Check no active match exists today
    existing = FriendlyMatch.query.filter(
        FriendlyMatch.game_day == current_day,
        FriendlyMatch.status == 'active',
        db.or_(
            FriendlyMatch.home_team_id == team.id,
            FriendlyMatch.away_team_id == team.id,
        )
    ).first()
    if existing:
        flash('Hai già una partita in corso.', 'warning')
        return redirect(url_for('match.view', match_id=existing.id))

    # Check team has a saved formation
    formation = TeamFormation.query.filter_by(team_id=team.id).first()
    if not formation:
        flash('Devi salvare una formazione prima di giocare.', 'danger')
        return redirect(url_for('match.lobby'))

    defender_ids = json.loads(formation.defender_ids_json or '[]')
    attacker_ids = json.loads(formation.attacker_ids_json or '[]')
    if not defender_ids and not attacker_ids:
        flash('La formazione deve avere almeno un difensore o un attaccante.', 'danger')
        return redirect(url_for('match.lobby'))

    from app.utils.match_engine import build_home_lineup, generate_bot_lineup

    home_lineup = build_home_lineup(team, formation)

    # Check at least 2 starters
    starters_count = 0
    if home_lineup.get('goalkeeper'):
        starters_count += 1
    starters_count += len(home_lineup.get('defenders') or [])
    starters_count += len(home_lineup.get('attackers') or [])

    if starters_count < 2:
        flash('Non hai abbastanza giocatori in forma per giocare (minimo 2 titolari).', 'danger')
        return redirect(url_for('match.lobby'))

    bot_lineup = generate_bot_lineup()

    match = FriendlyMatch(
        home_team_id=team.id,
        away_team_id=None,
        game_day=current_day,
        home_lineup_json=json.dumps(home_lineup),
        away_lineup_json=json.dumps(bot_lineup),
        last_turn_at=datetime.utcnow(),
        status='active',
        current_turn=0,
    )
    db.session.add(match)
    db.session.commit()

    return redirect(url_for('match.view', match_id=match.id))


@match_bp.route('/challenge/<int:team_id>', methods=['POST'])
@login_required
def send_challenge(team_id):
    team = _get_team_or_redirect()
    if not team:
        return redirect(url_for('game.create_team'))

    if get_game_weekday() == 6:
        flash('Le sfide si inviano da lunedì a sabato. La partita si giocherà domenica.', 'warning')
        return redirect(url_for('match.lobby'))

    target = Team.query.get_or_404(team_id)
    current_day = get_game_day_number()
    week_id = get_game_week_id()
    week_monday = _week_monday_game_day()

    # Check no existing challenge between these teams this week
    existing = MatchChallenge.query.filter(
        MatchChallenge.game_day >= week_monday,
        db.or_(
            db.and_(MatchChallenge.challenger_id == team.id,
                    MatchChallenge.challenged_id == team_id),
            db.and_(MatchChallenge.challenger_id == team_id,
                    MatchChallenge.challenged_id == team.id),
        )
    ).first()
    if existing:
        flash('Hai già sfidato questa squadra questa settimana.', 'warning')
        return redirect(url_for('match.lobby'))

    challenge = MatchChallenge(
        challenger_id=team.id,
        challenged_id=team_id,
        game_day=current_day,
        game_week_id=week_id,
        status='pending',
    )
    db.session.add(challenge)
    db.session.commit()
    flash(f'Sfida inviata a {target.name}! Potrete giocare domenica.', 'success')
    return redirect(url_for('match.lobby'))


@match_bp.route('/challenge/<int:challenge_id>/accept', methods=['POST'])
@login_required
def accept_challenge(challenge_id):
    team = _get_team_or_redirect()
    if not team:
        return redirect(url_for('game.create_team'))

    challenge = MatchChallenge.query.get_or_404(challenge_id)
    if challenge.challenged_id != team.id or challenge.status != 'pending':
        abort(403)

    challenge.status = 'accepted'
    db.session.commit()
    flash('Sfida accettata! La partita si giocherà domenica.', 'success')
    return redirect(url_for('match.lobby'))


@match_bp.route('/challenge/<int:challenge_id>/start', methods=['POST'])
@login_required
def start_challenge(challenge_id):
    """Sunday only: create and start a FriendlyMatch from an accepted challenge."""
    team = _get_team_or_redirect()
    if not team:
        return redirect(url_for('game.create_team'))
    if not _require_sunday():
        return redirect(url_for('match.lobby'))

    challenge = MatchChallenge.query.get_or_404(challenge_id)
    if challenge.status != 'accepted' or challenge.match_id is not None:
        flash('Sfida non disponibile.', 'warning')
        return redirect(url_for('match.lobby'))
    if challenge.challenger_id != team.id and challenge.challenged_id != team.id:
        abort(403)

    current_day = get_game_day_number()
    challenger_team = Team.query.get_or_404(challenge.challenger_id)
    challenged_team = Team.query.get_or_404(challenge.challenged_id)

    challenger_formation = TeamFormation.query.filter_by(team_id=challenger_team.id).first()
    challenged_formation = TeamFormation.query.filter_by(team_id=challenged_team.id).first()

    if not challenger_formation or not challenged_formation:
        flash('Una delle squadre non ha una formazione salvata.', 'danger')
        return redirect(url_for('match.lobby'))

    from app.utils.match_engine import build_home_lineup

    home_lineup = build_home_lineup(challenger_team, challenger_formation)
    away_lineup = build_home_lineup(challenged_team, challenged_formation)

    match = FriendlyMatch(
        home_team_id=challenger_team.id,
        away_team_id=challenged_team.id,
        game_day=current_day,
        home_lineup_json=json.dumps(home_lineup),
        away_lineup_json=json.dumps(away_lineup),
        last_turn_at=datetime.utcnow(),
        status='active',
        current_turn=0,
    )
    db.session.add(match)
    db.session.flush()

    challenge.match_id = match.id
    db.session.commit()

    return redirect(url_for('match.view', match_id=match.id))


@match_bp.route('/challenge/<int:challenge_id>/reject', methods=['POST'])
@login_required
def reject_challenge(challenge_id):
    team = _get_team_or_redirect()
    if not team:
        return redirect(url_for('game.create_team'))

    challenge = MatchChallenge.query.get_or_404(challenge_id)
    if challenge.challenged_id != team.id or challenge.status not in ('pending', 'accepted'):
        abort(403)

    challenge.status = 'rejected'
    db.session.commit()
    flash('Sfida rifiutata.', 'info')
    return redirect(url_for('match.lobby'))


@match_bp.route('/<int:match_id>')
@login_required
def view(match_id):
    team = _get_team_or_redirect()
    if not team:
        return redirect(url_for('game.create_team'))

    match = FriendlyMatch.query.get_or_404(match_id)

    # Verify this user's team is involved
    if match.home_team_id != team.id and match.away_team_id != team.id:
        abort(403)

    is_home = (match.home_team_id == team.id)
    TURN_SECONDS = TURN_DURATION

    # Advance turn if needed
    if match.status == 'active':
        if match.last_turn_at is not None:
            next_turn_time = match.last_turn_at + timedelta(seconds=TURN_SECONDS)
            if datetime.utcnow() >= next_turn_time:
                from app.utils.match_engine import process_turn
                # Home-field injury reduction always uses the HOME team's ground stars,
                # independent of which participant triggers the turn.
                home_ground = match.home_team.facility_ground if match.home_team else 0
                process_turn(match, home_ground)
                db.session.commit()

    # Parse data
    home_lineup = json.loads(match.home_lineup_json or '{}')
    away_lineup = json.loads(match.away_lineup_json or '{}')
    turns = json.loads(match.turns_json or '[]')

    my_lineup = home_lineup if is_home else away_lineup
    opp_lineup = away_lineup if is_home else home_lineup

    # Seconds until next turn
    if match.last_turn_at and match.status == 'active':
        delta = (match.last_turn_at + timedelta(seconds=TURN_SECONDS) - datetime.utcnow()).total_seconds()
        seconds_until_next_turn = max(0, int(delta))
    else:
        seconds_until_next_turn = 0

    # Determine opponent name
    if match.away_team_id is None:
        opp_name = 'Squadra del Bar'
    else:
        opp_team = match.away_team if is_home else match.home_team
        opp_name = opp_team.name if opp_team else 'Avversario'

    home_team_name = match.home_team.name if match.home_team else 'Casa'
    away_team_name = ('Squadra del Bar' if match.away_team_id is None
                      else (match.away_team.name if match.away_team else 'Ospite'))

    return render_template(
        'match/match.html',
        match=match,
        team=team,
        is_home=is_home,
        my_lineup=my_lineup,
        opp_lineup=opp_lineup,
        opp_name=opp_name,
        home_team_name=home_team_name,
        away_team_name=away_team_name,
        turns=turns,
        seconds_until_next_turn=seconds_until_next_turn,
        TURN_SECONDS=TURN_SECONDS,
    )


@match_bp.route('/<int:match_id>/sub', methods=['POST'])
@login_required
def substitute(match_id):
    team = _get_team_or_redirect()
    if not team:
        return redirect(url_for('game.create_team'))

    match = FriendlyMatch.query.get_or_404(match_id)

    # Either participating team can manage its own lineup
    if team.id not in (match.home_team_id, match.away_team_id):
        abort(403)
    if match.status != 'active':
        flash('La partita non è in corso.', 'warning')
        return redirect(url_for('match.view', match_id=match.id))

    is_home = (match.home_team_id == team.id)
    subs_field = 'home_pending_subs_json' if is_home else 'away_pending_subs_json'

    try:
        out_id = int(request.form.get('out_id', 0))
        in_id = int(request.form.get('in_id', 0))
    except (ValueError, TypeError):
        flash('Sostituzione non valida.', 'danger')
        return redirect(url_for('match.view', match_id=match.id))

    if not out_id or not in_id:
        flash('Seleziona un giocatore da sostituire e uno dalla panchina.', 'warning')
        return redirect(url_for('match.view', match_id=match.id))

    subs = json.loads(getattr(match, subs_field) or '{}')
    if 'swap' not in subs:
        subs['swap'] = []
    subs['swap'].append({'out_id': out_id, 'in_id': in_id})
    setattr(match, subs_field, json.dumps(subs))
    db.session.commit()

    flash('Sostituzione programmata per il prossimo turno.', 'success')
    return redirect(url_for('match.view', match_id=match.id))


@match_bp.route('/<int:match_id>/roles', methods=['POST'])
@login_required
def change_roles(match_id):
    team = _get_team_or_redirect()
    if not team:
        return redirect(url_for('game.create_team'))

    match = FriendlyMatch.query.get_or_404(match_id)

    if team.id not in (match.home_team_id, match.away_team_id):
        abort(403)
    if match.status != 'active':
        flash('La partita non è in corso.', 'warning')
        return redirect(url_for('match.view', match_id=match.id))

    is_home = (match.home_team_id == team.id)
    subs_field = 'home_pending_subs_json' if is_home else 'away_pending_subs_json'

    valid_roles = {'goalkeeper', 'defender', 'attacker'}
    role_changes = {}
    for key, value in request.form.items():
        if key.startswith('role_') and value in valid_roles:
            pid_str = key[len('role_'):]
            role_changes[pid_str] = value

    if role_changes:
        subs = json.loads(getattr(match, subs_field) or '{}')
        subs['role_changes'] = role_changes
        setattr(match, subs_field, json.dumps(subs))
        db.session.commit()
        flash('Cambi di ruolo programmati per il prossimo turno.', 'success')

    return redirect(url_for('match.view', match_id=match.id))
