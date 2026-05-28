"""Negozio premium (Gold): acquisto valuta, pass e spese Gold."""
import os
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app import db
from app.models.team import Player
from app.models.game import ActiveSponsor, Loan
from app.utils import ledger, gold
from app.utils.gold import (
    GOLD_PACKS, GOLD_SUB, PASS_STAGIONALE, PASS_FINANZA,
    GOLD_SCOUTING_COST, GOLD_ROSTER_SLOT_COST, GOLD_ROSTER_SLOT_MAX,
    GOLD_SPONSOR_SLOT_COST, GOLD_SPONSOR_SLOT_MAX,
    GOLD_SPONSOR_COST, GOLD_SPONSOR_WEEKLY, GOLD_SPONSOR_WEEKS, GOLD_SPONSOR_WEEKS_FED,
    GOLD_STADIUM_COST, GOLD_STADIUM_WEEKS, GOLD_FRESHNESS_COST, GOLD_FRESHNESS_BOOST,
)
from app.utils.gameclock import get_game_week_id, get_game_season, get_game_date

premium_bp = Blueprint('premium', __name__)

MAIN_SLOT_TYPES = ('main', 'dark', 'gold', 'stadium')


def payments_enabled():
    """True solo se è configurato un provider di pagamento (es. Stripe)."""
    return bool(os.environ.get('STRIPE_SECRET_KEY'))


def _require_team():
    if not current_user.team:
        flash('Devi prima creare una squadra.', 'warning')
        return redirect(url_for('game.create_team'))
    return None


@premium_bp.route('/')
@login_required
def store():
    if current_user.is_superadmin:
        flash('Il negozio Gold è riservato ai manager.', 'info')
        return redirect(url_for('admin.dashboard'))
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    active = ActiveSponsor.query.filter_by(team_id=team.id).all()
    has_main = any(s.type in MAIN_SLOT_TYPES for s in active)
    has_fed_loan = Loan.query.filter_by(team_id=team.id, loan_type='federation', is_active=True).first() is not None
    has_stadium_sponsor = any(s.type == 'stadium' for s in active)
    month = get_game_date().month
    return render_template(
        'premium/store.html',
        team=team,
        gold=gold.balance(current_user),
        packs=GOLD_PACKS, sub=GOLD_SUB,
        pass_stag=PASS_STAGIONALE, pass_finanza=PASS_FINANZA,
        payments_on=payments_enabled(),
        roster_max=GOLD_ROSTER_SLOT_MAX, sponsor_max=GOLD_SPONSOR_SLOT_MAX,
        sponsor_cost=GOLD_SPONSOR_COST, sponsor_weeks=GOLD_SPONSOR_WEEKS,
        sponsor_weekly=GOLD_SPONSOR_WEEKLY, stadium_cost=GOLD_STADIUM_COST,
        stadium_weeks=GOLD_STADIUM_WEEKS, fresh_cost=GOLD_FRESHNESS_COST,
        has_main=has_main, has_fed_loan=has_fed_loan, has_stadium_sponsor=has_stadium_sponsor,
        seasonal_window=(9 <= month <= 12),
        seasonal_bought=current_user.seasonal_pass_season == get_game_season(),
    )


# ── Acquisti con denaro reale (gated finché non c'è un provider) ────────────────

@premium_bp.route('/buy/<pack>', methods=['POST'])
@login_required
def buy_pack(pack):
    if pack not in GOLD_PACKS:
        flash('Pacchetto non valido.', 'danger')
        return redirect(url_for('premium.store'))
    if not payments_enabled():
        flash('💳 I pagamenti con denaro reale non sono ancora attivi.', 'warning')
        return redirect(url_for('premium.store'))
    # Con provider attivo qui partirebbe il checkout; l'accredito Gold avviene
    # nel webhook dopo la conferma del pagamento (verifica server-side).
    flash('Reindirizzamento al pagamento…', 'info')
    return redirect(url_for('premium.store'))


@premium_bp.route('/subscribe', methods=['POST'])
@login_required
def subscribe():
    if not payments_enabled():
        flash('💳 Gli abbonamenti non sono ancora attivi.', 'warning')
        return redirect(url_for('premium.store'))
    flash('Reindirizzamento al pagamento…', 'info')
    return redirect(url_for('premium.store'))


