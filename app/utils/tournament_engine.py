"""July annual finals: knockout tournaments + Supercoppa.

Main tournament: up to 16 teams (the season's Elite monthly champions, topped up
by the strongest teams), one match every 7 days from 1 July. Secondary tournament:
every other competing team, one match every 3 days. Supercoppa on 31 July between
the two winners. Knockout matches are decisive: a draw is settled by a (simulated)
penalty shootout weighted by squad strength.
"""
import json
import random

from app import db

MAIN_BRACKET_MAX = 16
MAIN_DAYS_BETWEEN = 7
SECONDARY_DAYS_BETWEEN = 3


# ── Helpers ──────────────────────────────────────────────────────────────────

def _next_pow2(n):
    p = 1
    while p < n:
        p *= 2
    return p


def _seed_order(size):
    """Standard single-elimination seed order for a bracket of `size` (power of 2).

    Returns a list of 1-based seed numbers; pairing consecutive entries gives the
    classic 1-vs-last matchups so byes fall to the top seeds."""
    seeds = [1]
    while len(seeds) < size:
        m = len(seeds) * 2 + 1
        nxt = []
        for s in seeds:
            nxt.append(s)
            nxt.append(m - s)
        seeds = nxt
    return seeds


def _season_month_ids(season):
    """The 10 month_ids of a season: Sep–Dec of `season`, Jan–Jun of season+1."""
    ids = [season * 100 + m for m in range(9, 13)]
    ids += [(season + 1) * 100 + m for m in range(1, 7)]
    return ids


def _elite_champions(season):
    """Distinct teams that won the Elite group in any month of the season,
    most-recent month first."""
    from app.models.championship import (
        ChampionshipSeason, ChampionshipGroup, ChampionshipMembership,
    )
    from app.models.team import Team

    seen = set()
    champions = []
    seasons = ChampionshipSeason.query.filter(
        ChampionshipSeason.month_id.in_(_season_month_ids(season)),
        ChampionshipSeason.status == 'completed',
    ).order_by(ChampionshipSeason.month_id.desc()).all()

    for s in seasons:
        elite = ChampionshipGroup.query.filter_by(season_id=s.id, tier='elite').first()
        if not elite:
            continue
        winner = ChampionshipMembership.query.filter_by(
            season_id=s.id, group_id=elite.id, final_position=1).first()
        if winner and winner.team_id not in seen:
            t = Team.query.get(winner.team_id)
            if t:
                seen.add(winner.team_id)
                champions.append(t)
    return champions


_TIER_RANK = {'iron': 0, 'bronze': 1, 'silver': 2, 'gold': 3, 'elite': 4}


def _all_competing_teams():
    from app.models.team import Team
    return Team.query.filter(
        db.or_(Team.is_bot == True, Team.manager_id != None)  # noqa: E712
    ).all()


def _strength_key(team):
    return (_TIER_RANK.get(team.current_tier, 0), team.top7_avg_skill)


# ── Bracket construction ─────────────────────────────────────────────────────

def _create_bracket(tournament, teams):
    """Create every match of the bracket, seed round 0, resolve byes."""
    from app.models.championship import TournamentMatch

    teams = sorted(teams, key=_strength_key, reverse=True)
    size = max(2, _next_pow2(len(teams)))
    tournament.bracket_size = size

    seed_to_team = {}
    for i, t in enumerate(teams):
        seed_to_team[i + 1] = t  # seed 1 = strongest

    order = _seed_order(size)            # length == size
    positions = [seed_to_team.get(s) for s in order]

    rounds = size.bit_length() - 1       # log2(size)
    by_round = {}
    for r in range(rounds):
        n_matches = size // (2 ** (r + 1))
        day = tournament.start_game_day + r * tournament.days_between_rounds
        row = []
        for slot in range(n_matches):
            m = TournamentMatch(
                tournament_id=tournament.id,
                round_index=r, slot_index=slot,
                scheduled_game_day=day,
            )
            db.session.add(m)
            row.append(m)
        by_round[r] = row
    db.session.flush()

    # Seed round 0
    for slot, m in enumerate(by_round[0]):
        m.home_team_id = positions[2 * slot].id if positions[2 * slot] else None
        m.away_team_id = positions[2 * slot + 1].id if positions[2 * slot + 1] else None

    # Resolve byes top-down (a match with exactly one team auto-advances).
    for r in range(rounds):
        for m in by_round[r]:
            if m.status == 'played':
                continue
            present = [tid for tid in (m.home_team_id, m.away_team_id) if tid]
            if len(present) == 1 and r < rounds - 1:
                m.winner_team_id = present[0]
                m.status = 'played'
                _advance_winner(tournament, m, present[0], by_round)
    db.session.flush()


