import random
import random as _random
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.team import Team, Player
from app.models.game import TeamWeeklyOffer, TrainingRecord, SponsorOffer, ActiveSponsor, FreeAgentListing, FreeAgentBid, Loan, Investment
from app.utils.gameclock import (
    get_game_week_id, get_game_weekday, get_game_day_number,
    format_game_date, is_training_day, is_sponsor_day, get_game_month_id,
    get_prev_game_week_id, get_next_game_week_id, get_training_session_day,
)
from app.utils.generators import (
    generate_market_offer_data, generate_sponsor_offer_data,
)

events_bp = Blueprint('events', __name__)

SKILLS = ['porta', 'difesa', 'attacco', 'resistenza']
SKILL_LABELS = {'porta': 'Porta', 'difesa': 'Difesa', 'attacco': 'Attacco', 'resistenza': 'Resistenza'}
MAX_SECONDARY = 2
_FACILITY_ATTRS = ['facility_training', 'facility_stream', 'facility_locker', 'facility_ground']

MAX_PHYSIO = 20
MAX_HEALTH = 5
MAX_CYBER  = 5
WELLNESS_PURCHASE_WEEKDAYS = (2, 3, 4, 5, 6)  # Wed–Sun

_SHOE_SPONSOR_NAMES = [
    'HyperStride Technologies', 'NeoFoot Labs', 'KinetiX Sport', 'VelocityGear',
    'ArcFlex Systems', 'BioStep Pro', 'FutureSole Inc.', 'TitanKick Corp.',
    'PulseTrack Athletics', 'OmegaBoot Tech', 'SkyFoot Dynamics', 'XcelRun Industries',
    'ApexCleat Solutions', 'SwiftTread Group', 'EliteStride Partners',
]

LOAN_TIERS = {
    'green':  {'multiplier': 1_000_000, 'rate': 0.01, 'label': 'Green',  'color': 'var(--success)'},
    'yellow': {'multiplier': 2_000_000, 'rate': 0.03, 'label': 'Yellow', 'color': '#ffc800'},
    'red':    {'multiplier': 5_000_000, 'rate': 0.09, 'label': 'Red',    'color': 'var(--danger)'},
    'black':  {'multiplier':10_000_000, 'rate': 0.20, 'label': 'Black',  'color': '#888'},
}
MAX_LOANS = 3
FEDERATION_TARGET = 2_000_000   # bring budget up to this when emergency loan fires

import random as _random
BOND_TYPES = {
    'white': {
        'label': 'White', 'color': '#d0d0d0',
        'cost': 10_000_000, 'payout': 10_100_000, 'weeks': 10,
        'max_count': 10, 'degrade_chance': 0, 'degrade_to': None,
    },
    'green': {
        'label': 'Green', 'color': 'var(--success)',
        'cost': 25_000_000, 'payout': 20_500_000, 'weeks': 25,
        'max_count': 10, 'degrade_chance': 0, 'degrade_to': None,
    },
    'yellow': {
        'label': 'Yellow', 'color': '#ffc800',
        'cost': 50_000_000, 'payout': 55_000_000, 'weeks': 50,
        'max_count': 10, 'degrade_chance': 0.01, 'degrade_to': 'green',
    },
    'red': {
        'label': 'Red', 'color': 'var(--danger)',
        'cost': 50_000_000, 'payout': 60_000_000, 'weeks': 50,
        'max_count': 10, 'degrade_chance': 0.05, 'degrade_to': 'green',
    },
    'black': {
        'label': 'Black', 'color': '#999',
        'cost': 100_000_000, 'payout': 150_000_000, 'weeks': 50,
        'max_count': 5, 'degrade_chance': 0.25, 'degrade_to': 'white',
    },
}
MAX_INVESTMENTS = 20


def _require_team():
    if not current_user.team:
        flash('Devi prima creare una squadra.', 'warning')
        return redirect(url_for('game.create_team'))
    return None


def _process_scouting_payment(team):
    """Every new week (on first market visit), charge 1M€ if recurring scouting is enabled."""
    if not team.scouting_enabled:
        return
    current_week = get_game_week_id()
    # paid_week_id is already set to current week or next week — only charge when a new week has arrived
    if team.scouting_paid_week_id >= current_week:
        return
    cost = 1_000_000
    if team.budget >= cost:
        team.budget -= cost
        team.scouting_paid_week_id = current_week
        db.session.commit()
        flash('💰 Scouting avanzato: €1.000.000 addebitati per questa settimana.', 'info')
    else:
        team.scouting_enabled = False
        db.session.commit()
        flash('⚠️ Scouting avanzato disattivato: budget insufficiente per il pagamento settimanale.', 'warning')


def _process_sponsor_payments(team):
    """Credit unpaid sponsor weeks to team budget."""
    current_week = get_game_week_id()
    sponsors = ActiveSponsor.query.filter_by(team_id=team.id).all()
    paid_any = False
    for sp in sponsors:
        if sp.remaining_weeks <= 0:
            db.session.delete(sp)
            paid_any = True
            continue
        weeks_due = max(0, current_week - sp.last_paid_week_id)
        if weeks_due > 0:
            to_pay = min(weeks_due, sp.remaining_weeks)
            rate = sp.weekly_amount if sp.type == 'main' else sp.weekly_amount * 0.3
            team.budget += rate * to_pay
            sp.remaining_weeks -= to_pay
            sp.last_paid_week_id = current_week
            paid_any = True
            if sp.remaining_weeks <= 0:
                db.session.delete(sp)
    if paid_any:
        db.session.commit()


def _process_stadium_degradation(team):
    """On first visit of a new game month, randomly reduce 2 facilities by 1 star."""
    current_month = get_game_month_id()
    if team.last_degraded_month >= current_month:
        return
    eligible = [f for f in _FACILITY_ATTRS if getattr(team, f) > 0]
    if eligible:
        for f in random.sample(eligible, min(2, len(eligible))):
            setattr(team, f, getattr(team, f) - 1)
    team.last_degraded_month = current_month
    db.session.commit()


def _process_loan_payments(team):
    """Deduct all overdue weekly loan installments (catches up missed weeks)."""
    current_week = get_game_week_id()
    active_loans = Loan.query.filter_by(team_id=team.id, is_active=True).all()
    paid_any = False
    for loan in active_loans:
        weeks_overdue = current_week - loan.last_paid_week_id
        if weeks_overdue <= 0:
            continue
        # Cap to remaining installments
        remaining = loan.weeks_total - loan.weeks_paid
        installments_due = min(weeks_overdue, remaining)
        team.budget -= loan.weekly_payment * installments_due
        loan.weeks_paid += installments_due
        loan.last_paid_week_id = current_week
        if loan.weeks_paid >= loan.weeks_total:
            loan.is_active = False
        paid_any = True
    if paid_any:
        db.session.commit()
    # Emergency federation loan if budget went negative
    _check_federation_loan(team)


