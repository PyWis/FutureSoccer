"""Public monthly championship engine.

Design: every group is always exactly GROUP_SIZE teams. Player teams move by a
simple, communicable rule (group winner promoted, bottom 2 relegated; Elite has
no promotion, Gold sends its 2 best group winners up via ranking). Bot teams are
the elastic buffer: they are created/demoted each month so every instantiated
tier is full and every group has 6 teams. Bots flow through the pyramid and are
promoted/relegated exactly like player teams, so the world feels alive and the
difficulty rises as you climb.
"""
import random

from app import db
from app.utils.league_engine import _berger_rounds  # reuse round-robin builder

# ── Constants ────────────────────────────────────────────────────────────────
GROUP_SIZE = 6
RELEGATE_PER_GROUP = 2

# low → high
TIER_ORDER = ['iron', 'bronze', 'silver', 'gold', 'elite']
# fixed group counts per tier (iron is dynamic)
TIER_GROUPS = {'elite': 1, 'gold': 3, 'silver': 9, 'bronze': 27}
# bot roster average skill per tier (power gradient up the pyramid)
TIER_BOT_AVG = {'iron': 2.2, 'bronze': 2.8, 'silver': 3.3, 'gold': 3.8, 'elite': 4.3}
# how many Gold group winners are promoted to Elite (top-N by ranking)
GOLD_PROMOTE_TO_ELITE = 2

ROSTER_SIZE = 7


def _tier_up(tier):
    i = TIER_ORDER.index(tier)
    return TIER_ORDER[i + 1] if i + 1 < len(TIER_ORDER) else None


def _tier_down(tier):
    i = TIER_ORDER.index(tier)
    return TIER_ORDER[i - 1] if i - 1 >= 0 else None


def _tier_capacity(tier):
    return TIER_GROUPS.get(tier, 0) * GROUP_SIZE


# ── Bot generation ─────────────────────────────────────────────────────────────

_BOT_PREFIX = ['AC', 'FC', 'AS', 'US', 'SC', 'Real', 'Inter', 'Atletico', 'Dynamo', 'Neo']
_BOT_CITY = ['Neoroma', 'Cybermilano', 'Novanapoli', 'Astratorino', 'Quantumgenova',
             'Helibologna', 'Vortexpalermo', 'Plasmafirenze', 'Ionvenezia', 'Fluxbari',
             'Synthverona', 'Voltcatania', 'Nebulapadova', 'Pulsartrieste', 'Arcobrescia']


def _unique_bot_name():
    from app.models.team import Team
    for _ in range(50):
        name = f'{random.choice(_BOT_PREFIX)} {random.choice(_BOT_CITY)}'
        if not Team.query.filter_by(name=name).first():
            return name
    # Fallback: guaranteed-unique suffix
    return f'Bot {random.randint(10 ** 6, 10 ** 7)}'


def _build_bot_formation(team_id, players):
    """Pick GK / defenders / attackers from a bot roster and save a TeamFormation."""
    import json
    from app.models.game import TeamFormation

    gk = max(players, key=lambda p: p.porta)
    rest = [p for p in players if p.id != gk.id]
    defenders = sorted(rest, key=lambda p: p.difesa, reverse=True)[:3]
    rem = [p for p in rest if p not in defenders]
    attackers = sorted(rem, key=lambda p: p.attacco, reverse=True)[:3]
    reserves = [p for p in rem if p not in attackers]

    db.session.add(TeamFormation(
        team_id=team_id,
        engagement='normale',
        goalkeeper_id=gk.id,
        defender_ids_json=json.dumps([p.id for p in defenders]),
        attacker_ids_json=json.dumps([p.id for p in attackers]),
        reserve_ids_json=json.dumps([p.id for p in reserves]),
    ))