@premium_bp.route('/pass/stagionale', methods=['POST'])
@login_required
def pass_stagionale():
    redir = _require_team()
    if redir:
        return redir
    month = get_game_date().month
    if not (9 <= month <= 12):
        flash('Il Pass Stagionale è acquistabile solo da settembre a dicembre.', 'danger')
        return redirect(url_for('premium.store'))
    if current_user.seasonal_pass_season == get_game_season():
        flash('Hai già acquistato il Pass Stagionale per questa stagione.', 'danger')
        return redirect(url_for('premium.store'))
    if not payments_enabled():
        flash('💳 I pagamenti con denaro reale non sono ancora attivi.', 'warning')
        return redirect(url_for('premium.store'))
    # Post-pagamento (eseguito qui per completezza logica):
    gold.grant(current_user, PASS_STAGIONALE['gold'], 'Pass Stagionale')
    ledger.record(current_user.team, PASS_STAGIONALE['cash'], ledger.CAT_LEAGUE_INCOME, 'Pass Stagionale')
    current_user.seasonal_pass_season = get_game_season()
    db.session.commit()
    flash('🍂 Pass Stagionale attivato!', 'success')
    return redirect(url_for('premium.store'))


@premium_bp.route('/pass/finanza', methods=['POST'])
@login_required
def pass_finanza():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    if team.budget < PASS_FINANZA['cash']:
        flash(f'Budget insufficiente: servono €{PASS_FINANZA["cash"]/1_000_000:.0f}M.', 'danger')
        return redirect(url_for('premium.store'))
    ledger.record(team, -PASS_FINANZA['cash'], ledger.CAT_BOND, 'Pass Finanza (→ Gold)')
    gold.grant(current_user, PASS_FINANZA['gold'], 'Pass Finanza')
    db.session.commit()
    flash(f'💼 Pass Finanza: −€{PASS_FINANZA["cash"]/1_000_000:.0f}M → +{PASS_FINANZA["gold"]} Gold.', 'success')
    return redirect(url_for('premium.store'))


# ── Spese Gold ricorrenti (toggle) ──────────────────────────────────────────────

@premium_bp.route('/scouting-gold/toggle', methods=['POST'])
@login_required
def scouting_gold_toggle():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    if team.gold_scouting_active:
        team.gold_scouting_active = False
        flash('🔭 Scouting Gold disattivato.', 'info')
    else:
        if gold.balance(current_user) < GOLD_SCOUTING_COST:
            flash('Gold insufficiente per attivare lo Scouting Gold.', 'danger')
            return redirect(url_for('premium.store'))
        team.gold_scouting_active = True
        # Prima fatturazione il prossimo mese di gioco
        from app.utils.gameclock import get_game_month_id
        team.gold_scouting_last_month = get_game_month_id()
        flash('🔭 Scouting Gold attivato! Ogni mese di gioco: 1 Gold → 1 giocatore.', 'success')
    db.session.commit()
    return redirect(url_for('premium.store'))


@premium_bp.route('/roster-slot', methods=['POST'])
@login_required
def roster_slot():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    action = request.form.get('action', 'add')
    from app.utils.gameclock import get_game_month_id
    if action == 'add':
        if team.gold_roster_slots >= GOLD_ROSTER_SLOT_MAX:
            flash(f'Hai già il massimo di slot rosa extra ({GOLD_ROSTER_SLOT_MAX}).', 'danger')
            return redirect(url_for('premium.store'))
        if gold.balance(current_user) < GOLD_ROSTER_SLOT_COST:
            flash('Gold insufficiente.', 'danger')
            return redirect(url_for('premium.store'))
        if team.gold_roster_slots == 0:
            team.gold_roster_last_month = get_game_month_id()
        team.gold_roster_slots += 1
        flash('➕ Slot rosa extra attivato (1 Gold/mese).', 'success')
    else:
        if team.gold_roster_slots > 0:
            team.gold_roster_slots -= 1
            flash('➖ Slot rosa extra disattivato.', 'info')
    db.session.commit()
    return redirect(url_for('premium.store'))


@premium_bp.route('/sponsor-slot', methods=['POST'])
@login_required
def sponsor_slot():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    action = request.form.get('action', 'add')
    from app.utils.gameclock import get_game_month_id
    if action == 'add':
        if team.gold_sponsor_slots >= GOLD_SPONSOR_SLOT_MAX:
            flash(f'Hai già il massimo di slot sponsor extra ({GOLD_SPONSOR_SLOT_MAX}).', 'danger')
            return redirect(url_for('premium.store'))
        if gold.balance(current_user) < GOLD_SPONSOR_SLOT_COST:
            flash('Gold insufficiente.', 'danger')
            return redirect(url_for('premium.store'))
        if team.gold_sponsor_slots == 0:
            team.gold_sponsor_last_month = get_game_month_id()
        team.gold_sponsor_slots += 1
        flash('➕ Slot sponsor secondario extra attivato (1 Gold/mese).', 'success')
    else:
        if team.gold_sponsor_slots > 0:
            team.gold_sponsor_slots -= 1
            flash('➖ Slot sponsor secondario extra disattivato.', 'info')
    db.session.commit()
    return redirect(url_for('premium.store'))