def _check_federation_loan(team):
    """If budget < 0, auto-issue a federation emergency loan to bring to +2M.
    Tracks consecutive weeks with federation help; at 25 weeks triggers a donation + skill penalty."""
    if team.budget >= 0:
        # Team healthy: reset streak
        if team.federation_loan_streak > 0:
            team.federation_loan_streak = 0
            db.session.commit()
        return
    existing = Loan.query.filter_by(team_id=team.id, loan_type='federation', is_active=True).first()
    if existing:
        return
    amount = FEDERATION_TARGET - team.budget
    interest = round(amount * 0.01, 2)
    total_due = round(amount + interest, 2)
    loan = Loan(
        team_id=team.id,
        loan_type='federation',
        principal=amount,
        total_due=total_due,
        weekly_payment=total_due,
        weeks_total=1,
        weeks_paid=0,
        last_paid_week_id=get_game_week_id(),
    )
    team.budget += amount
    team.federation_loan_streak += 1
    db.session.add(loan)

    if team.federation_loan_streak >= 25:
        # Federazione dona 50M ma i giocatori devono fare la "lunga promozione"
        team.budget += 50_000_000
        team.federation_loan_streak = 0
        for player in team.players.all():
            player.porta       = round(player.porta       * 0.5, 2)
            player.difesa      = round(player.difesa      * 0.5, 2)
            player.attacco     = round(player.attacco     * 0.5, 2)
            player.resistenza  = round(player.resistenza  * 0.5, 2)
        db.session.commit()
        flash('🏛️ La Federazione ha donato €50M — ma la "Lunga Promozione" ha dimezzato tutte le skill dei giocatori.', 'warning')
    else:
        db.session.commit()
        streak_left = 25 - team.federation_loan_streak
        flash(
            f'🚨 Aiuto dalla Federazione attivato: €{amount/1_000_000:.2f}M '
            f'(+1% = €{total_due/1_000_000:.2f}M da restituire). '
            f'Crisi finanziaria: settimana {team.federation_loan_streak}/25 '
            f'(mancano {streak_left} alla donazione federale).',
            'warning'
        )


def _process_investments(team):
    """Pay out matured investments."""
    current_week = get_game_week_id()
    matured = Investment.query.filter_by(team_id=team.id, is_active=True).filter(
        Investment.game_week_id_maturity <= current_week
    ).all()
    for inv in matured:
        team.budget += inv.payout
        inv.is_active = False
        flash(
            f'📈 Cedola {BOND_TYPES[inv.bond_type]["label"]} maturata! '
            f'+€{inv.payout/1_000_000:.2f}M accreditati.',
            'success'
        )
    if matured:
        db.session.commit()


# ─── MARKET ────────────────────────────────────────────────────────────────────

@events_bp.route('/market')
@login_required
def market():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    _process_sponsor_payments(team)
    _process_scouting_payment(team)
    _process_loan_payments(team)

    week_id = get_game_week_id()
    weekday = get_game_weekday()
    scouting_active = team.scouting_active
    scouting_next_week = team.scouting_pending_next_week
    offer_expired = weekday >= 5   # Sat or Sun: offer no longer purchasable

    # Generate offer once per week (available Mon–Fri only)
    offer = TeamWeeklyOffer.query.filter_by(team_id=team.id, game_week_id=week_id).first()
    if not offer and not offer_expired:
        data = generate_market_offer_data(scouted=scouting_active)
        offer = TeamWeeklyOffer(
            team_id=team.id,
            game_week_id=week_id,
            offer_name=data['name'],
            offer_type=data['type'],
            offer_age=data['age'],
            offer_porta=data['porta'],
            offer_difesa=data['difesa'],
            offer_attacco=data['attacco'],
            offer_resistenza=data['resistenza'],
            offer_avg=data['avg'],
            is_scouted=scouting_active,
            purchased=False,
        )
        db.session.add(offer)
        db.session.commit()

    return render_template('events/market.html',
                           team=team,
                           offer=offer,
                           offer_expired=offer_expired,
                           scouting_active=scouting_active,
                           scouting_next_week=scouting_next_week,
                           game_date=format_game_date(),
                           weekday=weekday,
                           week_id=week_id,
                           skill_labels=SKILL_LABELS)


@events_bp.route('/market/buy', methods=['POST'])
@login_required
def market_buy():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    week_id = get_game_week_id()
    offer = TeamWeeklyOffer.query.filter_by(team_id=team.id, game_week_id=week_id).first_or_404()

    if get_game_weekday() >= 5:
        flash('L\'offerta della settimana è scaduta. Torna lunedì per la nuova offerta.', 'warning')
        return redirect(url_for('events.market'))

    if offer.purchased:
        flash('Hai già acquistato il giocatore di questa settimana.', 'warning')
        return redirect(url_for('events.market'))

    if team.players.count() >= 12:
        flash('Rosa al completo (massimo 12 giocatori).', 'danger')
        return redirect(url_for('events.market'))

    cost = 250_000
    if team.budget < cost:
        flash(f'Budget insufficiente. Costo: €{cost:,.0f}', 'danger')
        return redirect(url_for('events.market'))

    player = Player(
        name=offer.offer_name,
        type=offer.offer_type,
        age=offer.offer_age,
        porta=offer.offer_porta,
        difesa=offer.offer_difesa,
        attacco=offer.offer_attacco,
        resistenza=offer.offer_resistenza,
        is_free_agent=False,
        team_id=team.id,
    )
    db.session.add(player)
    team.budget -= cost
    offer.purchased = True
    db.session.commit()

    type_icon = {'uomo': '👨', 'donna': '👩', 'cyber': '🤖'}.get(offer.offer_type, '')
    if offer.is_scouted:
        flash(
            f'🔮 Giocatore scouting rivelato: {type_icon} {offer.offer_name} '
            f'(media {offer.offer_avg:.2f}) acquistato per €{cost:,.0f}!',
            'success'
        )
    else:
        flash(f'{type_icon} {offer.offer_name} acquistato per €{cost:,.0f}!', 'success')
    return redirect(url_for('game.my_team'))


@events_bp.route('/market/scouting', methods=['POST'])
@login_required
def activate_scouting():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    next_week_id = get_next_game_week_id()
    cost = 1_000_000
    if team.scouting_enabled:
        flash('Scouting già attivo.', 'warning')
        return redirect(url_for('events.market'))
    if team.budget < cost:
        flash('Budget insufficiente per attivare lo scouting (1M€).', 'danger')
        return redirect(url_for('events.market'))
    team.budget -= cost
    team.scouting_paid_week_id = next_week_id
    team.scouting_enabled = True
    db.session.commit()
    flash('Scouting avanzato attivato! Lunedì riceverai un giocatore con media fino a 5.0. Si rinnova automaticamente ogni settimana.', 'success')
    return redirect(url_for('events.market'))


@events_bp.route('/market/scouting/deactivate', methods=['POST'])
@login_required
def deactivate_scouting():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    if not team.scouting_enabled:
        flash('Scouting non attivo.', 'warning')
        return redirect(url_for('events.market'))
    team.scouting_enabled = False
    db.session.commit()
    flash('Scouting avanzato disattivato. Non verranno addebitati ulteriori costi.', 'success')
    return redirect(url_for('events.market'))


# ─── TRAINING ──────────────────────────────────────────────────────────────────