def create_bot_team(tier):
    """Create a persistent bot Team (no manager) with a roster scaled to the tier."""
    from app.models.team import Team, Player
    from app.utils.generators import _generate_skills, _random_type, MAX_SKILL_ABSOLUTE
    from app.utils.social import roll_carisma

    avg = TIER_BOT_AVG.get(tier, 2.2)
    team = Team(
        name=_unique_bot_name(),
        city=random.choice(_BOT_CITY),
        stadium='Arena Neutrale',
        is_bot=True,
        current_tier=tier,
        manager_id=None,
    )
    db.session.add(team)
    db.session.flush()

    players = []
    for _ in range(ROSTER_SIZE):
        ptype = _random_type()
        skills = _generate_skills(avg, max_val=min(MAX_SKILL_ABSOLUTE, avg + 1.5))
        p = Player(
            name=f'{team.name[:3].upper()}-{random.randint(1, 99):02d}',
            type=ptype,
            age=random.randint(18, 30),
            porta=skills[0], difesa=skills[1], attacco=skills[2], resistenza=skills[3],
            carisma=roll_carisma(ptype),
            is_free_agent=False,
            team_id=team.id,
        )
        db.session.add(p)
        players.append(p)
    db.session.flush()

    _build_bot_formation(team.id, players)
    return team


def _refresh_bot_freshness(team):
    """Bots don't recover via the normal event loop; reset each month so they
    never auto-exclude over time."""
    for p in team.players.all():
        p.freshness = 10.0


# ── Group composition ──────────────────────────────────────────────────────────

def _competing_teams_by_tier():
    """All teams that take part in the public championship, grouped by current_tier.

    Includes player teams (have a manager) and persistent bots.
    """
    from app.models.team import Team
    teams = Team.query.filter(
        db.or_(Team.is_bot == True, Team.manager_id != None)  # noqa: E712
    ).all()
    by_tier = {t: [] for t in TIER_ORDER}
    for tm in teams:
        tier = tm.current_tier if tm.current_tier in TIER_ORDER else 'iron'
        by_tier[tier].append(tm)
    return by_tier


def compose_groups(season, rng):
    """Create groups + memberships for the season, normalising each instantiated
    tier to full groups of 6 using bots as the buffer. Tiers materialise on demand:
    a fixed tier is only built if it holds at least one player team; Iron is always
    built as the entry point. Returns True if at least one group was created.
    """
    from app.models.championship import ChampionshipGroup, ChampionshipMembership

    by_tier = _competing_teams_by_tier()

    def _has_player(team_list):
        return any(not t.is_bot for t in team_list)

    created_any = False

    # Fixed tiers top-down so demoted overflow cascades into lower tiers.
    for tier in ['elite', 'gold', 'silver', 'bronze']:
        pool = by_tier[tier]
        capacity = _tier_capacity(tier)

        if not _has_player(pool):
            # No player here: recycle any bots down a tier instead of wasting them.
            lower = _tier_down(tier)
            for t in pool:
                t.current_tier = lower
                by_tier[lower].append(t)
            by_tier[tier] = []
            continue

        # Overflow: keep player teams (oldest first), demote bots first then the
        # newest player teams. Sorting players-oldest → players-newest → bots puts
        # the demotion candidates at the tail, which the slice below removes.
        if len(pool) > capacity:
            from datetime import datetime
            pool.sort(key=lambda t: (t.is_bot, t.created_at or datetime.min))
            overflow = pool[capacity:]
            pool = pool[:capacity]
            lower = _tier_down(tier)
            for t in overflow:
                t.current_tier = lower
                by_tier[lower].append(t)

        # Deficit: create bots to fill.
        while len(pool) < capacity:
            pool.append(create_bot_team(tier))

        by_tier[tier] = pool
        _materialise_tier(season, tier, pool, rng)
        created_any = True

    # Iron: dynamic. Always instantiate if anyone is there (round up to a full group).
    iron_pool = by_tier['iron']
    if iron_pool:
        deficit = (-len(iron_pool)) % GROUP_SIZE
        for _ in range(deficit):
            iron_pool.append(create_bot_team('iron'))
        _materialise_tier(season, 'iron', iron_pool, rng)
        created_any = True

    return created_any