def _advance_winner(tournament, match, winner_id, by_round=None):
    """Place the winner into the correct slot of the next round."""
    from app.models.championship import TournamentMatch

    next_round = match.round_index + 1
    rounds = tournament.bracket_size.bit_length() - 1
    if next_round >= rounds:
        tournament.winner_team_id = winner_id
        tournament.status = 'completed'
        return

    next_slot = match.slot_index // 2
    if by_round is not None:
        nm = by_round[next_round][next_slot]
    else:
        nm = TournamentMatch.query.filter_by(
            tournament_id=tournament.id, round_index=next_round, slot_index=next_slot).first()
    if not nm:
        return
    if match.slot_index % 2 == 0:
        nm.home_team_id = winner_id
    else:
        nm.away_team_id = winner_id


# ── Match play ───────────────────────────────────────────────────────────────

def _play_match(match):
    """Simulate a knockout match to a decisive winner and advance it."""
    from app.models.team import Team
    from app.models.game import TeamFormation
    from app.utils.league_engine import _MockMatch
    from app.utils.match_engine import (
        build_home_lineup, generate_bot_lineup, simulate_match_to_completion,
    )

    home = Team.query.get(match.home_team_id) if match.home_team_id else None
    away = Team.query.get(match.away_team_id) if match.away_team_id else None

    tournament = match.tournament

    # A bye that never got a second team: whoever is present wins.
    if not home or not away:
        present = home or away
        if present:
            match.winner_team_id = present.id
            match.status = 'played'
            _advance_winner(tournament, match, present.id)
        return

    mock = _MockMatch(home, away)
    hf = TeamFormation.query.filter_by(team_id=home.id).first()
    af = TeamFormation.query.filter_by(team_id=away.id).first()
    mock.home_lineup_json = json.dumps(build_home_lineup(home, hf) if hf else generate_bot_lineup())
    mock.away_lineup_json = json.dumps(build_home_lineup(away, af) if af else generate_bot_lineup())

    simulate_match_to_completion(mock)

    match.home_score = mock.home_score
    match.away_score = mock.away_score
    match.home_lineup_json = mock.home_lineup_json
    match.away_lineup_json = mock.away_lineup_json
    match.turns_json = mock.turns_json
    match.injuries_json = mock.injuries_json
    match.played_game_day = match.scheduled_game_day
    match.status = 'played'

    if mock.home_score > mock.away_score:
        winner_id = home.id
    elif mock.away_score > mock.home_score:
        winner_id = away.id
    else:
        # Penalty shootout, weighted by squad strength.
        hs = max(0.1, home.top7_avg_skill)
        as_ = max(0.1, away.top7_avg_skill)
        winner_id = home.id if random.random() < hs / (hs + as_) else away.id
        match.decided_by_penalties = True

    match.winner_team_id = winner_id
    _advance_winner(tournament, match, winner_id)


# ── Tournament creation ──────────────────────────────────────────────────────