@events_bp.route('/training', methods=['GET', 'POST'])
@login_required
def training():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    _process_sponsor_payments(team)
    _process_loan_payments(team)

    actual_game_day = get_game_day_number()
    session_day = get_training_session_day()   # canonical day for TrainingRecord
    weekday = get_game_weekday()
    is_wednesday_makeup = (weekday == 2)       # Wed = makeup for Tuesday
    regular_training = is_training_day()       # Tue, Wed, Thu
    saturday_slots = team.facility_training if weekday == 5 else 0
    is_saturday_mode = saturday_slots > 0
    training_ok = regular_training or is_saturday_mode

    from app.routes.game import _process_team_freshness
    _process_team_freshness(team)

    players = team.players.all()
    trained_ids = {
        r.player_id for r in
        TrainingRecord.query.filter_by(team_id=team.id, game_day=session_day).all()
    }
    today_records = {
        r.player_id: r for r in
        TrainingRecord.query.filter_by(team_id=team.id, game_day=session_day).all()
    }
    trainable = [p for p in players if p.id not in trained_ids]

    # Formation roles for display
    formation_roles = team.formation.current_roles() if team.formation else {}

    game_day = session_day  # alias used throughout the POST block below

    if request.method == 'POST' and training_ok:
        sessions = []

        if is_saturday_mode and not regular_training:
            # Saturday: collect all players with valid 2-skill selection, cap at saturday_slots
            for p in trainable:
                raw = request.form.getlist(f'skills_{p.id}')
                if len(raw) != 2:
                    continue
                skill1, skill2 = raw[0], raw[1]
                if skill1 not in SKILLS or skill2 not in SKILLS or skill1 == skill2:
                    continue
                sessions.append((p, skill1, skill2, 'p200k'))
            sessions = sessions[:saturday_slots]  # server-side cap
            total_cost = 0.0
        else:
            # Regular Tue/Thu training
            bulk_500k = request.form.get('bulk_500k') == 'on'
            for p in trainable:
                raw = request.form.getlist(f'skills_{p.id}')
                if len(raw) != 2:
                    continue
                skill1, skill2 = raw[0], raw[1]
                if skill1 not in SKILLS or skill2 not in SKILLS or skill1 == skill2:
                    continue
                prem = 'p50k' if bulk_500k else request.form.get(f'prem_{p.id}', 'standard')
                sessions.append((p, skill1, skill2, prem))
            if bulk_500k and sessions:
                total_cost = 500_000.0
            else:
                total_cost = sum(
                    200_000 if prem == 'p200k' else (50_000 if prem == 'p50k' else 0)
                    for _, _, _, prem in sessions
                )

        if not sessions:
            if is_saturday_mode and not regular_training:
                return redirect(url_for('events.training'))   # Saturday: no selection is fine
            flash('Seleziona esattamente 2 skill per almeno un giocatore.', 'warning')
            return redirect(url_for('events.training'))

        if team.budget < total_cost:
            flash(f'Budget insufficiente. Costo sessione: €{total_cost:,.0f}', 'danger')
            return redirect(url_for('events.training'))

        team.budget -= total_cost
        results = []
        is_saturday_post = is_saturday_mode and not regular_training
        for p, skill1, skill2, prem in sessions:
            if prem == 'p200k':
                improved = random.choice([skill1, skill2])
                delta = 0.2 if random.random() < 0.3 else 0.1
            else:
                prob = 0.50 if prem == 'p50k' else 0.20
                if random.random() < prob:
                    improved = random.choice([skill1, skill2])
                    delta = 0.1
                else:
                    improved = None
                    delta = 0.0

            if improved and delta > 0:
                current_val = getattr(p, improved)
                new_val = min(6.5, round(current_val + delta, 1))
                actual = round(new_val - current_val, 1)
                setattr(p, improved, new_val)
            else:
                actual = 0.0

            player_cost = 0 if is_saturday_post else (
                200_000 if prem == 'p200k' else (50_000 if prem == 'p50k' else 0)
            )
            rec = TrainingRecord(
                team_id=team.id, player_id=p.id, game_day=game_day,
                skill1=skill1, skill2=skill2, premium_type=prem,
                skill_improved=improved if actual > 0 else None,
                improvement=actual, cost=player_cost,
            )
            db.session.add(rec)
            # Training reduces freshness
            p.freshness = max(0.0, round(p.freshness - 0.1, 1))
            p.last_freshness_day = actual_game_day
            results.append({'player': p, 'improved': improved, 'delta': actual})

        db.session.commit()
        trained_ids = {r.player_id for r in
                       TrainingRecord.query.filter_by(team_id=team.id, game_day=session_day).all()}
        today_records = {
            r.player_id: r for r in
            TrainingRecord.query.filter_by(team_id=team.id, game_day=session_day).all()
        }
        trainable = [p for p in players if p.id not in trained_ids]
        improved_count = sum(1 for r in results if r['delta'] > 0)
        cost_str = 'GRATUITO (Stadio)' if is_saturday_post else f'€{total_cost:,.0f}'
        flash(f'Allenamento completato! {improved_count}/{len(results)} giocatori migliorati. '
              f'Costo: {cost_str}', 'success')

    return render_template('events/training.html',
                           team=team,
                           players=players,
                           trainable=trainable,
                           today_records=today_records,
                           formation_roles=formation_roles,
                           is_training=regular_training,
                           is_saturday_mode=is_saturday_mode,
                           is_wednesday_makeup=is_wednesday_makeup,
                           saturday_slots=saturday_slots,
                           training_ok=training_ok,
                           game_date=format_game_date(),
                           weekday=weekday,
                           game_day=session_day,
                           skill_labels=SKILL_LABELS)


# ─── SPONSORS ──────────────────────────────────────────────────────────────────

@events_bp.route('/sponsors')
@login_required
def sponsors():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    _process_sponsor_payments(team)
    _process_loan_payments(team)

    week_id = get_game_week_id()
    weekday = get_game_weekday()
    is_friday = is_sponsor_day()
    prev_week_id = get_prev_game_week_id()

    active = ActiveSponsor.query.filter_by(team_id=team.id).all()
    main_sponsor = next((s for s in active if s.type in ('main', 'dark')), None)
    secondary_sponsors = [s for s in active if s.type == 'secondary']

    # Sponsor offer window: generated Friday of week W, valid through Wednesday of week W+1.
    # Mon/Tue/Wed → show previous week's offer; Fri/Sat/Sun → show this week's offer; Thu → none.
    if weekday <= 2:      # Mon, Tue, Wed: previous week's offer still valid
        offer_week = prev_week_id
        offer_window_open = True
    elif weekday == 4:    # Friday: generate and show this week's offer
        offer_week = week_id
        offer_window_open = True
    elif weekday in (5, 6):  # Sat, Sun: this week's offer (generated yesterday/Fri)
        offer_week = week_id
        offer_window_open = True
    else:                 # Thursday: no offer window
        offer_week = None
        offer_window_open = False

    # Generate Friday offer if not yet created
    if is_friday and not SponsorOffer.query.filter_by(team_id=team.id, game_week_id=week_id).first():
        existing_names = {s.sponsor_name for s in active}
        data = generate_sponsor_offer_data(team.top7_avg_skill, existing_names)
        new_offer = SponsorOffer(
            team_id=team.id, game_week_id=week_id,
            sponsor_name=data['name'],
            weekly_amount=data['weekly_amount'],
            duration_weeks=data['duration_weeks'],
        )
        db.session.add(new_offer)
        db.session.commit()

    offer = None
    if offer_week:
        offer = SponsorOffer.query.filter_by(
            team_id=team.id, game_week_id=offer_week, status='pending'
        ).first()

    return render_template('events/sponsors.html',
                           team=team,
                           offer=offer,
                           active=active,
                           main_sponsor=main_sponsor,
                           secondary_sponsors=secondary_sponsors,
                           can_add_main=main_sponsor is None,
                           can_add_secondary=len(secondary_sponsors) < MAX_SECONDARY,
                           is_friday=is_friday,
                           offer_window_open=offer_window_open,
                           game_date=format_game_date(),
                           week_id=week_id,
                           dark_sponsor_available=_dark_sponsor_available(team),
                           dark_sponsor_payout=round(team.top7_avg_skill * 10_000_000, 2),
                           dark_sponsor_weeks_left=_dark_sponsor_cooldown_left(team))