# ── Spese Gold una tantum ───────────────────────────────────────────────────────

@premium_bp.route('/sponsor-gold', methods=['POST'])
@login_required
def sponsor_gold():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    week_id = get_game_week_id()
    fed_loan = Loan.query.filter_by(team_id=team.id, loan_type='federation', is_active=True).first()
    existing_main = ActiveSponsor.query.filter(
        ActiveSponsor.team_id == team.id, ActiveSponsor.type.in_(MAIN_SLOT_TYPES)).first()

    if fed_loan is None and existing_main is not None:
        flash('Slot principale occupato: rimuovi lo sponsor principale prima.', 'danger')
        return redirect(url_for('premium.store'))

    if not gold.spend(current_user, GOLD_SPONSOR_COST, 'Sponsor Gold'):
        flash(f'Gold insufficiente (servono {GOLD_SPONSOR_COST}).', 'danger')
        return redirect(url_for('premium.store'))

    weekly_m = GOLD_SPONSOR_WEEKLY / 1_000_000
    if fed_loan is not None:
        # L'aiuto della federazione viene saldato dallo sponsor; sponsor bloccato in main per 10 settimane
        fed_loan.weeks_paid = fed_loan.weeks_total
        fed_loan.is_active = False
        team.federation_loan_streak = 0
        if existing_main is not None and not existing_main.locked:
            db.session.delete(existing_main)
        weeks = GOLD_SPONSOR_WEEKS_FED
        locked = True
        msg = ('🟡 Sponsor Gold: aiuto della Federazione saldato; '
               f'sponsor bloccato in principale per {weeks} settimane ({weekly_m:.0f}M/sett.).')
    else:
        weeks = GOLD_SPONSOR_WEEKS
        locked = False
        total_m = weekly_m * weeks
        msg = f'🟡 Sponsor Gold attivato: {total_m:.0f}M in {weeks} settimane ({weekly_m:.0f}M/sett.).'

    db.session.add(ActiveSponsor(
        team_id=team.id, sponsor_name='Sponsor Gold',
        weekly_amount=GOLD_SPONSOR_WEEKLY, remaining_weeks=weeks,
        type='gold', last_paid_week_id=week_id, locked=locked,
    ))
    db.session.commit()
    flash(msg, 'success')
    return redirect(url_for('premium.store'))


@premium_bp.route('/sponsor-stadio', methods=['POST'])
@login_required
def sponsor_stadio():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    main = ActiveSponsor.query.filter_by(team_id=team.id, type='main').first()
    if main is None:
        flash('Serve uno sponsor principale (non Gold/Oscuro) da trasformare.', 'danger')
        return redirect(url_for('premium.store'))
    if not gold.spend(current_user, GOLD_STADIUM_COST, 'Sponsor Stadio'):
        flash(f'Gold insufficiente (servono {GOLD_STADIUM_COST}).', 'danger')
        return redirect(url_for('premium.store'))
    main.type = 'stadium'
    main.sponsor_name = f'{main.sponsor_name} Stadium'
    main.remaining_weeks = GOLD_STADIUM_WEEKS
    main.locked = True
    main.last_paid_week_id = get_game_week_id()
    db.session.commit()
    flash(f'🏟️ Sponsor Stadio attivo per {GOLD_STADIUM_WEEKS} settimane: stop alla manutenzione dello stadio.', 'success')
    return redirect(url_for('premium.store'))


@premium_bp.route('/freshness-boost', methods=['POST'])
@login_required
def freshness_boost():
    redir = _require_team()
    if redir:
        return redir
    team = current_user.team
    if not gold.spend(current_user, GOLD_FRESHNESS_COST, 'Boost freschezza'):
        flash(f'Gold insufficiente (serve {GOLD_FRESHNESS_COST}).', 'danger')
        return redirect(url_for('premium.store'))
    for p in team.players.all():
        p.freshness = min(10.0, round(p.freshness + GOLD_FRESHNESS_BOOST, 1))
    db.session.commit()
    flash(f'⚡ +{GOLD_FRESHNESS_BOOST:.0f} freschezza a tutti i giocatori.', 'success')
    return redirect(url_for('premium.store'))
