import random
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models.team import Team, Player
from app.models.game import TeamWeeklyOffer, TrainingRecord, SponsorOffer, ActiveSponsor
from app.utils.gameclock import (
    get_game_week_id, get_game_weekday, get_game_day_number,
    format_game_date, is_training_day, is_sponsor_day,
)
from app.utils.generators import (
    generate_market_offer_data, generate_sponsor_offer_data,
)

events_bp = Blueprint('events', __name__)

SKILLS = ['porta', 'difesa', 'attacco', 'resistenza']
SKILL_LABELS = {'porta': 'Porta', 'difesa': 'Difesa', 'attacco': 'Attacco', 'resistenza': 'Resistenza'}
MAX_SECONDARY = 2


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

    cost = round(offer.offer_avg * 500_000, -3)
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
    training_ok = is_training_day()

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

    if request.method == 'POST' and training_ok:
        bulk_500k = request.form.get('bulk_500k') == 'on'
        sessions = []

        for p in trainable:
            raw = request.form.getlist(f'skills_{p.id}')
            if len(raw) != 2:
                continue
            skill1, skill2 = raw[0], raw[1]
            if skill1 not in SKILLS or skill2 not in SKILLS or skill1 == skill2:
                continue
            prem = 'standard' if not bulk_500k else 'p50k'
            if not bulk_500k:
                prem = request.form.get(f'prem_{p.id}', 'standard')
            sessions.append((p, skill1, skill2, prem))

        if not sessions:
            flash('Seleziona esattamente 2 skill per almeno un giocatore.', 'warning')
            return redirect(url_for('events.training'))

        # Calculate cost
        if bulk_500k and sessions:
            total_cost = 500_000.0
        else:
            total_cost = sum(
                200_000 if prem == 'p200k' else (50_000 if prem == 'p50k' else 0)
                for _, _, _, prem in sessions
            )

        if team.budget < total_cost:
            flash(f'Budget insufficiente. Costo sessione: €{total_cost:,.0f}', 'danger')
            return redirect(url_for('events.training'))

        team.budget -= total_cost
        results = []
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

            player_cost = (200_000 if prem == 'p200k' else
                           (50_000 if prem == 'p50k' else 0)) if not bulk_500k else 0
            rec = TrainingRecord(
                team_id=team.id, player_id=p.id, game_day=game_day,
                skill1=skill1, skill2=skill2, premium_type=prem,
                skill_improved=improved if actual > 0 else None,
                improvement=actual, cost=player_cost,
            )
            db.session.add(rec)
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
        flash(f'Allenamento completato! {improved_count}/{len(results)} giocatori migliorati. '
              f'Costo: €{total_cost:,.0f}', 'success')

    return render_template('events/training.html',
                           team=team,
                           players=players,
                           trainable=trainable,
                           today_records=today_records,
                           is_training=training_ok,
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