def _dark_sponsor_available(team):
    """Dark sponsor usable once every 200 game weeks (cooldown)."""
    return _dark_sponsor_cooldown_left(team) == 0


def _dark_sponsor_cooldown_left(team):
    """Weeks remaining before dark sponsor can be used again (0 = available)."""
    if team.dark_sponsor_last_week_id == -1:
        return 0
    current_week = get_game_week_id()
    elapsed = current_week - team.dark_sponsor_last_week_id
    return max(0, 200 - elapsed)


_DARK_OUTCOMES = [
    ('none',         15, 'Nessuna conseguenza. Lo sponsor è soddisfatto.'),
    ('player_leave', 20, 'Uno dei tuoi migliori 3 giocatori si è svincolato.'),
    ('fine_50m',     25, 'La Federazione ti ha multato: −€50M.'),
    ('fine_100m',    20, 'La Federazione ti ha multato: −€100M.'),
    ('fine_200m',    15, 'La Federazione ti ha multato: −€200M.'),
    ('lungo',         5, 'Lungo processo federale: −€25M e giocatori a −80% di tutte le skill.'),
]


@events_bp.route('/sponsors/dark', methods=['POST'])
@login_required
def dark_sponsor():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team

    if not _dark_sponsor_available(team):
        flash('Sponsor Oscuro non disponibile.', 'danger')
        return redirect(url_for('events.sponsors'))

    payout = round(team.top7_avg_skill * 10_000_000, 2)
    if payout <= 0:
        flash('La tua squadra non ha forza sufficiente per attirare lo Sponsor Oscuro.', 'danger')
        return redirect(url_for('events.sponsors'))

    team.budget += payout
    current_week = get_game_week_id()
    team.dark_sponsor_last_week_id = current_week

    # Replace/remove any existing main sponsor, install dark one for 5 weeks (cannot remove)
    existing_main = ActiveSponsor.query.filter_by(team_id=team.id, type='main').first()
    if existing_main:
        db.session.delete(existing_main)
    dark_contract = ActiveSponsor(
        team_id=team.id,
        sponsor_name='Sponsor Oscuro',
        weekly_amount=0,
        remaining_weeks=5,
        type='dark',
        last_paid_week_id=current_week,
    )
    db.session.add(dark_contract)

    # Roll outcome
    outcomes, weights, _ = zip(*_DARK_OUTCOMES)
    result = _random.choices(outcomes, weights=weights, k=1)[0]
    desc = next(d for o, _, d in _DARK_OUTCOMES if o == result)

    if result == 'none':
        flash(f'🕶️ Sponsor Oscuro: +€{payout/1_000_000:.2f}M incassati. {desc}', 'success')

    elif result == 'player_leave':
        top3 = sorted(team.players.all(), key=lambda p: p.avg_skill, reverse=True)[:3]
        if top3:
            victim = _random.choice(top3)
            victim.team_id = None
            flash(f'🕶️ Sponsor Oscuro: +€{payout/1_000_000:.2f}M. ⚠️ {victim.name} si è svincolato!', 'warning')
        else:
            flash(f'🕶️ Sponsor Oscuro: +€{payout/1_000_000:.2f}M. {desc}', 'warning')

    elif result == 'fine_50m':
        team.budget -= 50_000_000
        flash(f'🕶️ Sponsor Oscuro: +€{payout/1_000_000:.2f}M. 🚨 {desc}', 'danger')

    elif result == 'fine_100m':
        team.budget -= 100_000_000
        flash(f'🕶️ Sponsor Oscuro: +€{payout/1_000_000:.2f}M. 🚨 {desc}', 'danger')

    elif result == 'fine_200m':
        team.budget -= 200_000_000
        flash(f'🕶️ Sponsor Oscuro: +€{payout/1_000_000:.2f}M. 🚨 {desc}', 'danger')

    elif result == 'lungo':
        team.budget -= 25_000_000
        for player in team.players.all():
            player.porta      = round(player.porta      * 0.2, 2)
            player.difesa     = round(player.difesa     * 0.2, 2)
            player.attacco    = round(player.attacco    * 0.2, 2)
            player.resistenza = round(player.resistenza * 0.2, 2)
        flash(f'🕶️ Sponsor Oscuro: +€{payout/1_000_000:.2f}M. ☠️ {desc}', 'danger')

    db.session.commit()
    return redirect(url_for('events.sponsors'))


@events_bp.route('/sponsors/accept/<int:offer_id>/<slot>', methods=['POST'])
@login_required
def sponsor_accept(offer_id, slot):
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    offer = SponsorOffer.query.get_or_404(offer_id)
    if offer.team_id != team.id or offer.status != 'pending':
        flash('Offerta non disponibile.', 'danger')
        return redirect(url_for('events.sponsors'))

    active = ActiveSponsor.query.filter_by(team_id=team.id).all()
    main_count = sum(1 for s in active if s.type == 'main')
    sec_count = sum(1 for s in active if s.type == 'secondary')

    if slot == 'main' and main_count >= 1:
        flash('Hai già uno sponsor principale. Rimuovilo prima.', 'danger')
        return redirect(url_for('events.sponsors'))
    if slot == 'secondary' and sec_count >= MAX_SECONDARY:
        flash(f'Hai già {MAX_SECONDARY} sponsor secondari.', 'danger')
        return redirect(url_for('events.sponsors'))

    week_id = get_game_week_id()
    sp = ActiveSponsor(
        team_id=team.id,
        sponsor_name=offer.sponsor_name,
        weekly_amount=offer.weekly_amount,
        remaining_weeks=offer.duration_weeks,
        type=slot,
        last_paid_week_id=week_id,
    )
    db.session.add(sp)
    offer.status = 'accepted'
    db.session.commit()
    rate = offer.weekly_amount if slot == 'main' else offer.weekly_amount * 0.3
    flash(f'Sponsor {offer.sponsor_name} attivato! '
          f'Guadagno: €{rate:,.0f}/settimana per {offer.duration_weeks} settimane.', 'success')
    return redirect(url_for('events.sponsors'))


@events_bp.route('/sponsors/reject/<int:offer_id>', methods=['POST'])
@login_required
def sponsor_reject(offer_id):
    redir = _require_team()
    if redir:
        return redir
    offer = SponsorOffer.query.get_or_404(offer_id)
    if offer.team_id != current_user.team.id:
        flash('Operazione non autorizzata.', 'danger')
        return redirect(url_for('events.sponsors'))
    offer.status = 'rejected'
    db.session.commit()
    flash('Offerta sponsor rifiutata.', 'info')
    return redirect(url_for('events.sponsors'))


