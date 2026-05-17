import random
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.team import Team, Player
from app.models.game import TeamWeeklyOffer, TrainingRecord, SponsorOffer, ActiveSponsor, FreeAgentListing, FreeAgentBid
from app.utils.gameclock import (
    get_game_week_id, get_game_weekday, get_game_day_number,
    format_game_date, is_training_day, is_sponsor_day, get_game_month_id,
)
from app.utils.generators import (
    generate_market_offer_data, generate_sponsor_offer_data,
)

events_bp = Blueprint('events', __name__)

SKILLS = ['porta', 'difesa', 'attacco', 'resistenza']
SKILL_LABELS = {'porta': 'Porta', 'difesa': 'Difesa', 'attacco': 'Attacco', 'resistenza': 'Resistenza'}
MAX_SECONDARY = 2
_FACILITY_ATTRS = ['facility_training', 'facility_stream', 'facility_locker', 'facility_ground']


def _require_team():
    if not current_user.team:
        flash('Devi prima creare una squadra.', 'warning')
        return redirect(url_for('game.create_team'))
    return None


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


# ─── MARKET ────────────────────────────────────────────────────────────────────

@events_bp.route('/market')
@login_required
def market():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    _process_sponsor_payments(team)

    week_id = get_game_week_id()
    weekday = get_game_weekday()
    scouting_active = team.scouting_active

    # Generate offer once per week (available from Monday onwards)
    offer = TeamWeeklyOffer.query.filter_by(team_id=team.id, game_week_id=week_id).first()
    if not offer:
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
                           scouting_active=scouting_active,
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
    week_id = get_game_week_id()
    cost = 1_000_000
    if team.budget < cost:
        flash('Budget insufficiente per attivare lo scouting (1M€).', 'danger')
        return redirect(url_for('events.market'))
    team.budget -= cost
    team.scouting_paid_week_id = week_id
    # If offer already generated this week without scouting, regenerate it
    offer = TeamWeeklyOffer.query.filter_by(team_id=team.id, game_week_id=week_id).first()
    if offer and not offer.purchased and not offer.is_scouted:
        data = generate_market_offer_data(scouted=True)
        offer.offer_name = data['name']
        offer.offer_type = data['type']
        offer.offer_age = data['age']
        offer.offer_porta = data['porta']
        offer.offer_difesa = data['difesa']
        offer.offer_attacco = data['attacco']
        offer.offer_resistenza = data['resistenza']
        offer.offer_avg = data['avg']
        offer.is_scouted = True
    db.session.commit()
    flash('Scouting attivato per questa settimana! Giocatore aggiornato.', 'success')
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

    game_day = get_game_day_number()
    weekday = get_game_weekday()
    regular_training = is_training_day()
    saturday_slots = team.facility_training if weekday == 5 else 0
    is_saturday_mode = saturday_slots > 0
    training_ok = regular_training or is_saturday_mode

    from app.routes.game import _process_team_freshness
    _process_team_freshness(team)

    players = team.players.all()
    trained_ids = {
        r.player_id for r in
        TrainingRecord.query.filter_by(team_id=team.id, game_day=game_day).all()
    }
    today_records = {
        r.player_id: r for r in
        TrainingRecord.query.filter_by(team_id=team.id, game_day=game_day).all()
    }
    trainable = [p for p in players if p.id not in trained_ids]

    # Formation roles for display
    formation_roles = team.formation.current_roles() if team.formation else {}

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
            p.last_freshness_day = game_day
            results.append({'player': p, 'improved': improved, 'delta': actual})

        db.session.commit()
        trained_ids = {r.player_id for r in
                       TrainingRecord.query.filter_by(team_id=team.id, game_day=game_day).all()}
        today_records = {
            r.player_id: r for r in
            TrainingRecord.query.filter_by(team_id=team.id, game_day=game_day).all()
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
                           saturday_slots=saturday_slots,
                           training_ok=training_ok,
                           game_date=format_game_date(),
                           weekday=weekday,
                           game_day=game_day,
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

    week_id = get_game_week_id()
    weekday = get_game_weekday()
    is_friday = is_sponsor_day()

    active = ActiveSponsor.query.filter_by(team_id=team.id).all()
    main_sponsor = next((s for s in active if s.type == 'main'), None)
    secondary_sponsors = [s for s in active if s.type == 'secondary']

    # Generate Friday offer if not yet created
    offer = SponsorOffer.query.filter_by(team_id=team.id, game_week_id=week_id,
                                         status='pending').first() if is_friday else None
    if is_friday and not SponsorOffer.query.filter_by(team_id=team.id, game_week_id=week_id).first():
        existing_names = {s.sponsor_name for s in active}
        data = generate_sponsor_offer_data(team.top7_avg_skill, existing_names)
        offer = SponsorOffer(
            team_id=team.id, game_week_id=week_id,
            sponsor_name=data['name'],
            weekly_amount=data['weekly_amount'],
            duration_weeks=data['duration_weeks'],
        )
        db.session.add(offer)
        db.session.commit()

    return render_template('events/sponsors.html',
                           team=team,
                           offer=offer,
                           active=active,
                           main_sponsor=main_sponsor,
                           secondary_sponsors=secondary_sponsors,
                           can_add_main=main_sponsor is None,
                           can_add_secondary=len(secondary_sponsors) < MAX_SECONDARY,
                           is_friday=is_friday,
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
