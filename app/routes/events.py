import random
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.team import Team, Player
from app.models.game import TeamWeeklyOffer, TrainingRecord, SponsorOffer, ActiveSponsor, FreeAgentListing, FreeAgentBid, Loan
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

LOAN_TIERS = {
    'green':  {'multiplier': 1_000_000, 'rate': 0.01, 'label': 'Green',  'color': 'var(--success)'},
    'yellow': {'multiplier': 2_000_000, 'rate': 0.03, 'label': 'Yellow', 'color': '#ffc800'},
    'red':    {'multiplier': 5_000_000, 'rate': 0.09, 'label': 'Red',    'color': 'var(--danger)'},
    'black':  {'multiplier':10_000_000, 'rate': 0.20, 'label': 'Black',  'color': '#888'},
}
MAX_LOANS = 3
FEDERATION_TARGET = 2_000_000   # bring budget up to this when emergency loan fires


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
    """If budget < 0, auto-issue a federation emergency loan to bring to +2M."""
    if team.budget >= 0:
        return
    # Only one federation loan at a time
    existing = Loan.query.filter_by(team_id=team.id, loan_type='federation', is_active=True).first()
    if existing:
        return
    amount = FEDERATION_TARGET - team.budget   # enough to reach +2M
    interest = round(amount * 0.01, 2)
    total_due = round(amount + interest, 2)
    loan = Loan(
        team_id=team.id,
        loan_type='federation',
        principal=amount,
        total_due=total_due,
        weekly_payment=total_due,   # repaid in full next week
        weeks_total=1,
        weeks_paid=0,
        last_paid_week_id=get_game_week_id(),  # start counting from this week → paid next week
    )
    team.budget += amount
    db.session.add(loan)
    db.session.commit()
    flash(f'🚨 Aiuto dalla Federazione attivato: €{amount/1_000_000:.2f}M (+ 1% interesse = €{total_due/1_000_000:.2f}M da restituire la prossima settimana).', 'warning')


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
    main_sponsor = next((s for s in active if s.type == 'main'), None)
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
                           week_id=week_id)


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

    active_loans = Loan.query.filter_by(team_id=team.id, is_active=True).order_by(Loan.created_at).all()
    has_federation_loan = any(l.loan_type == 'federation' for l in active_loans)
    can_borrow = not has_federation_loan and len(active_loans) < MAX_LOANS

    # Compute total_stars for loan amounts
    total_stars = (team.facility_training + team.facility_stream +
                   team.facility_locker + team.facility_ground)

    # Build tier info with actual amounts for this team
    tiers = {}
    for key, t in LOAN_TIERS.items():
        principal = total_stars * t['multiplier']
        tiers[key] = {**t, 'principal': principal}

    current_week = get_game_week_id()
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
                           max_loans=MAX_LOANS)


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