@events_bp.route('/sponsors/remove/<int:sponsor_id>', methods=['POST'])
@login_required
def sponsor_remove(sponsor_id):
    redir = _require_team()
    if redir:
        return redir
    sp = ActiveSponsor.query.get_or_404(sponsor_id)
    if sp.team_id != current_user.team.id:
        flash('Operazione non autorizzata.', 'danger')
        return redirect(url_for('events.sponsors'))
    if sp.type in ('dark', 'shoe'):
        flash('Questo sponsor non può essere rimosso.', 'danger')
        return redirect(url_for('events.sponsors'))
    name = sp.sponsor_name
    db.session.delete(sp)
    db.session.commit()
    flash(f'Sponsor {name} rimosso.', 'info')
    return redirect(url_for('events.sponsors'))


@events_bp.route('/sponsors/upgrade/<int:sponsor_id>', methods=['POST'])
@login_required
def sponsor_upgrade(sponsor_id):
    """Upgrade a secondary sponsor to main (only if no main exists)."""
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    sp = ActiveSponsor.query.get_or_404(sponsor_id)
    if sp.team_id != team.id or sp.type != 'secondary':
        flash('Operazione non valida.', 'danger')
        return redirect(url_for('events.sponsors'))
    if ActiveSponsor.query.filter_by(team_id=team.id, type='main').first():
        flash('Rimuovi lo sponsor principale prima di promuovere un secondario.', 'danger')
        return redirect(url_for('events.sponsors'))
    sp.type = 'main'
    db.session.commit()
    flash(f'{sp.sponsor_name} promosso a sponsor principale!', 'success')
    return redirect(url_for('events.sponsors'))


# ─── FREE AGENTS ───────────────────────────────────────────────────────────────

def _listing_current_price(listing, current_day):
    days = max(0, current_day - listing.list_game_day)
    periods = days // 7
    price = listing.base_price * (0.7 ** periods)
    return max(200_000, round(price, -3))


def _process_free_agent_auctions():
    """Resolve closed auction windows and expire listings with no bids."""
    current_day = get_game_day_number()
    changed = False

    # 1. Resolve closed auction windows
    closed_listings = FreeAgentListing.query.filter(
        FreeAgentListing.status == 'active',
        FreeAgentListing.bid_window_end != None,
        FreeAgentListing.bid_window_end < current_day,
    ).all()

    for listing in closed_listings:
        bids = FreeAgentBid.query.filter_by(listing_id=listing.id).order_by(
            FreeAgentBid.amount.desc(), FreeAgentBid.bid_timestamp.asc()
        ).all()

        winner_bid = None
        for bid in bids:
            bidding_team = Team.query.get(bid.team_id)
            if bidding_team and bidding_team.budget >= bid.amount:
                winner_bid = bid
                break

        if winner_bid:
            winner_team = Team.query.get(winner_bid.team_id)
            winner_team.budget -= winner_bid.amount
            # Credit seller
            days_listed = current_day - listing.list_game_day
            seller_pct = 0.75 if days_listed <= 60 else 0.50
            if listing.seller_team_id:
                seller_team = Team.query.get(listing.seller_team_id)
                if seller_team:
                    seller_team.budget += round(winner_bid.amount * seller_pct, -3)
            # Transfer player
            if listing.player_id:
                player = Player.query.get(listing.player_id)
                if player:
                    player.team_id = winner_team.id
                    player.is_free_agent = False
            listing.status = 'sold'
            for bid in bids:
                bid.status = 'won' if bid.id == winner_bid.id else 'lost'
        else:
            # No valid winner — expire and delete player
            if listing.player_id:
                player = Player.query.get(listing.player_id)
                if player:
                    db.session.delete(player)
            listing.player_id = None
            listing.status = 'expired'
            for bid in bids:
                bid.status = 'lost'
        changed = True

    # 2. Expire listings with no bids that have passed their expiry
    expired_listings = FreeAgentListing.query.filter(
        FreeAgentListing.status == 'active',
        FreeAgentListing.expires_game_day <= current_day,
        FreeAgentListing.bid_window_start == None,
    ).all()

    for listing in expired_listings:
        if listing.player_id:
            player = Player.query.get(listing.player_id)
            if player:
                db.session.delete(player)
        listing.player_id = None
        listing.status = 'expired'
        changed = True

    if changed:
        db.session.commit()


@events_bp.route('/free-agents')
@login_required
def free_agents():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    _process_free_agent_auctions()
    _process_sponsor_payments(team)
    _process_loan_payments(team)

    current_day = get_game_day_number()
    listings = FreeAgentListing.query.filter_by(status='active').all()

    enriched = {}
    for listing in listings:
        days = max(0, current_day - listing.list_game_day)
        current_price = _listing_current_price(listing, current_day)
        days_to_next_reduction = 7 - (days % 7)
        days_remaining = listing.expires_game_day - current_day

        if listing.bid_window_end is not None and listing.bid_window_end < current_day:
            auction_status = 'closed'
        elif listing.bid_window_start is not None:
            auction_status = 'open'
        else:
            auction_status = 'no_bids'

        enriched[listing.id] = {
            'current_price': current_price,
            'days_to_next_reduction': days_to_next_reduction,
            'days_remaining': days_remaining,
            'auction_status': auction_status,
        }

    my_bids = {}
    for bid in FreeAgentBid.query.filter_by(team_id=team.id).all():
        my_bids[bid.listing_id] = bid

    return render_template(
        'events/free_agents.html',
        team=team,
        listings=listings,
        enriched=enriched,
        my_bids=my_bids,
        current_day=current_day,
        game_date=format_game_date(),
    )


@events_bp.route('/free-agents/<int:listing_id>/bid', methods=['POST'])
@login_required
def free_agent_bid(listing_id):
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    listing = FreeAgentListing.query.get_or_404(listing_id)

    if listing.status != 'active':
        flash('Questo annuncio non è più attivo.', 'danger')
        return redirect(url_for('events.free_agents'))

    if listing.seller_team_id == team.id:
        flash('Non puoi fare un\'offerta sul tuo stesso giocatore.', 'danger')
        return redirect(url_for('events.free_agents'))

    if team.players.count() >= 12:
        flash('Rosa al completo (massimo 12 giocatori).', 'danger')
        return redirect(url_for('events.free_agents'))

    current_day = get_game_day_number()

    if listing.bid_window_end is not None and listing.bid_window_end < current_day:
        flash('La finestra d\'asta per questo giocatore è già chiusa.', 'danger')
        return redirect(url_for('events.free_agents'))

    existing_bid = FreeAgentBid.query.filter_by(listing_id=listing_id, team_id=team.id).first()
    if existing_bid:
        flash('Hai già fatto un\'offerta per questo giocatore.', 'warning')
        return redirect(url_for('events.free_agents'))

    try:
        amount = float(request.form.get('amount', 0))
    except (ValueError, TypeError):
        flash('Importo non valido.', 'danger')
        return redirect(url_for('events.free_agents'))

    min_price = _listing_current_price(listing, current_day)
    if amount < min_price:
        flash(f'L\'offerta deve essere almeno €{min_price:,.0f}.', 'danger')
        return redirect(url_for('events.free_agents'))

    if amount > team.budget:
        flash('Budget insufficiente per questa offerta.', 'danger')
        return redirect(url_for('events.free_agents'))

    bid = FreeAgentBid(
        listing_id=listing_id,
        team_id=team.id,
        amount=amount,
        bid_game_day=current_day,
    )
    db.session.add(bid)

    if listing.bid_window_start is None:
        listing.bid_window_start = current_day
        listing.bid_window_end = current_day + 7

    db.session.commit()
    flash(f'Offerta di €{amount:,.0f} inviata con successo!', 'success')
    return redirect(url_for('events.free_agents'))


