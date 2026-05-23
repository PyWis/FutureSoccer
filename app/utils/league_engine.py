"""Private league engine: calendar generation, finance, auto-play, season lifecycle."""
import json
import random
from datetime import timedelta

from app import db

# ── Constants ────────────────────────────────────────────────────────────────
LEAGUE_CREATION_COST = 100_000_000.0
LEAGUE_LOAN_PRINCIPAL = 100_000_000.0
LEAGUE_LOAN_TOTAL_DUE = 105_000_000.0
LEAGUE_LOAN_WEEKLY_PAYMENT = 1_050_000.0
LEAGUE_LOAN_WEEKS = 100

ENTRY_FEE = 10_000_000.0
PERMANENCE_FEE = 5_000_000.0
MIN_TEAMS = 4
MAX_CAPACITY = 24

OWNER_SHARE = 0.02
EQUAL_SHARE = 0.68
MERIT_SHARE = 0.30

POSITION_BONUSES = {1: 100, 2: 50, 3: 20, 4: 10}
PRESTIGE_COEFFICIENT = 1_000_000.0

# ── Calendar helpers ──────────────────────────────────────────────────────────

def _berger_rounds(team_ids):
    """Berger circle algorithm. Returns list of rounds, each round is list of (home_id, away_id)."""
    lst = list(team_ids)
    n = len(lst)
    if n % 2 == 1:
        lst.append(None)
        n += 1

    rounds = []
    for _ in range(n - 1):
        pairs = []
        for i in range(n // 2):
            h, a = lst[i], lst[n - 1 - i]
            if h is not None and a is not None:
                pairs.append((h, a))
        rounds.append(pairs)
        lst = [lst[0]] + [lst[-1]] + lst[1:-1]
    return rounds


def generate_season_calendar(season, memberships):
    """Build NBA-style calendar for the season.

    - N-1 rounds of round-robin sola andata
    - Rounds distributed over weeks 1..(N-1); last round on end_game_day
    - Conflict resolution: push to next free day (before end_game_day)
    Returns a list of unsaved PrivateLeagueMatch objects.
    """
    from app.models.private_league import PrivateLeagueMatch

    active = [m for m in memberships if m.status == 'active']
    team_ids = [m.team_id for m in active]
    n = len(team_ids)
    if n < 2:
        return []

    start_day = season.start_game_day
    end_day = season.end_game_day

    rounds = _berger_rounds(team_ids)       # N-1 rounds

    rng = random.Random(season.tiebreak_seed)
    rng.shuffle(rounds)

    last_round_pairs = rounds[-1]
    other_rounds = rounds[:-1]              # N-2 rounds

    # Track busy days per team
    team_days: dict = {tid: set() for tid in team_ids}

    matches = []
    week = 7  # days per week

    for week_idx, round_pairs in enumerate(other_rounds):
        w_start = start_day + week_idx * week
        w_end = w_start + week - 1
        max_day = min(w_end, end_day - 1)

        for home_id, away_id in round_pairs:
            candidates = list(range(w_start, max_day + 1))
            rng.shuffle(candidates)

            day = None
            for d in candidates:
                if d not in team_days[home_id] and d not in team_days[away_id]:
                    day = d
                    break

            # Overflow search
            if day is None:
                for d in range(w_end + 1, end_day):
                    if d not in team_days[home_id] and d not in team_days[away_id]:
                        day = d
                        break

            if day is None:
                day = end_day - 1

            team_days[home_id].add(day)
            team_days[away_id].add(day)

            matches.append(PrivateLeagueMatch(
                season_id=season.id,
                home_team_id=home_id,
                away_team_id=away_id,
                round_number=week_idx + 1,
                is_final_round=False,
                scheduled_game_day=day,
                status='scheduled',
            ))

    # Last round: all on end_day
    final_round = len(rounds)
    for home_id, away_id in last_round_pairs:
        matches.append(PrivateLeagueMatch(
            season_id=season.id,
            home_team_id=home_id,
            away_team_id=away_id,
            round_number=final_round,
            is_final_round=True,
            scheduled_game_day=end_day,
            status='scheduled',
        ))

    return matches


# ── Prestige ─────────────────────────────────────────────────────────────────

def _prestige_base_first(memberships):
    """Seed prestige: avg_force * 2 * 4."""
    forces = [m.team.top7_avg_skill for m in memberships if m.team]
    if not forces:
        return 0.0
    return round((sum(forces) / len(forces)) * 2 * 4, 2)


def _prestige_base_from_prev(prev_memberships):
    """Prestige from previous season force snapshots (average × count)."""
    snaps = [m.force_snapshot for m in prev_memberships if m.force_snapshot is not None]
    if not snaps:
        return 0.0
    return round((sum(snaps) / len(snaps)) * len(snaps), 2)


# ── Season lifecycle ──────────────────────────────────────────────────────────

def create_forming_season(league):
    """Create the first 'forming' season for a new league."""
    from app.models.private_league import PrivateLeagueSeason
    s = PrivateLeagueSeason(
        league_id=league.id,
        season_number=1,
        status='forming',
    )
    db.session.add(s)
    db.session.flush()
    return s


def start_season(league):
    """Activate the current forming season.

    Returns (season, error_message). On success error_message is None.
    If < MIN_TEAMS the season is cancelled (loan continues).
    """
    from app.models.private_league import PrivateLeagueSeason, PrivateLeagueMembership
    from app.utils.gameclock import get_game_day_number
    from app.utils.gameclock import GAME_START_DATE, game_day_to_date
    from app.utils import ledger

    season = league.current_season
    if not season or season.status != 'forming':
        return None, 'Nessuna stagione in fase di formazione.'

    memberships = PrivateLeagueMembership.query.filter_by(
        season_id=season.id, status='active'
    ).all()

    if len(memberships) < MIN_TEAMS:
        season.status = 'cancelled'
        db.session.commit()
        return None, f'Stagione annullata: servono almeno {MIN_TEAMS} squadre (trovate {len(memberships)}).'

    n = len(memberships)
    today = game_day_to_date(get_game_day_number())
    # Start next Monday
    days_to_mon = (7 - today.weekday()) % 7 or 7
    start_date = today + timedelta(days=days_to_mon)
    start_day = (start_date - GAME_START_DATE).days
    end_day = start_day + n * 7 - 1    # N weeks duration

    season.num_teams = n
    season.capacity_at_start = league.capacity
    season.start_game_day = start_day
    season.end_game_day = end_day
    season.tiebreak_seed = random.randint(1, 10 ** 9)

    # Prestige
    prev = PrivateLeagueSeason.query.filter_by(
        league_id=league.id, status='completed'
    ).order_by(PrivateLeagueSeason.season_number.desc()).first()

    if prev is None:
        season.prestige_base = _prestige_base_first(memberships)
    else:
        prev_mems = PrivateLeagueMembership.query.filter_by(season_id=prev.id).all()
        season.prestige_base = _prestige_base_from_prev(prev_mems)

    season.prestige_coefficient = PRESTIGE_COEFFICIENT
    season.prestige_random = round(random.uniform(0.70, 1.00), 4)
    season.prestige = round(season.prestige_base * season.prestige_coefficient * season.prestige_random, 2)
    season.sponsor_amount = season.prestige

    # Assign tiebreak randoms
    rng = random.Random(season.tiebreak_seed)
    for m in memberships:
        m.tiebreak_random = rng.randint(1, 10 ** 9)

    # Collect fees into league wallet
    for m in memberships:
        t = m.team
        if t.budget >= ENTRY_FEE:
            ledger.record(t, -ENTRY_FEE, ledger.CAT_LEAGUE_ENTRY,
                          f'Iscrizione Lega Privata: {league.name}')
            m.entry_fee_paid = True
            season.total_budget += ENTRY_FEE
        if t.budget >= PERMANENCE_FEE:
            ledger.record(t, -PERMANENCE_FEE, ledger.CAT_LEAGUE_PERM,
                          f'Quota permanenza Lega Privata: {league.name}')
            m.permanence_fee_paid = True
            season.total_budget += PERMANENCE_FEE

    season.total_budget += season.sponsor_amount

    # Generate calendar
    calendar = generate_season_calendar(season, memberships)
    for match in calendar:
        db.session.add(match)

    season.status = 'active'
    league.capacity = min(league.capacity + 2, MAX_CAPACITY)

    db.session.commit()
    return season, None


# ── Match auto-play ───────────────────────────────────────────────────────────

class _MockMatch:
    """Minimal duck-type for match_engine functions."""
    def __init__(self, home_team, away_team):
        self.home_team_id = home_team.id
        self.away_team_id = away_team.id
        self.home_team = home_team
        self.away_team = away_team
        self.status = 'active'
        self.current_turn = 0
        self.home_score = 0
        self.away_score = 0
        self.last_turn_at = None
        self.home_lineup_json = '{}'
        self.away_lineup_json = '{}'
        self.home_pending_subs_json = '{}'
        self.away_pending_subs_json = '{}'
        self.injuries_json = '[]'
        self.turns_json = '[]'


def _auto_play_league_match(match):
    """Simulate a league match to completion and persist results."""
    from app.models.game import TeamFormation
    from app.utils.match_engine import (
        build_home_lineup, generate_bot_lineup, simulate_match_to_completion,
    )

    home_team = match.home_team
    away_team = match.away_team

    mock = _MockMatch(home_team, away_team)

    hf = TeamFormation.query.filter_by(team_id=home_team.id).first()
    mock.home_lineup_json = json.dumps(
        build_home_lineup(home_team, hf) if hf else generate_bot_lineup()
    )

    af = TeamFormation.query.filter_by(team_id=away_team.id).first()
    mock.away_lineup_json = json.dumps(
        build_home_lineup(away_team, af) if af else generate_bot_lineup()
    )

    simulate_match_to_completion(mock)

    match.home_score = mock.home_score
    match.away_score = mock.away_score
    match.home_lineup_json = mock.home_lineup_json
    match.away_lineup_json = mock.away_lineup_json
    match.turns_json = mock.turns_json
    match.injuries_json = mock.injuries_json
    match.played_game_day = match.scheduled_game_day
    match.status = 'played'

    _update_standings(match)


def _update_standings(match):
    from app.models.private_league import PrivateLeagueMembership

    hm = PrivateLeagueMembership.query.filter_by(
        season_id=match.season_id, team_id=match.home_team_id).first()
    am = PrivateLeagueMembership.query.filter_by(
        season_id=match.season_id, team_id=match.away_team_id).first()
    if not hm or not am:
        return

    hm.goals_for += match.home_score
    hm.goals_against += match.away_score
    am.goals_for += match.away_score
    am.goals_against += match.home_score

    if match.home_score > match.away_score:
        hm.wins += 1
        am.losses += 1
    elif match.home_score < match.away_score:
        am.wins += 1
        hm.losses += 1
    else:
        hm.draws += 1
        am.draws += 1

    hm.points = hm.wins * 3 + hm.draws
    am.points = am.wins * 3 + am.draws


# ── Standings ─────────────────────────────────────────────────────────────────

def get_standings(season):
    """Return memberships sorted: points → goal_diff → goals_for → tiebreak_random."""
    from app.models.private_league import PrivateLeagueMembership
    mems = PrivateLeagueMembership.query.filter_by(season_id=season.id).all()
    return sorted(
        mems,
        key=lambda m: (-m.points, -(m.goals_for - m.goals_against), -m.goals_for, m.tiebreak_random),
    )


# ── Weekly payout ─────────────────────────────────────────────────────────────

def process_weekly_payout(season):
    """Distribute weekly share of league budget. Idempotent per game-week."""
    from app.utils.gameclock import get_game_week_id
    from app.utils import ledger
    from app.models.private_league import PrivateLeagueMembership

    week = get_game_week_id()
    if season.last_payout_week_id >= week:
        return

    mems = PrivateLeagueMembership.query.filter_by(
        season_id=season.id, status='active').all()
    n = len(mems)
    if n == 0 or season.total_budget <= 0:
        season.last_payout_week_id = week
        return

    budget = season.total_budget

    # 2 % to owner
    owner_team = season.league.owner.team if season.league.owner else None
    if owner_team:
        ledger.record(owner_team, budget * OWNER_SHARE, ledger.CAT_LEAGUE_INCOME,
                      f'Quota proprietario Lega: {season.league.name}')

    # 68 % equal split
    per_equal = budget * EQUAL_SHARE / n
    for m in mems:
        ledger.record(m.team, per_equal, ledger.CAT_LEAGUE_INCOME,
                      f'Quota fissa Lega: {season.league.name}')

    # 30 % meritocratic
    standings = get_standings(season)
    merit_pool = budget * MERIT_SHARE
    weights = [(m, max(m.points + POSITION_BONUSES.get(pos, 0), 1))
               for pos, m in enumerate(standings, 1)]
    total_w = sum(w for _, w in weights)
    if total_w > 0:
        for m, w in weights:
            ledger.record(m.team, merit_pool * w / total_w, ledger.CAT_LEAGUE_INCOME,
                          f'Quota meritocratica Lega: {season.league.name}')

    season.last_payout_week_id = week


# ── Season finalisation ───────────────────────────────────────────────────────

def finalize_season(season):
    """Assign positions, snapshots, exclusions, ownership transfer, prepare next season."""
    from app.models.private_league import PrivateLeagueMembership

    standings = get_standings(season)
    for pos, m in enumerate(standings, 1):
        m.final_position = pos
        m.force_snapshot = m.team.top7_avg_skill if m.team else 0.0

    # Auto-exclude bottom 2 when at max capacity
    if season.num_teams and season.num_teams >= MAX_CAPACITY:
        for m in standings[-2:]:
            if m.status == 'active':
                m.status = 'excluded_auto'

    season.status = 'completed'

    _check_ownership_transfer(season, standings)
    db.session.commit()

    _prepare_next_season(season)


def _check_ownership_transfer(season, standings):
    """Transfer ownership if owner inactive 30+ real days before season end."""
    from datetime import datetime
    league = season.league
    owner = league.owner
    if not owner or not owner.last_login:
        return
    if (datetime.utcnow() - owner.last_login).days >= 30 and standings:
        winner_team = standings[0].team
        if winner_team and winner_team.manager:
            league.owner_id = winner_team.manager_id


def _prepare_next_season(completed_season):
    """Create 'forming' season and carry over non-excluded members."""
    from app.models.private_league import PrivateLeagueSeason, PrivateLeagueMembership

    league = completed_season.league
    next_s = PrivateLeagueSeason(
        league_id=league.id,
        season_number=completed_season.season_number + 1,
        status='forming',
    )
    db.session.add(next_s)
    db.session.flush()

    active_mems = PrivateLeagueMembership.query.filter_by(
        season_id=completed_season.id, status='active'
    ).all()
    for m in active_mems:
        db.session.add(PrivateLeagueMembership(
            league_id=league.id,
            season_id=next_s.id,
            team_id=m.team_id,
        ))
    db.session.commit()


# ── Owner exclusion ───────────────────────────────────────────────────────────

def can_owner_exclude(season, target_membership):
    """Returns (allowed: bool, reason: str|None)."""
    from app.models.private_league import PrivateLeagueMembership

    standings = get_standings(season)
    n = len(standings)
    if n == 0:
        return False, 'Classifica vuota.'

    pos = next((i + 1 for i, m in enumerate(standings)
                if m.team_id == target_membership.team_id), None)
    if pos is None:
        return False, 'Squadra non in classifica.'
    if pos <= n // 2:
        return False, 'Puoi escludere solo squadre nella metà inferiore della classifica.'

    forces = [m.team.top7_avg_skill for m in standings if m.team]
    max_force = max(forces) if forces else 0
    target_force = target_membership.team.top7_avg_skill if target_membership.team else 0
    if target_force >= max_force - 4:
        return False, 'Forza della squadra troppo vicina alla massima (soglia: max - 4).'

    already = PrivateLeagueMembership.query.filter_by(
        season_id=season.id, status='excluded_owner'
    ).count()
    if already >= 1:
        return False, 'Hai già usato la tua esclusione discrezionale questa stagione.'

    return True, None


# ── Global event processor (called on page load) ──────────────────────────────

def process_due_league_events():
    """Process due league matches and season transitions. Called on every page load."""
    from app.models.private_league import PrivateLeagueMatch, PrivateLeagueSeason
    from app.utils.gameclock import get_game_day_number, get_game_week_id

    current_day = get_game_day_number()

    # Auto-play due matches
    due = PrivateLeagueMatch.query.filter(
        PrivateLeagueMatch.status == 'scheduled',
        PrivateLeagueMatch.scheduled_game_day <= current_day,
    ).all()

    for match in due:
        try:
            _auto_play_league_match(match)
        except Exception:
            db.session.rollback()
            continue

    if due:
        db.session.commit()

    # Weekly payouts + season finalization for active seasons
    active_seasons = PrivateLeagueSeason.query.filter_by(status='active').all()
    for season in active_seasons:
        try:
            process_weekly_payout(season)
            if season.end_game_day and current_day > season.end_game_day:
                finalize_season(season)
        except Exception:
            db.session.rollback()

    if active_seasons:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
