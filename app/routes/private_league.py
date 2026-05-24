"""Routes for the private league system."""
import json
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.private_league import (
    PrivateLeague, PrivateLeagueSeason, PrivateLeagueMembership, PrivateLeagueMatch,
)
from app.models.game import Loan
from app.utils import ledger
from app.utils.gameclock import get_game_day_number, get_game_week_id, game_day_to_date
from app.utils.league_engine import (
    LEAGUE_CREATION_COST, LEAGUE_LOAN_PRINCIPAL, LEAGUE_LOAN_TOTAL_DUE,
    LEAGUE_LOAN_WEEKLY_PAYMENT, LEAGUE_LOAN_WEEKS, MIN_TEAMS, MAX_CAPACITY,
    ENTRY_FEE, PERMANENCE_FEE, create_forming_season, start_season, get_standings,
    can_owner_exclude,
)

league_bp = Blueprint('league', __name__)

MAX_LEAGUES_AS_MEMBER = 3


def _fmt_m(amount):
    """Format a float as M (millions) for display."""
    return f'{amount / 1_000_000:.1f}M'


def _active_membership_count(team):
    """Count how many leagues this team is currently active in."""
    return (PrivateLeagueMembership.query
            .join(PrivateLeagueSeason)
            .filter(
                PrivateLeagueMembership.team_id == team.id,
                PrivateLeagueMembership.status == 'active',
                PrivateLeagueSeason.status.in_(['forming', 'active']),
            ).count())


# ── Index ─────────────────────────────────────────────────────────────────────

@league_bp.route('/')
@login_required
def index():
    team = current_user.team
    if not team:
        flash('Devi avere una squadra per accedere alle leghe.', 'warning')
        return redirect(url_for('game.dashboard'))

    all_leagues = PrivateLeague.query.order_by(PrivateLeague.created_at.desc()).all()

    # Enrich each league with current_season info + estimated prize pool
    league_data = []
    for lg in all_leagues:
        s = lg.current_season
        count = (PrivateLeagueMembership.query
                 .filter_by(season_id=s.id if s else -1, status='active').count()) if s else 0

        # Montepremi
        if s is None:
            prize_pool = 0.0
            prize_is_estimate = False
        elif s.status == 'forming':
            # Solo quote già impegnate; sponsor non ancora calcolato
            prize_pool = (ENTRY_FEE + PERMANENCE_FEE) * count
            prize_is_estimate = True        # sarà più alto (+ sponsor)
        else:
            prize_pool = s.total_budget
            prize_is_estimate = False

        league_data.append({
            'league': lg,
            'season': s,
            'member_count': count,
            'prize_pool': prize_pool,
            'prize_is_estimate': prize_is_estimate,
        })

    my_mems = (PrivateLeagueMembership.query
               .join(PrivateLeagueSeason)
               .filter(
                   PrivateLeagueMembership.team_id == team.id,
                   PrivateLeagueSeason.status.in_(['forming', 'active']),
               ).all())

    can_create = (
        current_user.owned_league is None
        and _active_membership_count(team) < MAX_LEAGUES_AS_MEMBER
    )

    return render_template('private_league/index.html',
                           league_data=league_data,
                           my_mems=my_mems,
                           can_create=can_create,
                           fmt_m=_fmt_m)


# ── Create ────────────────────────────────────────────────────────────────────