# ─── FINANCE ───────────────────────────────────────────────────────────────────

@events_bp.route('/finance')
@login_required
def finance():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    _process_sponsor_payments(team)
    _process_scouting_payment(team)
    _process_loan_payments(team)
    _process_investments(team)

    current_week = get_game_week_id()

    # ── Loans ──
    active_loans = Loan.query.filter_by(team_id=team.id, is_active=True).order_by(Loan.created_at).all()
    has_federation_loan = any(l.loan_type == 'federation' for l in active_loans)
    can_borrow = not has_federation_loan and len(active_loans) < MAX_LOANS

    total_stars = (team.facility_training + team.facility_stream +
                   team.facility_locker + team.facility_ground)
    tiers = {}
    for key, t in LOAN_TIERS.items():
        tiers[key] = {**t, 'principal': total_stars * t['multiplier']}

    loans_display = []
    for loan in active_loans:
        weeks_left = loan.weeks_total - loan.weeks_paid
        weeks_overdue = max(0, current_week - loan.last_paid_week_id)
        loans_display.append({
            'loan': loan,
            'weeks_left': weeks_left,
            'remaining_due': round(loan.weekly_payment * weeks_left, 2),
            'weeks_overdue': weeks_overdue,
        })
    total_weekly_debt = sum(l.weekly_payment for l in active_loans)

    # ── Investments ──
    active_investments = Investment.query.filter_by(team_id=team.id, is_active=True).order_by(Investment.created_at).all()
    can_invest = len(active_investments) < MAX_INVESTMENTS

    # Count active per bond type for limit checks
    active_counts = {}
    for inv in active_investments:
        active_counts[inv.original_type] = active_counts.get(inv.original_type, 0) + 1

    investments_display = []
    for inv in active_investments:
        weeks_left = inv.game_week_id_maturity - current_week
        investments_display.append({
            'inv': inv,
            'weeks_left': max(0, weeks_left),
            'bond_info': BOND_TYPES.get(inv.bond_type, {}),
        })

    total_invested = sum(i.cost for i in active_investments)
    total_expected_payout = sum(i.payout for i in active_investments)

    return render_template('events/finance.html',
                           team=team,
                           game_date=format_game_date(),
                           active_loans=loans_display,
                           has_federation_loan=has_federation_loan,
                           can_borrow=can_borrow,
                           total_stars=total_stars,
                           tiers=tiers,
                           total_weekly_debt=total_weekly_debt,
                           loan_durations=[25, 50, 75, 100],
                           max_loans=MAX_LOANS,
                           investments_display=investments_display,
                           can_invest=can_invest,
                           active_counts=active_counts,
                           bond_types=BOND_TYPES,
                           max_investments=MAX_INVESTMENTS,
                           total_invested=total_invested,
                           total_expected_payout=total_expected_payout,
                           active_investments_count=len(active_investments))


@events_bp.route('/finance/borrow', methods=['POST'])
@login_required
def finance_borrow():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team

    active_loans = Loan.query.filter_by(team_id=team.id, is_active=True).all()
    has_federation_loan = any(l.loan_type == 'federation' for l in active_loans)
    if has_federation_loan:
        flash('Non puoi richiedere prestiti mentre è attivo l\'Aiuto dalla Federazione.', 'danger')
        return redirect(url_for('events.finance'))
    if len(active_loans) >= MAX_LOANS:
        flash(f'Hai già {MAX_LOANS} prestiti attivi. Restituiscili prima di richiederne altri.', 'danger')
        return redirect(url_for('events.finance'))

    loan_type = request.form.get('loan_type')
    try:
        weeks = int(request.form.get('weeks', 0))
    except (ValueError, TypeError):
        weeks = 0

    if loan_type not in LOAN_TIERS or weeks not in (25, 50, 75, 100):
        flash('Parametri non validi.', 'danger')
        return redirect(url_for('events.finance'))

    total_stars = (team.facility_training + team.facility_stream +
                   team.facility_locker + team.facility_ground)
    if total_stars == 0:
        flash('Il tuo stadio non ha ancora strutture: non puoi richiedere prestiti.', 'danger')
        return redirect(url_for('events.finance'))

    tier = LOAN_TIERS[loan_type]
    principal = total_stars * tier['multiplier']
    rate = tier['rate']
    total_due = round(principal * (1 + rate * (weeks / 25)), 2)
    weekly_payment = round(total_due / weeks, 2)

    loan = Loan(
        team_id=team.id,
        loan_type=loan_type,
        principal=principal,
        total_due=total_due,
        weekly_payment=weekly_payment,
        weeks_total=weeks,
        weeks_paid=0,
        last_paid_week_id=get_game_week_id(),  # first payment next week
    )
    team.budget += principal
    db.session.add(loan)
    db.session.commit()

    flash(f'💰 Prestito {tier["label"]} di €{principal/1_000_000:.1f}M approvato! '
          f'Rimborso: €{weekly_payment/1_000:.0f}k/settimana per {weeks} settimane.', 'success')
    return redirect(url_for('events.finance'))


def _process_wellness(team):
    """Grant weekly sessions from locker + active shoe upgrades."""
    current_week = get_game_week_id()
    if team.locker_last_grant_week_id >= current_week:
        return  # already processed this week

    granted_physio = 0
    granted_health = 0

    # Locker stars → physio sessions
    granted_physio += team.facility_locker

    # Soccer Pro: +3 physio/week while active
    if team.soccer_pro_end_week_id > 0 and current_week < team.soccer_pro_end_week_id:
        granted_physio += 3

    # Soccer Future: +5 physio +1 health/week while active
    if team.soccer_future_end_week_id > 0 and current_week < team.soccer_future_end_week_id:
        granted_physio += 5
        granted_health += 1
        # One-time skill boost on first grant week
        if not team.soccer_future_skill_boosted:
            import random as _r
            skills = ['porta', 'difesa', 'attacco', 'resistenza']
            for player in team.players.all():
                sk = _r.choice(skills)
                setattr(player, sk, round(getattr(player, sk) + 0.1, 2))
            team.soccer_future_skill_boosted = True

    team.physio_sessions = min(MAX_PHYSIO, team.physio_sessions + granted_physio)
    team.health_sessions = min(MAX_HEALTH, team.health_sessions + granted_health)
    team.locker_last_grant_week_id = current_week
    db.session.commit()


# ─── WELLNESS ──────────────────────────────────────────────────────────────────