def _materialise_tier(season, tier, teams, rng):
    """Split `teams` into groups of 6, create groups/memberships, build calendar."""
    from app.models.championship import ChampionshipGroup, ChampionshipMembership

    rng.shuffle(teams)
    for gi in range(0, len(teams), GROUP_SIZE):
        chunk = teams[gi:gi + GROUP_SIZE]
        group = ChampionshipGroup(
            season_id=season.id, tier=tier, group_index=gi // GROUP_SIZE,
        )
        db.session.add(group)
        db.session.flush()

        for t in chunk:
            if t.is_bot:
                _refresh_bot_freshness(t)
            db.session.add(ChampionshipMembership(
                season_id=season.id, group_id=group.id, team_id=t.id,
                tiebreak_random=rng.randint(1, 10 ** 9),
            ))
        db.session.flush()
        _generate_group_calendar(season, group, [t.id for t in chunk], rng)


# ── Calendar ────────────────────────────────────────────────────────────────────

def _generate_group_calendar(season, group, team_ids, rng):
    """Single round-robin; non-final rounds on distinct random days within the
    month, final round pinned to the fixed last matchday (the 28th)."""
    from app.models.championship import ChampionshipMatch

    if len(team_ids) < 2:
        return
    rounds = _berger_rounds(team_ids)          # N-1 rounds for N teams
    non_final = rounds[:-1]
    final = rounds[-1]

    window = list(range(season.start_game_day, season.last_matchday_game_day))
    if len(window) >= len(non_final):
        days = sorted(rng.sample(window, len(non_final)))
    else:
        days = [season.start_game_day + i for i in range(len(non_final))]

    for idx, round_pairs in enumerate(non_final):
        for home_id, away_id in round_pairs:
            db.session.add(ChampionshipMatch(
                season_id=season.id, group_id=group.id,
                home_team_id=home_id, away_team_id=away_id,
                round_number=idx + 1, scheduled_game_day=days[idx],
            ))

    for home_id, away_id in final:
        db.session.add(ChampionshipMatch(
            season_id=season.id, group_id=group.id,
            home_team_id=home_id, away_team_id=away_id,
            round_number=len(rounds), is_final_round=True,
            scheduled_game_day=season.last_matchday_game_day,
        ))


# ── Match auto-play ──────────────────────────────────────────────────────────────

def _auto_play_match(match):
    import json
    from app.models.team import Team
    from app.models.game import TeamFormation
    from app.utils.league_engine import _MockMatch
    from app.utils.match_engine import (
        build_home_lineup, generate_bot_lineup, simulate_match_to_completion,
    )

    home = Team.query.get(match.home_team_id)
    away = Team.query.get(match.away_team_id)
    if not home or not away:
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

    _update_standings(match)


