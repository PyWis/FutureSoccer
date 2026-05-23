from flask import Blueprint, render_template
from flask_login import login_required, current_user

from app.utils.championship_engine import (
    get_or_create_current_season, get_group_standings, TIER_ORDER,
)

championship_bp = Blueprint('championship', __name__)


@championship_bp.route('/')
@login_required
def index():
    season = get_or_create_current_season()

    my_team = getattr(current_user, 'team', None)
    my_group = None
    my_standings = []
    if season and my_team:
        from app.models.championship import ChampionshipMembership
        mem = ChampionshipMembership.query.filter_by(
            season_id=season.id, team_id=my_team.id).first()
        if mem:
            my_group = mem.group
            my_standings = get_group_standings(my_group)

    # All groups by tier (high → low) for the pyramid overview.
    tiers = []
    if season:
        order = list(reversed(TIER_ORDER))  # elite first
        groups_by_tier = {t: [] for t in order}
        for g in season.groups:
            groups_by_tier.setdefault(g.tier, []).append(g)
        for tier in order:
            grps = sorted(groups_by_tier.get(tier, []), key=lambda g: g.group_index)
            if grps:
                tiers.append((tier, [(g, get_group_standings(g)) for g in grps]))

    # July annual finals: show brackets if any tournaments exist for this season.
    from app.utils.gameclock import get_game_season
    from app.models.championship import Tournament
    tournaments = []
    tour_objs = Tournament.query.filter_by(season=get_game_season()).all()
    kind_order = {'main': 0, 'secondary': 1, 'supercoppa': 2}
    for t in sorted(tour_objs, key=lambda x: kind_order.get(x.kind, 9)):
        rounds = {}
        for m in t.matches:
            rounds.setdefault(m.round_index, []).append(m)
        ordered = [(r, sorted(rounds[r], key=lambda m: m.slot_index)) for r in sorted(rounds)]
        tournaments.append((t, ordered))

    return render_template(
        'championship/index.html',
        season=season, my_team=my_team, my_group=my_group,
        my_standings=my_standings, tiers=tiers, tournaments=tournaments,
    )