@events_bp.route('/wellness')
@login_required
def wellness():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    _process_sponsor_payments(team)
    _process_loan_payments(team)
    _process_wellness(team)

    current_week = get_game_week_id()
    weekday = get_game_weekday()
    purchase_window = weekday in WELLNESS_PURCHASE_WEEKDAYS
    already_bought = team.wellness_last_buy_week_id == current_week

    players = team.players.order_by(None).all()
    human_players = [p for p in players if p.type in ('uomo', 'donna')]
    cyber_players = [p for p in players if p.type == 'cyber']

    # Secondary sponsor slots for shoe sponsor
    active_sponsors = ActiveSponsor.query.filter_by(team_id=team.id).all()
    secondary_count = sum(1 for s in active_sponsors if s.type in ('secondary', 'shoe'))
    shoe_sp_record = next((s for s in active_sponsors if s.type == 'shoe'), None)
    shoe_sponsor_active = shoe_sp_record is not None
    shoe_sponsor_name = shoe_sp_record.sponsor_name if shoe_sp_record else None
    shoe_sponsor_weeks_left = shoe_sp_record.remaining_weeks if shoe_sp_record else 0
    can_shoe_sponsor = not shoe_sponsor_active and secondary_count < 2

    # Shoe Pro cooldown: available if end_week <= current_week (or never used)
    pro_active = team.soccer_pro_end_week_id > current_week
    pro_available = not pro_active and (team.soccer_pro_end_week_id <= current_week)
    pro_weeks_left = max(0, team.soccer_pro_end_week_id - current_week) if pro_active else 0

    future_active = team.soccer_future_end_week_id > current_week
    future_available = not future_active and (team.soccer_future_end_week_id <= current_week)
    future_weeks_left = max(0, team.soccer_future_end_week_id - current_week) if future_active else 0

    return render_template('events/wellness.html',
                           team=team,
                           game_date=format_game_date(),
                           purchase_window=purchase_window,
                           weekday=weekday,
                           human_players=human_players,
                           cyber_players=cyber_players,
                           can_shoe_sponsor=can_shoe_sponsor,
                           shoe_sponsor_active=shoe_sponsor_active,
                           shoe_sponsor_name=shoe_sponsor_name,
                           shoe_sponsor_weeks_left=shoe_sponsor_weeks_left,
                           pro_active=pro_active,
                           pro_available=pro_available,
                           pro_weeks_left=pro_weeks_left,
                           future_active=future_active,
                           future_available=future_available,
                           future_weeks_left=future_weeks_left,
                           already_bought=already_bought,
                           MAX_PHYSIO=MAX_PHYSIO,
                           MAX_HEALTH=MAX_HEALTH,
                           MAX_CYBER=MAX_CYBER)


@events_bp.route('/wellness/buy-sessions', methods=['POST'])
@login_required
def wellness_buy_sessions():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    current_week = get_game_week_id()
    if get_game_weekday() not in WELLNESS_PURCHASE_WEEKDAYS:
        flash('Acquisti disponibili solo da mercoledì a domenica.', 'warning')
        return redirect(url_for('events.wellness'))
    if team.wellness_last_buy_week_id == current_week:
        flash('Hai già acquistato questa settimana. Prossimo acquisto disponibile da mercoledì.', 'warning')
        return redirect(url_for('events.wellness'))

    option = request.form.get('option')  # 'physio1','physio2','physio3','health1','diet'
    costs = {'physio1': 100_000, 'physio2': 250_000, 'physio3': 500_000, 'health1': 500_000, 'diet': 500_000}
    if option not in costs:
        flash('Opzione non valida.', 'danger')
        return redirect(url_for('events.wellness'))

    cost = costs[option]
    if team.budget < cost:
        flash('Budget insufficiente.', 'danger')
        return redirect(url_for('events.wellness'))

    team.budget -= cost
    if option == 'diet':
        players = team.players.all()
        for p in players:
            p.freshness = round(p.freshness + 0.2, 2)
        flash(f'🥗 Dieta bilanciata: +0.2 freschezza a tutti i {len(players)} giocatori.', 'success')
    elif option == 'health1':
        if team.health_sessions >= MAX_HEALTH:
            flash('Hai già il massimo di sessioni salute.', 'warning')
            return redirect(url_for('events.wellness'))
        team.health_sessions = min(MAX_HEALTH, team.health_sessions + 1)
        flash('✅ 1 sessione salute acquistata.', 'success')
    else:
        qty = int(option[-1])
        if team.physio_sessions + qty > MAX_PHYSIO:
            flash(f'Non puoi superare {MAX_PHYSIO} sessioni fisioterapia.', 'warning')
            return redirect(url_for('events.wellness'))
        team.physio_sessions = min(MAX_PHYSIO, team.physio_sessions + qty)
        flash(f'✅ {qty} sessione/i fisioterapia acquistate.', 'success')

    team.wellness_last_buy_week_id = current_week
    db.session.commit()
    return redirect(url_for('events.wellness'))


@events_bp.route('/wellness/convert', methods=['POST'])
@login_required
def wellness_convert():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    target = request.form.get('target')  # 'health' or 'cyber'

    if team.physio_sessions < 3:
        flash('Servono almeno 3 sessioni fisioterapia per la conversione.', 'danger')
        return redirect(url_for('events.wellness'))

    if target == 'health':
        if team.health_sessions >= MAX_HEALTH:
            flash('Hai già il massimo di sessioni salute.', 'warning')
            return redirect(url_for('events.wellness'))
        team.physio_sessions -= 3
        team.health_sessions = min(MAX_HEALTH, team.health_sessions + 1)
        flash('🔄 3 sessioni fisioterapia convertite in 1 sessione salute.', 'success')
    elif target == 'cyber':
        if team.cyber_sessions >= MAX_CYBER:
            flash('Hai già il massimo di sessioni cyberfisio.', 'warning')
            return redirect(url_for('events.wellness'))
        team.physio_sessions -= 3
        team.cyber_sessions = min(MAX_CYBER, team.cyber_sessions + 1)
        flash('🔄 3 sessioni fisioterapia convertite in 1 sessione cyberfisio.', 'success')
    else:
        flash('Tipo conversione non valido.', 'danger')

    db.session.commit()
    return redirect(url_for('events.wellness'))