def _update_standings(match):
    from app.models.championship import ChampionshipMembership

    hm = ChampionshipMembership.query.filter_by(
        season_id=match.season_id, team_id=match.home_team_id).first()
    am = ChampionshipMembership.query.filter_by(
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


# ── Standings ────────────────────────────────────────────────────────────────────

def get_group_standings(group):
    """points → goal diff → goals for → tiebreak_random."""
    mems = list(group.memberships)
    return sorted(
        mems,
        key=lambda m: (-m.points, -(m.goals_for - m.goals_against), -m.goals_for, m.tiebreak_random),
    )


# ── Season lifecycle ─────────────────────────────────────────────────────────────

def get_or_create_current_season():
    """Return the active ChampionshipSeason for the current game month, creating
    and populating it on first access. Returns None outside competition months."""
    from app.models.championship import ChampionshipSeason
    from app.utils.gameclock import (
        get_game_month_id, is_competition_month,
        get_month_start_game_day, get_month_last_matchday_game_day, get_month_end_game_day,
    )

    if not is_competition_month():
        return None

    month_id = get_game_month_id()
    s = ChampionshipSeason.query.filter_by(month_id=month_id).first()
    if s:
        return s

    s = ChampionshipSeason(
        month_id=month_id,
        status='forming',
        start_game_day=get_month_start_game_day(),
        last_matchday_game_day=get_month_last_matchday_game_day(),
        end_game_day=get_month_end_game_day(),
        tiebreak_seed=random.randint(1, 10 ** 9),
    )
    db.session.add(s)
    db.session.flush()

    rng = random.Random(s.tiebreak_seed)
    if compose_groups(s, rng):
        s.status = 'active'
    else:
        s.status = 'completed'   # nobody to compete
    db.session.commit()
    return s


def finalize_month(season):
    """Assign final positions and apply promotions/relegations to Team.current_tier.

    Per-group rule: winner promoted one tier, bottom 2 relegated one tier. Elite has
    no promotion (champion stays); Gold sends its 2 best group winners up to Elite.
    Iron has no relegation (it is the entry tier). Bots move exactly like players.
    """
    from app.models.championship import ChampionshipGroup

    groups = ChampionshipGroup.query.filter_by(season_id=season.id).all()
    gold_winners = []

    for group in groups:
        standings = get_group_standings(group)
        for pos, m in enumerate(standings, 1):
            m.final_position = pos
            m.outcome = 'stay'

        n = len(standings)
        tier = group.tier

        # Relegation: bottom 2 (every tier except Iron).
        if tier != 'iron' and n > RELEGATE_PER_GROUP:
            down = _tier_down(tier)
            for m in standings[-RELEGATE_PER_GROUP:]:
                m.outcome = 'relegated'
                if m.team:
                    m.team.current_tier = down

        # Promotion of the group winner (Gold handled collectively below).
        if n >= 1 and tier != 'elite':
            winner = standings[0]
            if tier == 'gold':
                gold_winners.append(winner)
            else:
                up = _tier_up(tier)
                if up:
                    winner.outcome = 'promoted'
                    if winner.team:
                        winner.team.current_tier = up

    # Gold → Elite: only the best GOLD_PROMOTE_TO_ELITE group winners go up.
    gold_winners.sort(
        key=lambda m: (-m.points, -(m.goals_for - m.goals_against), -m.goals_for, m.tiebreak_random)
    )
    for m in gold_winners[:GOLD_PROMOTE_TO_ELITE]:
        m.outcome = 'promoted'
        if m.team:
            m.team.current_tier = 'elite'

    season.status = 'completed'


# ── Driver (called on page load and from the scheduler) ──────────────────────────

def process_due_championship_events():
    """Idempotent: create the month's season, auto-play due matches, finalise
    seasons whose last matchday has passed. Safe to call on every request."""
    from app.models.championship import ChampionshipSeason, ChampionshipMatch
    from app.utils.gameclock import get_game_day_number

    current_day = get_game_day_number()

    # Make sure the current month's season exists (only in competition months).
    get_or_create_current_season()

    # Auto-play due matches across active seasons.
    due = ChampionshipMatch.query.join(
        ChampionshipSeason, ChampionshipMatch.season_id == ChampionshipSeason.id
    ).filter(
        ChampionshipSeason.status == 'active',
        ChampionshipMatch.status == 'scheduled',
        ChampionshipMatch.scheduled_game_day <= current_day,
    ).all()

    played = False
    for match in due:
        try:
            _auto_play_match(match)
            played = True
        except Exception:
            db.session.rollback()
            continue
    if played:
        db.session.commit()

    # Finalise active seasons past their last matchday.
    active = ChampionshipSeason.query.filter_by(status='active').all()
    for season in active:
        try:
            if season.last_matchday_game_day is not None and current_day > season.last_matchday_game_day:
                finalize_month(season)
        except Exception:
            db.session.rollback()
    if active:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