def _create_main(season):
    from app.models.championship import Tournament
    from app.utils.gameclock import get_july_first_game_day

    qualified = _elite_champions(season)
    if len(qualified) < MAIN_BRACKET_MAX:
        ids = {t.id for t in qualified}
        for t in sorted(_all_competing_teams(), key=_strength_key, reverse=True):
            if t.id not in ids:
                qualified.append(t)
                ids.add(t.id)
            if len(qualified) >= MAIN_BRACKET_MAX:
                break
    qualified = qualified[:MAIN_BRACKET_MAX]
    if len(qualified) < 2:
        return None

    t = Tournament(season=season, kind='main', status='active',
                   start_game_day=get_july_first_game_day(),
                   days_between_rounds=MAIN_DAYS_BETWEEN)
    db.session.add(t)
    db.session.flush()
    _create_bracket(t, qualified)
    return t


def _create_secondary(season, exclude_ids):
    from app.models.championship import Tournament
    from app.utils.gameclock import get_july_first_game_day

    teams = [t for t in _all_competing_teams() if t.id not in exclude_ids]
    if len(teams) < 2:
        return None

    t = Tournament(season=season, kind='secondary', status='active',
                   start_game_day=get_july_first_game_day(),
                   days_between_rounds=SECONDARY_DAYS_BETWEEN)
    db.session.add(t)
    db.session.flush()
    _create_bracket(t, teams)
    return t


def _create_supercoppa(season, main, secondary):
    from app.models.championship import Tournament, TournamentMatch
    from app.utils.gameclock import get_july_last_game_day

    t = Tournament(season=season, kind='supercoppa', status='active',
                   start_game_day=get_july_last_game_day(),
                   days_between_rounds=1, bracket_size=2)
    db.session.add(t)
    db.session.flush()
    db.session.add(TournamentMatch(
        tournament_id=t.id, round_index=0, slot_index=0,
        home_team_id=main.winner_team_id, away_team_id=secondary.winner_team_id,
        scheduled_game_day=get_july_last_game_day(),
    ))
    db.session.flush()
    return t


# ── Driver ───────────────────────────────────────────────────────────────────

def process_due_tournament_events():
    """Create July tournaments, auto-play due matches, crown the Supercoppa.
    Idempotent; safe to call on every request."""
    from app.models.championship import Tournament, TournamentMatch
    from app.utils.gameclock import is_july_finals, get_game_season, get_game_day_number

    if not is_july_finals():
        return

    season = get_game_season()
    current_day = get_game_day_number()

    main = Tournament.query.filter_by(season=season, kind='main').first()
    secondary = Tournament.query.filter_by(season=season, kind='secondary').first()

    created = False
    if main is None:
        main = _create_main(season)
        created = True
    if secondary is None:
        excl = {m.home_team_id for m in (main.matches if main else [])}
        excl |= {m.away_team_id for m in (main.matches if main else [])}
        secondary = _create_secondary(season, {i for i in excl if i})
        created = True
    if created:
        db.session.commit()

    # Auto-play due matches (both teams known).
    due = TournamentMatch.query.join(
        Tournament, TournamentMatch.tournament_id == Tournament.id
    ).filter(
        Tournament.status == 'active',
        TournamentMatch.status == 'scheduled',
        TournamentMatch.scheduled_game_day <= current_day,
        TournamentMatch.home_team_id != None,   # noqa: E712
        TournamentMatch.away_team_id != None,   # noqa: E712
    ).all()
    played = False
    for m in due:
        try:
            _play_match(m)
            played = True
        except Exception:
            db.session.rollback()
            continue
    if played:
        db.session.commit()

    # Supercoppa once both finals are decided and we've reached 31 July.
    if (main and secondary and main.status == 'completed' and secondary.status == 'completed'
            and main.winner_team_id and secondary.winner_team_id):
        from app.utils.gameclock import get_july_last_game_day
        sc = Tournament.query.filter_by(season=season, kind='supercoppa').first()
        if sc is None and current_day >= get_july_last_game_day():
            _create_supercoppa(season, main, secondary)
            db.session.commit()
        sc = Tournament.query.filter_by(season=season, kind='supercoppa').first()
        if sc and sc.status == 'active':
            for m in sc.matches:
                if m.status == 'scheduled' and m.scheduled_game_day <= current_day:
                    try:
                        _play_match(m)
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