@events_bp.route('/wellness/use', methods=['POST'])
@login_required
def wellness_use():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team

    from app.models.team import Player
    session_type = request.form.get('session_type')  # 'physio','health','cyber'
    try:
        player_id = int(request.form.get('player_id', 0))
    except (ValueError, TypeError):
        flash('Giocatore non valido.', 'danger')
        return redirect(url_for('events.wellness'))

    player = Player.query.get_or_404(player_id)
    if player.team_id != team.id:
        flash('Giocatore non nella tua squadra.', 'danger')
        return redirect(url_for('events.wellness'))

    if session_type == 'physio':
        if player.type not in ('uomo', 'donna'):
            flash('La fisioterapia funziona solo su giocatori uomini o donne.', 'warning')
            return redirect(url_for('events.wellness'))
        if team.physio_sessions < 1:
            flash('Nessuna sessione fisioterapia disponibile.', 'danger')
            return redirect(url_for('events.wellness'))
        team.physio_sessions -= 1
        player.freshness = round(player.freshness + 0.5, 2)
        flash(f'💆 {player.name}: +0.5 freschezza (fisioterapia).', 'success')

    elif session_type == 'health':
        if player.type not in ('uomo', 'donna'):
            flash('La sessione salute funziona solo su giocatori uomini o donne.', 'warning')
            return redirect(url_for('events.wellness'))
        if player.freshness >= 0:
            flash(f'{player.name} ha freschezza ≥ 0 — la sessione salute si usa solo su freschezza negativa.', 'warning')
            return redirect(url_for('events.wellness'))
        if team.health_sessions < 1:
            flash('Nessuna sessione salute disponibile.', 'danger')
            return redirect(url_for('events.wellness'))
        team.health_sessions -= 1
        player.freshness = round(player.freshness + 2.0, 2)
        flash(f'🏥 {player.name}: +2.0 freschezza (sessione salute).', 'success')

    elif session_type == 'cyber':
        if player.type != 'cyber':
            flash('La sessione cyberfisio funziona solo su giocatori cyber.', 'warning')
            return redirect(url_for('events.wellness'))
        if team.cyber_sessions < 1:
            flash('Nessuna sessione cyberfisio disponibile.', 'danger')
            return redirect(url_for('events.wellness'))
        team.cyber_sessions -= 1
        player.freshness = round(player.freshness + 2.5, 2)
        flash(f'🤖 {player.name}: +2.5 freschezza (cyberfisio).', 'success')

    else:
        flash('Tipo sessione non valido.', 'danger')
        return redirect(url_for('events.wellness'))

    db.session.commit()
    return redirect(url_for('events.wellness'))


@events_bp.route('/wellness/shop', methods=['POST'])
@login_required
def wellness_shop():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    item = request.form.get('item')
    current_week = get_game_week_id()

    if item == 'pro':
        # Scarpe Soccer Pro: 5M, +3 physio/week for 13 weeks, cooldown 13 weeks
        if team.soccer_pro_end_week_id > current_week:
            flash('Scarpe Pro già attive.', 'warning')
            return redirect(url_for('events.wellness'))
        if team.budget < 5_000_000:
            flash('Budget insufficiente (5M€).', 'danger')
            return redirect(url_for('events.wellness'))
        team.budget -= 5_000_000
        team.soccer_pro_end_week_id = current_week + 13
        db.session.commit()
        flash('👟 Scarpe Soccer Pro attivate! +3 sessioni fisioterapia/settimana per 13 settimane.', 'success')

    elif item == 'sponsor':
        # Scarpe Soccer Sponsor: free, +20 physio, locked secondary sponsor 5 weeks
        active_sponsors = ActiveSponsor.query.filter_by(team_id=team.id).all()
        secondary_count = sum(1 for s in active_sponsors if s.type in ('secondary', 'shoe'))
        shoe_active = any(s.type == 'shoe' for s in active_sponsors)
        if shoe_active:
            flash('Sponsor tecnico scarpe già attivo.', 'warning')
            return redirect(url_for('events.wellness'))
        if secondary_count >= 2:
            flash('Nessuno slot sponsor secondario disponibile.', 'danger')
            return redirect(url_for('events.wellness'))
        # Add +20 physio (one-time) and locked secondary sponsor for 5 weeks
        team.physio_sessions = min(MAX_PHYSIO, team.physio_sessions + 20)
        shoe_name = random.choice(_SHOE_SPONSOR_NAMES)
        shoe_sp = ActiveSponsor(
            team_id=team.id,
            sponsor_name=shoe_name,
            weekly_amount=0,
            remaining_weeks=5,
            type='shoe',
            last_paid_week_id=current_week,
        )
        db.session.add(shoe_sp)
        db.session.commit()
        flash(f'👟 Scarpe Soccer Sponsor attivate! Sponsor tecnico: {shoe_name} (5 settimane, non rimovibile) · +20 sessioni fisioterapia.', 'success')

    elif item == 'future':
        # Scarpe Soccer Future: 20M, +5 physio +1 health/week for 20 weeks, +0.1 skill once, cooldown 20 weeks
        if team.soccer_future_end_week_id > current_week:
            flash('Scarpe Future già attive.', 'warning')
            return redirect(url_for('events.wellness'))
        if team.budget < 20_000_000:
            flash('Budget insufficiente (20M€).', 'danger')
            return redirect(url_for('events.wellness'))
        team.budget -= 20_000_000
        team.soccer_future_end_week_id = current_week + 20
        team.soccer_future_skill_boosted = False   # reset so skill boost fires next processing
        db.session.commit()
        flash('👟 Scarpe Soccer Future attivate! +5 fisioterapia +1 salute/settimana per 20 settimane. +0.1 skill casuale a tutti i giocatori alla prossima visita.', 'success')

    else:
        flash('Articolo non valido.', 'danger')

    return redirect(url_for('events.wellness'))


# ─── FINANCE ───────────────────────────────────────────────────────────────────

@events_bp.route('/finance/invest', methods=['POST'])
@login_required
def finance_invest():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team

    bond_type = request.form.get('bond_type')
    if bond_type not in BOND_TYPES:
        flash('Tipo di cedola non valido.', 'danger')
        return redirect(url_for('events.finance'))

    bt = BOND_TYPES[bond_type]
    current_week = get_game_week_id()

    # Check global limit
    total_active = Investment.query.filter_by(team_id=team.id, is_active=True).count()
    if total_active >= MAX_INVESTMENTS:
        flash(f'Hai già {MAX_INVESTMENTS} cedole attive.', 'danger')
        return redirect(url_for('events.finance'))

    # Check per-type limit
    type_count = Investment.query.filter_by(team_id=team.id, original_type=bond_type, is_active=True).count()
    if type_count >= bt['max_count']:
        flash(f'Hai raggiunto il limite di {bt["max_count"]} cedole {bt["label"]}.', 'danger')
        return redirect(url_for('events.finance'))

    if team.budget < bt['cost']:
        flash(f'Budget insufficiente. Servono €{bt["cost"]/1_000_000:.0f}M.', 'danger')
        return redirect(url_for('events.finance'))

    # Roll for degradation
    actual_type = bond_type
    actual_payout = bt['payout']
    actual_weeks = bt['weeks']
    degraded = False

    if bt['degrade_chance'] > 0 and _random.random() < bt['degrade_chance']:
        degraded = True
        degrade_target = bt['degrade_to']
        actual_type = degrade_target
        # Degraded bond uses the target type's payout but a fixed 25-week maturity
        actual_payout = BOND_TYPES[degrade_target]['payout']
        actual_weeks = 25

    inv = Investment(
        team_id=team.id,
        bond_type=actual_type,
        original_type=bond_type,
        degraded=degraded,
        cost=bt['cost'],
        payout=actual_payout,
        weeks_total=actual_weeks,
        game_week_id_bought=current_week,
        game_week_id_maturity=current_week + actual_weeks,
    )
    team.budget -= bt['cost']
    db.session.add(inv)
    db.session.commit()

    if degraded:
        flash(
            f'⚠️ Cedola {bt["label"]} acquistata ma DEGRADATA a {BOND_TYPES[actual_type]["label"]}! '
            f'Riceverai €{actual_payout/1_000_000:.2f}M tra {actual_weeks} settimane.',
            'warning'
        )
    else:
        flash(
            f'📈 Cedola {bt["label"]} acquistata! '
            f'Riceverai €{actual_payout/1_000_000:.2f}M tra {actual_weeks} settimane.',
            'success'
        )
    return redirect(url_for('events.finance'))