@league_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    team = current_user.team
    if not team:
        flash('Devi avere una squadra.', 'warning')
        return redirect(url_for('game.dashboard'))

    if current_user.owned_league:
        flash('Sei già proprietario di una lega privata.', 'danger')
        return redirect(url_for('league.index'))

    if _active_membership_count(team) >= MAX_LEAGUES_AS_MEMBER:
        flash(f'Puoi partecipare a massimo {MAX_LEAGUES_AS_MEMBER} leghe contemporaneamente.', 'danger')
        return redirect(url_for('league.index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        payment = request.form.get('payment', 'direct')

        if not name or len(name) < 3 or len(name) > 100:
            flash('Nome lega: tra 3 e 100 caratteri.', 'danger')
            return redirect(url_for('league.create'))

        if PrivateLeague.query.filter_by(name=name).first():
            flash('Nome già utilizzato da un\'altra lega.', 'danger')
            return redirect(url_for('league.create'))

        # Count active non-excluded loans to enforce max 3 rule (reuse existing limits)
        active_loans = Loan.query.filter_by(team_id=team.id, is_active=True).count()

        if payment == 'direct':
            if team.budget < LEAGUE_CREATION_COST:
                flash(f'Budget insufficiente. Servono {_fmt_m(LEAGUE_CREATION_COST)}.', 'danger')
                return redirect(url_for('league.create'))
            ledger.record(team, -LEAGUE_CREATION_COST, ledger.CAT_LEAGUE_ENTRY,
                          f'Creazione Lega Privata: {name}')
            loan_obj = None
        else:
            # Special federation loan — only regular loans count toward the cap
            regular_loan_count = Loan.query.filter(
                Loan.team_id == team.id,
                Loan.is_active == True,
                Loan.loan_type != 'league_creation',
            ).count()
            if regular_loan_count >= 3:
                flash('Hai già 3 prestiti regolari attivi. Non puoi prenderne un altro.', 'danger')
                return redirect(url_for('league.create'))
            loan_obj = Loan(
                team_id=team.id,
                loan_type='league_creation',
                principal=LEAGUE_LOAN_PRINCIPAL,
                total_due=LEAGUE_LOAN_TOTAL_DUE,
                weekly_payment=LEAGUE_LOAN_WEEKLY_PAYMENT,
                weeks_total=LEAGUE_LOAN_WEEKS,
                is_active=True,
                last_paid_week_id=get_game_week_id(),  # prima rata la prossima settimana
            )
            db.session.add(loan_obj)
            db.session.flush()
            # Loan disbursed then immediately used for creation: net zero on team budget
            ledger.record(team, LEAGUE_LOAN_PRINCIPAL, ledger.CAT_LOAN_IN,
                          f'Prestito Speciale Federazione – Lega: {name}')
            ledger.record(team, -LEAGUE_CREATION_COST, ledger.CAT_LEAGUE_ENTRY,
                          f'Creazione Lega Privata (via prestito): {name}')

        league = PrivateLeague(
            name=name,
            owner_id=current_user.id,
            capacity=4,
            loan_id=loan_obj.id if loan_obj else None,
        )
        db.session.add(league)
        db.session.flush()

        # Owner auto-joins the first forming season
        season = create_forming_season(league)
        db.session.add(PrivateLeagueMembership(
            league_id=league.id,
            season_id=season.id,
            team_id=team.id,
        ))

        db.session.commit()
        flash(f'Lega "{name}" creata! Ora cerca altri manager da far iscrivere.', 'success')
        return redirect(url_for('league.detail', league_id=league.id))

    return render_template('private_league/create.html',
                           cost=_fmt_m(LEAGUE_CREATION_COST),
                           loan_weekly=_fmt_m(LEAGUE_LOAN_WEEKLY_PAYMENT),
                           loan_weeks=LEAGUE_LOAN_WEEKS,
                           loan_total=_fmt_m(LEAGUE_LOAN_TOTAL_DUE),
                           team_budget=_fmt_m(team.budget))


# ── Detail ────────────────────────────────────────────────────────────────────

@league_bp.route('/<int:league_id>')
@login_required
def detail(league_id):
    team = current_user.team
    league = PrivateLeague.query.get_or_404(league_id)
    season = league.current_season

    memberships = []
    standings = []
    my_mem = None

    if season:
        memberships = PrivateLeagueMembership.query.filter_by(
            season_id=season.id).all()
        standings = get_standings(season) if season.status == 'active' else memberships
        my_mem = next((m for m in memberships if m.team_id == (team.id if team else -1)), None)

    is_owner = (league.owner_id == current_user.id)
    current_day = get_game_day_number()

    # Can join?
    can_join = (
        team is not None
        and season is not None
        and season.status == 'forming'
        and my_mem is None
        and _active_membership_count(team) < MAX_LEAGUES_AS_MEMBER
        and len(memberships) < league.capacity
    )

    can_start = (
        is_owner
        and season is not None
        and season.status == 'forming'
        and len(memberships) >= MIN_TEAMS
    )

    # Kickable teams (owner only, active season, rules enforced)
    kickable_ids = set()
    if is_owner and season and season.status == 'active':
        for m in memberships:
            if m.team_id == team.id if team else True:
                continue
            ok, _ = can_owner_exclude(season, m)
            if ok:
                kickable_ids.add(m.team_id)

    # Format match days
    def fmt_day(d):
        if d is None:
            return '—'
        from app.utils.gameclock import WEEKDAY_IT, MONTH_IT
        dt = game_day_to_date(d)
        return f'{WEEKDAY_IT[dt.weekday()]} {dt.day}/{dt.month}/{dt.year}'

    # Montepremi breakdown per la pagina dettaglio
    n_members = len([m for m in memberships if m.status == 'active'])
    if season and season.status == 'active':
        prize_fees = (ENTRY_FEE + PERMANENCE_FEE) * season.num_teams
        prize_sponsor = season.sponsor_amount
        prize_total = season.total_budget
        prize_is_estimate = False
    elif season and season.status == 'forming':
        prize_fees = (ENTRY_FEE + PERMANENCE_FEE) * n_members
        prize_sponsor = None        # non ancora calcolato
        prize_total = prize_fees    # minimo stimato (senza sponsor)
        prize_is_estimate = True
    else:
        prize_fees = prize_sponsor = prize_total = None
        prize_is_estimate = False

    return render_template('private_league/detail.html',
                           league=league,
                           season=season,
                           memberships=memberships,
                           standings=standings,
                           my_mem=my_mem,
                           is_owner=is_owner,
                           can_join=can_join,
                           can_start=can_start,
                           kickable_ids=kickable_ids,
                           current_day=current_day,
                           fmt_m=_fmt_m,
                           fmt_day=fmt_day,
                           min_teams=MIN_TEAMS,
                           entry_fee=_fmt_m(ENTRY_FEE),
                           perm_fee=_fmt_m(PERMANENCE_FEE),
                           prize_total=prize_total,
                           prize_fees=prize_fees,
                           prize_sponsor=prize_sponsor,
                           prize_is_estimate=prize_is_estimate)


# ── Join ──────────────────────────────────────────────────────────────────────

@league_bp.route('/<int:league_id>/join', methods=['POST'])
@login_required
def join(league_id):
    team = current_user.team
    if not team:
        flash('Devi avere una squadra.', 'warning')
        return redirect(url_for('league.index'))

    league = PrivateLeague.query.get_or_404(league_id)
    season = league.current_season

    if not season or season.status != 'forming':
        flash('La lega non è aperta alle iscrizioni.', 'danger')
        return redirect(url_for('league.detail', league_id=league_id))

    existing = PrivateLeagueMembership.query.filter_by(
        season_id=season.id, team_id=team.id).first()
    if existing:
        flash('Sei già iscritto a questa lega.', 'warning')
        return redirect(url_for('league.detail', league_id=league_id))

    count = PrivateLeagueMembership.query.filter_by(
        season_id=season.id, status='active').count()
    if count >= league.capacity:
        flash('La lega è al completo.', 'danger')
        return redirect(url_for('league.detail', league_id=league_id))

    if _active_membership_count(team) >= MAX_LEAGUES_AS_MEMBER:
        flash(f'Sei già in {MAX_LEAGUES_AS_MEMBER} leghe. Limite massimo raggiunto.', 'danger')
        return redirect(url_for('league.detail', league_id=league_id))

    db.session.add(PrivateLeagueMembership(
        league_id=league.id,
        season_id=season.id,
        team_id=team.id,
    ))
    db.session.commit()
    flash(f'Iscritto alla lega "{league.name}"!', 'success')
    return redirect(url_for('league.detail', league_id=league_id))


# ── Leave (forming only) ──────────────────────────────────────────────────────

@league_bp.route('/<int:league_id>/leave', methods=['POST'])
@login_required
def leave(league_id):
    team = current_user.team
    if not team:
        return redirect(url_for('league.index'))

    league = PrivateLeague.query.get_or_404(league_id)
    season = league.current_season

    if not season or season.status != 'forming':
        flash('Non puoi uscire da una stagione già avviata.', 'danger')
        return redirect(url_for('league.detail', league_id=league_id))

    if league.owner_id == current_user.id:
        flash('Il proprietario non può lasciare la propria lega.', 'danger')
        return redirect(url_for('league.detail', league_id=league_id))

    mem = PrivateLeagueMembership.query.filter_by(
        season_id=season.id, team_id=team.id).first()
    if mem:
        db.session.delete(mem)
        db.session.commit()
        flash('Hai abbandonato la lega.', 'info')
    return redirect(url_for('league.detail', league_id=league_id))


# ── Start season (owner) ──────────────────────────────────────────────────────

@league_bp.route('/<int:league_id>/start', methods=['POST'])
@login_required
def start(league_id):
    league = PrivateLeague.query.get_or_404(league_id)
    if league.owner_id != current_user.id:
        flash('Solo il proprietario può avviare la stagione.', 'danger')
        return redirect(url_for('league.detail', league_id=league_id))

    season, err = start_season(league)
    if err:
        flash(err, 'danger')
    else:
        from app.utils.gameclock import game_day_to_date
        end_dt = game_day_to_date(season.end_game_day)
        flash(f'Stagione {season.season_number} avviata! '
              f'{season.num_teams} squadre, {season.num_teams} settimane. '
              f'Fine prevista: {end_dt.strftime("%d/%m/%Y")}.', 'success')
    return redirect(url_for('league.detail', league_id=league_id))


# ── Kick (owner manual exclusion) ────────────────────────────────────────────

@league_bp.route('/<int:league_id>/kick/<int:team_id>', methods=['POST'])
@login_required
def kick(league_id, team_id):
    league = PrivateLeague.query.get_or_404(league_id)
    if league.owner_id != current_user.id:
        flash('Solo il proprietario può escludere squadre.', 'danger')
        return redirect(url_for('league.detail', league_id=league_id))

    season = league.current_season
    if not season or season.status != 'active':
        flash('Operazione disponibile solo durante una stagione attiva.', 'danger')
        return redirect(url_for('league.detail', league_id=league_id))

    mem = PrivateLeagueMembership.query.filter_by(
        season_id=season.id, team_id=team_id).first_or_404()

    allowed, reason = can_owner_exclude(season, mem)
    if not allowed:
        flash(f'Esclusione non consentita: {reason}', 'danger')
        return redirect(url_for('league.detail', league_id=league_id))

    mem.status = 'excluded_owner'
    db.session.commit()
    flash(f'Squadra "{mem.team.name}" esclusa dalla stagione corrente.', 'warning')
    return redirect(url_for('league.detail', league_id=league_id))


# ── Calendar ──────────────────────────────────────────────────────────────────

@league_bp.route('/<int:league_id>/calendar')
@login_required
def calendar(league_id):
    league = PrivateLeague.query.get_or_404(league_id)
    season = league.current_season or league.last_completed_season
    if not season:
        flash('Nessuna stagione disponibile.', 'warning')
        return redirect(url_for('league.detail', league_id=league_id))

    matches = (PrivateLeagueMatch.query
               .filter_by(season_id=season.id)
               .order_by(PrivateLeagueMatch.scheduled_game_day,
                         PrivateLeagueMatch.round_number)
               .all())

    current_day = get_game_day_number()
    team = current_user.team

    def fmt_day(d):
        if d is None:
            return '—'
        from app.utils.gameclock import WEEKDAY_IT
        dt = game_day_to_date(d)
        return f'{WEEKDAY_IT[dt.weekday()]} {dt.day}/{dt.month}/{dt.year}'

    return render_template('private_league/calendar.html',
                           league=league,
                           season=season,
                           matches=matches,
                           current_day=current_day,
                           my_team_id=team.id if team else None,
                           fmt_day=fmt_day)


# ── Match detail ──────────────────────────────────────────────────────────────

@league_bp.route('/<int:league_id>/match/<int:match_id>')
@login_required
def match_detail(league_id, match_id):
    league = PrivateLeague.query.get_or_404(league_id)
    # Verify match belongs to this league (via its season)
    match = (PrivateLeagueMatch.query
             .join(PrivateLeagueSeason)
             .filter(PrivateLeagueMatch.id == match_id,
                     PrivateLeagueSeason.league_id == league_id)
             .first_or_404())

    turns = json.loads(match.turns_json or '[]')
    injuries = json.loads(match.injuries_json or '[]')

    def fmt_day(d):
        if d is None:
            return '—'
        from app.utils.gameclock import WEEKDAY_IT
        dt = game_day_to_date(d)
        return f'{WEEKDAY_IT[dt.weekday()]} {dt.day}/{dt.month}/{dt.year}'

    return render_template('private_league/match.html',
                           league=league,
                           match=match,
                           turns=turns,
                           injuries=injuries,
                           fmt_day=fmt_day)
