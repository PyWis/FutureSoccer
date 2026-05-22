"""
match_engine.py — Sunday Friendly Match simulation logic.
"""
import json
import os
import random


def get_goal_coeff():
    """Goal-formula coefficient. With the threshold model (goal when value >= 1)
    a value around 1.0 yields realistic scoring (default 1.0)."""
    return float(os.environ.get('GOAL_COEFF', 1.0))


def get_injury_base():
    """Base injury probability per turn before resistenza/facility reduction (default 0.010)."""
    return float(os.environ.get('INJURY_BASE', 0.010))
from datetime import datetime

_ENGAGEMENT_MODS = {
    'basso': 0.75,
    'moderato': 0.90,
    'normale': 1.00,
    'aggressivo': 1.10,
    'super_aggressivo': 1.15,
}

_BOT_FIRST_NAMES = ['Marco', 'Luigi', 'Giovanni', 'Pietro', 'Antonio',
                    'Sandro', 'Fabio', 'Carlo', 'Pino', 'Dario']
_BOT_LAST_NAMES = ['Rossi', 'Bianchi', 'Ferrari', 'Russo', 'Esposito']


def player_to_dict(player):
    """Convert a SQLAlchemy Player ORM object to a lineup dict."""
    return {
        'player_id': player.id,
        'name': player.name,
        'type': player.type,
        'porta': player.porta,
        'difesa': player.difesa,
        'attacco': player.attacco,
        'resistenza': player.resistenza,
        'freshness': player.freshness,
    }


def build_home_lineup(team, formation):
    """
    Build initial lineup JSON dict from team's saved TeamFormation + Player objects.
    Excludes players with freshness < 2 and tries to fill gaps from reserves.
    """
    from app.models.team import Player

    def load_player(pid):
        if pid is None:
            return None
        p = Player.query.get(pid)
        if p is None or p.team_id != team.id:
            return None
        return p

    # Teams in a ritiro play with freshness pinned to 3 for the whole match.
    in_ritiro = bool(getattr(team, 'ritiro_end_day', 0) and team.ritiro_end_day > 0)
    if in_ritiro:
        def d3(p):
            d = player_to_dict(p)
            d['freshness'] = 3.0
            return d
        gk = load_player(formation.goalkeeper_id)
        defs = [load_player(pid) for pid in formation.defender_ids]
        atts = [load_player(pid) for pid in formation.attacker_ids]
        res = [load_player(pid) for pid in formation.reserve_ids]
        return {
            'engagement': formation.engagement,
            'frozen_freshness': 3.0,
            'goalkeeper': d3(gk) if gk else None,
            'defenders': [d3(p) for p in defs if p is not None],
            'attackers': [d3(p) for p in atts if p is not None],
            'reserves':  [d3(p) for p in res if p is not None],
        }

    # Load all players from formation
    gk_player = load_player(formation.goalkeeper_id)
    defender_players = [load_player(pid) for pid in formation.defender_ids]
    defender_players = [p for p in defender_players if p is not None]
    attacker_players = [load_player(pid) for pid in formation.attacker_ids]
    attacker_players = [p for p in attacker_players if p is not None]
    reserve_players = [load_player(pid) for pid in formation.reserve_ids]
    reserve_players = [p for p in reserve_players if p is not None]

    # Filter reserves to only fresh ones (freshness >= 2)
    available_reserves = [p for p in reserve_players if p.freshness >= 2]
    depleted_reserves = [p for p in reserve_players if p.freshness < 2]

    def maybe_replace(player, role_label):
        """If player has freshness < 2, try to replace with first available reserve."""
        nonlocal available_reserves
        if player is None:
            return None
        if player.freshness >= 2:
            return player
        # Player excluded — try reserve replacement
        if available_reserves:
            replacement = available_reserves.pop(0)
            return replacement
        # No replacement available
        return None

    # Process goalkeeper
    final_gk = maybe_replace(gk_player, 'goalkeeper')

    # Process defenders
    final_defenders = []
    for p in defender_players:
        result = maybe_replace(p, 'defender')
        if result is not None:
            final_defenders.append(result)

    # Process attackers
    final_attackers = []
    for p in attacker_players:
        result = maybe_replace(p, 'attacker')
        if result is not None:
            final_attackers.append(result)

    # Remaining available reserves become actual reserves in the lineup
    final_reserves = list(available_reserves)

    lineup = {
        'engagement': formation.engagement,
        'goalkeeper': player_to_dict(final_gk) if final_gk else None,
        'defenders': [player_to_dict(p) for p in final_defenders],
        'attackers': [player_to_dict(p) for p in final_attackers],
        'reserves': [player_to_dict(p) for p in final_reserves],
    }
    return lineup


def _random_bot_skills():
    """Generate 4 skills averaging to ~2.0, each in [0.5, 2.5]."""
    skills = []
    for _ in range(4):
        s = random.uniform(0.5, 2.5)
        skills.append(round(s, 2))
    # Adjust to get average close to 2.0
    total = sum(skills)
    target_total = 8.0
    diff = target_total - total
    # Distribute the difference evenly
    for i in range(4):
        skills[i] = round(min(2.5, max(0.5, skills[i] + diff / 4)), 2)
    return skills


def _bot_player(pid_str, name):
    skills = _random_bot_skills()
    return {
        'player_id': pid_str,
        'name': name,
        'type': 'uomo',
        'porta': skills[0],
        'difesa': skills[1],
        'attacco': skills[2],
        'resistenza': skills[3],
        'freshness': 10.0,
    }


def generate_bot_lineup():
    """Generate 'Squadra del Bar' lineup with 5 bot players."""
    def rname():
        return random.choice(_BOT_FIRST_NAMES) + ' ' + random.choice(_BOT_LAST_NAMES)

    gk = _bot_player('bot_gk', rname())
    def0 = _bot_player('bot_def_0', rname())
    def1 = _bot_player('bot_def_1', rname())
    att0 = _bot_player('bot_att_0', rname())
    att1 = _bot_player('bot_att_1', rname())

    return {
        'engagement': 'normale',
        'goalkeeper': gk,
        'defenders': [def0, def1],
        'attackers': [att0, att1],
        'reserves': [],
    }


def _pick_scorer(lineup_dict):
    """Pick a random scorer name from players currently on the field, preferring
    attackers, then defenders, then the goalkeeper."""
    for slot in ('attackers', 'defenders'):
        pool = [p for p in (lineup_dict.get(slot) or []) if p and p.get('name')]
        if pool:
            return random.choice(pool)['name']
    gk = lineup_dict.get('goalkeeper')
    if gk and gk.get('name'):
        return gk['name']
    return None


def compute_strength(lineup_dict):
    """Compute {'porta', 'difesa', 'attacco'} for a lineup dict."""
    gk = lineup_dict.get('goalkeeper')
    defenders = lineup_dict.get('defenders') or []
    attackers = lineup_dict.get('attackers') or []
    engagement = lineup_dict.get('engagement', 'normale')

    starters = []
    if gk:
        starters.append(gk)
    starters.extend(defenders)
    starters.extend(attackers)

    porta = gk['porta'] if gk else 2.0

    # Difesa: defenders' difesa + 50% from every other starter's difesa
    others_for_def = [p for p in starters if p not in defenders]
    difesa = sum(p['difesa'] for p in defenders) + 0.5 * sum(p['difesa'] for p in others_for_def)

    # Attacco: attackers' attacco + 50% from every other starter's attacco
    others_for_att = [p for p in starters if p not in attackers]
    attacco = sum(p['attacco'] for p in attackers) + 0.5 * sum(p['attacco'] for p in others_for_att)

    mod = _ENGAGEMENT_MODS.get(engagement, 1.00)

    return {
        'porta': round(porta * mod, 2),
        'difesa': round(difesa * mod, 2),
        'attacco': round(attacco * mod, 2),
    }


def apply_freshness_loss(lineup_dict, delta=-0.2):
    """Reduce freshness of all starters (not reserves) by delta (min 0). Modifies in-place.

    Teams in a ritiro have freshness pinned (frozen_freshness) for the whole
    match, so they neither lose freshness nor get excluded."""
    frozen = lineup_dict.get('frozen_freshness')
    if frozen is not None:
        gk = lineup_dict.get('goalkeeper')
        if gk:
            gk['freshness'] = frozen
        for p in lineup_dict.get('defenders') or []:
            p['freshness'] = frozen
        for p in lineup_dict.get('attackers') or []:
            p['freshness'] = frozen
        return lineup_dict

    gk = lineup_dict.get('goalkeeper')
    if gk:
        gk['freshness'] = round(max(0.0, gk['freshness'] + delta), 2)

    for p in lineup_dict.get('defenders') or []:
        p['freshness'] = round(max(0.0, p['freshness'] + delta), 2)

    for p in lineup_dict.get('attackers') or []:
        p['freshness'] = round(max(0.0, p['freshness'] + delta), 2)

    return lineup_dict


def check_freshness_exclusions(lineup_dict):
    """
    Check all slots. Any player with freshness < 2 is removed.
    If a starter is removed, try to replace from reserves (first with freshness >= 2).
    Returns (modified_lineup_dict, list_of_excluded_names).
    """
    excluded_names = []
    reserves = lineup_dict.get('reserves') or []

    def get_fresh_reserve():
        for i, r in enumerate(reserves):
            if r['freshness'] >= 2:
                return reserves.pop(i)
        return None

    # Check goalkeeper
    gk = lineup_dict.get('goalkeeper')
    if gk and gk['freshness'] < 2:
        excluded_names.append(gk['name'])
        replacement = get_fresh_reserve()
        lineup_dict['goalkeeper'] = replacement  # None if no replacement

    # Check defenders
    new_defenders = []
    for p in lineup_dict.get('defenders') or []:
        if p['freshness'] < 2:
            excluded_names.append(p['name'])
            replacement = get_fresh_reserve()
            if replacement:
                new_defenders.append(replacement)
        else:
            new_defenders.append(p)
    lineup_dict['defenders'] = new_defenders

    # Check attackers
    new_attackers = []
    for p in lineup_dict.get('attackers') or []:
        if p['freshness'] < 2:
            excluded_names.append(p['name'])
            replacement = get_fresh_reserve()
            if replacement:
                new_attackers.append(replacement)
        else:
            new_attackers.append(p)
    lineup_dict['attackers'] = new_attackers

    lineup_dict['reserves'] = reserves
    return lineup_dict, excluded_names


def roll_injuries(lineup_dict, facility_field_stars=0):
    """
    For each starter, roll injury probability.
    Returns (modified_lineup_dict, list of injury events).
    """
    injury_events = []
    reserves = lineup_dict.get('reserves') or []

    def get_fresh_reserve():
        for i, r in enumerate(reserves):
            if r['freshness'] >= 2:
                return reserves.pop(i)
        return None

    def roll_for_player(p):
        prob = max(0.0, get_injury_base() - p['resistenza'] / 2500 - 0.001 * facility_field_stars)
        return random.random() < prob

    # Goalkeeper
    gk = lineup_dict.get('goalkeeper')
    if gk and roll_for_player(gk):
        replacement = get_fresh_reserve()
        malus = round(random.uniform(-15, -5), 1)
        event = {
            'player_name': gk['name'],
            'player_id': gk['player_id'],
            'replaced_by': replacement['name'] if replacement else None,
            'freshness_malus': malus,
        }
        injury_events.append(event)
        lineup_dict['goalkeeper'] = replacement  # None if no replacement

    # Defenders
    new_defenders = []
    for p in list(lineup_dict.get('defenders') or []):
        if roll_for_player(p):
            replacement = get_fresh_reserve()
            malus = round(random.uniform(-15, -5), 1)
            event = {
                'player_name': p['name'],
                'player_id': p['player_id'],
                'replaced_by': replacement['name'] if replacement else None,
                'freshness_malus': malus,
            }
            injury_events.append(event)
            if replacement:
                new_defenders.append(replacement)
        else:
            new_defenders.append(p)
    lineup_dict['defenders'] = new_defenders

    # Attackers
    new_attackers = []
    for p in list(lineup_dict.get('attackers') or []):
        if roll_for_player(p):
            replacement = get_fresh_reserve()
            malus = round(random.uniform(-15, -5), 1)
            event = {
                'player_name': p['name'],
                'player_id': p['player_id'],
                'replaced_by': replacement['name'] if replacement else None,
                'freshness_malus': malus,
            }
            injury_events.append(event)
            if replacement:
                new_attackers.append(replacement)
        else:
            new_attackers.append(p)
    lineup_dict['attackers'] = new_attackers

    lineup_dict['reserves'] = reserves
    return lineup_dict, injury_events


def apply_role_changes(lineup_dict, role_changes):
    """
    Apply role changes to starters.
    role_changes: {str(player_id): 'goalkeeper'|'defender'|'attacker'}
    Moves a starter from their current role slot to the requested slot.
    Only valid target roles are goalkeeper/defender/attacker.
    """
    if not role_changes:
        return lineup_dict

    valid_roles = {'goalkeeper', 'defender', 'attacker'}

    for pid_str, new_role in role_changes.items():
        if new_role not in valid_roles:
            continue
        try:
            pid = int(pid_str)
        except (ValueError, TypeError):
            pid = pid_str  # bot players have string ids

        # Find the player in their current slot
        player = None
        current_role = None

        gk = lineup_dict.get('goalkeeper')
        if gk and gk['player_id'] == pid:
            player = gk
            current_role = 'goalkeeper'

        if player is None:
            for p in lineup_dict.get('defenders') or []:
                if p['player_id'] == pid:
                    player = p
                    current_role = 'defender'
                    break

        if player is None:
            for p in lineup_dict.get('attackers') or []:
                if p['player_id'] == pid:
                    player = p
                    current_role = 'attacker'
                    break

        if player is None or current_role == new_role:
            continue

        # Remove from current slot
        if current_role == 'goalkeeper':
            lineup_dict['goalkeeper'] = None
        elif current_role == 'defender':
            lineup_dict['defenders'] = [p for p in lineup_dict['defenders'] if p['player_id'] != pid]
        elif current_role == 'attacker':
            lineup_dict['attackers'] = [p for p in lineup_dict['attackers'] if p['player_id'] != pid]

        # Add to new slot
        if new_role == 'goalkeeper':
            # If there's already a goalkeeper, demote them to defender
            existing_gk = lineup_dict.get('goalkeeper')
            if existing_gk:
                lineup_dict['defenders'] = lineup_dict.get('defenders') or []
                lineup_dict['defenders'].append(existing_gk)
            lineup_dict['goalkeeper'] = player
        elif new_role == 'defender':
            lineup_dict['defenders'] = lineup_dict.get('defenders') or []
            lineup_dict['defenders'].append(player)
        elif new_role == 'attacker':
            lineup_dict['attackers'] = lineup_dict.get('attackers') or []
            lineup_dict['attackers'].append(player)

    return lineup_dict


def apply_pending_subs(lineup_dict, subs_dict):
    """
    Apply pending substitutions.
    subs_dict format: {"swap": [{"out_id": 123, "in_id": 456}, ...]}
    Silently skips invalid swaps.
    """
    swaps = subs_dict.get('swap') or []
    reserves = lineup_dict.get('reserves') or []

    for swap in swaps:
        out_id = swap.get('out_id')
        in_id = swap.get('in_id')
        if out_id is None or in_id is None:
            continue

        # Find the reserve player to bring in
        reserve_player = None
        reserve_idx = None
        for i, r in enumerate(reserves):
            if r['player_id'] == in_id:
                reserve_player = r
                reserve_idx = i
                break
        if reserve_player is None:
            continue

        # Find the starter player to take out
        # Check goalkeeper
        gk = lineup_dict.get('goalkeeper')
        if gk and gk['player_id'] == out_id:
            reserves[reserve_idx] = gk
            lineup_dict['goalkeeper'] = reserve_player
            continue

        # Check defenders
        swapped = False
        new_defenders = []
        for p in lineup_dict.get('defenders') or []:
            if not swapped and p['player_id'] == out_id:
                reserves[reserve_idx] = p
                new_defenders.append(reserve_player)
                swapped = True
            else:
                new_defenders.append(p)
        if swapped:
            lineup_dict['defenders'] = new_defenders
            continue

        # Check attackers
        new_attackers = []
        for p in lineup_dict.get('attackers') or []:
            if not swapped and p['player_id'] == out_id:
                reserves[reserve_idx] = p
                new_attackers.append(reserve_player)
                swapped = True
            else:
                new_attackers.append(p)
        if swapped:
            lineup_dict['attackers'] = new_attackers

    lineup_dict['reserves'] = reserves
    return lineup_dict


def process_turn(match, facility_field_stars=0):
    """
    Main turn processor. Modifies match in-place.
    Called when a turn needs to advance.
    """
    from app.models.team import Player

    # 1. Parse lineups
    home_lineup = json.loads(match.home_lineup_json or '{}')
    away_lineup = json.loads(match.away_lineup_json or '{}')

    # 2. Apply pending subs + role changes
    home_subs = json.loads(match.home_pending_subs_json or '{}')
    if home_subs:
        home_lineup = apply_pending_subs(home_lineup, home_subs)
        home_lineup = apply_role_changes(home_lineup, home_subs.get('role_changes', {}))
    # Away subs only for a real (human) away team
    if match.away_team_id is not None:
        away_subs = json.loads(match.away_pending_subs_json or '{}')
        if away_subs:
            away_lineup = apply_pending_subs(away_lineup, away_subs)
            away_lineup = apply_role_changes(away_lineup, away_subs.get('role_changes', {}))

    # 3. Apply freshness loss for both lineups
    home_lineup = apply_freshness_loss(home_lineup, delta=-0.2)
    away_lineup = apply_freshness_loss(away_lineup, delta=-0.2)

    # 4. Check freshness exclusions
    home_lineup, home_excluded = check_freshness_exclusions(home_lineup)
    away_lineup, away_excluded = check_freshness_exclusions(away_lineup)

    # 5. Roll injuries
    home_lineup, home_injuries = roll_injuries(home_lineup, facility_field_stars)
    away_lineup, away_injuries = roll_injuries(away_lineup, 0)

    # 6. Compute strengths
    home_str = compute_strength(home_lineup)
    away_str = compute_strength(away_lineup)

    # 7-8. Goal model (per turn, team-aggregate):
    #   Goal = GOAL_COEFF * AttaccoSquadra * rand(0,2) / (DifesaAvv + PortaAvv)
    #   A goal is scored when Goal >= 1. Max one goal per team per turn.
    gc = get_goal_coeff()

    def _goal(att_strength, opp_def, opp_porta):
        denom = opp_def + opp_porta
        rand_factor = random.uniform(0.0, 2.0)
        if denom <= 0:
            return True, float('inf')  # uncontested attack
        value = gc * att_strength * rand_factor / denom
        return value >= 1.0, round(value, 3)

    home_scores, home_goal_val = _goal(home_str['attacco'], away_str['difesa'], away_str['porta'])
    away_scores, away_goal_val = _goal(away_str['attacco'], home_str['difesa'], home_str['porta'])

    # No scoring on the opening turn (T0): the match is just kicking off.
    if match.current_turn == 0:
        home_scores = False
        away_scores = False

    if home_scores:
        match.home_score += 1
    if away_scores:
        match.away_score += 1

    # 9. Build events list
    events = []
    if home_scores:
        scorer = _pick_scorer(home_lineup)
        text = f'GOAL! {scorer} segna per la squadra di casa!' if scorer else 'GOAL! La squadra di casa segna!'
        events.append({'team': 'home', 'type': 'goal', 'text': text})
    if away_scores:
        scorer = _pick_scorer(away_lineup)
        text = f'GOAL! {scorer} segna per la squadra ospite!' if scorer else 'GOAL! La squadra ospite segna!'
        events.append({'team': 'away', 'type': 'goal', 'text': text})

    for name in home_excluded:
        events.append({'team': 'home', 'type': 'freshness', 'text': f'{name} escluso per stanchezza'})
    for name in away_excluded:
        events.append({'team': 'away', 'type': 'freshness', 'text': f'{name} escluso per stanchezza'})

    for inj in home_injuries:
        txt = f'{inj["player_name"]} infortunato'
        if inj['replaced_by']:
            txt += f', sostituito da {inj["replaced_by"]}'
        events.append({'team': 'home', 'type': 'injury', 'text': txt})

    for inj in away_injuries:
        txt = f'{inj["player_name"]} infortunato'
        if inj['replaced_by']:
            txt += f', sostituito da {inj["replaced_by"]}'
        events.append({'team': 'away', 'type': 'injury', 'text': txt})

    # 10. Append turn record
    turns = json.loads(match.turns_json or '[]')
    turn_record = {
        'turn': match.current_turn,
        'home_str': home_str,
        'away_str': away_str,
        'home_goal_val': home_goal_val if home_goal_val != float('inf') else None,
        'away_goal_val': away_goal_val if away_goal_val != float('inf') else None,
        'home_goal': home_scores,
        'away_goal': away_scores,
        'events': events,
    }
    turns.append(turn_record)

    # 11. Accumulate injuries
    all_injuries = json.loads(match.injuries_json or '[]')
    for inj in home_injuries:
        all_injuries.append({'player_id': inj['player_id'], 'malus': inj['freshness_malus']})
    # Away injuries (bot players have string IDs, finalize_match skips them)
    for inj in away_injuries:
        all_injuries.append({'player_id': inj['player_id'], 'malus': inj['freshness_malus']})

    # 12. Update match
    match.home_lineup_json = json.dumps(home_lineup)
    match.away_lineup_json = json.dumps(away_lineup)
    match.turns_json = json.dumps(turns)
    match.injuries_json = json.dumps(all_injuries)
    match.home_pending_subs_json = '{}'
    match.away_pending_subs_json = '{}'
    match.current_turn += 1
    match.last_turn_at = datetime.utcnow()

    # 13. Check end condition
    if match.current_turn == 7:
        # After turn 6: check if scores equal → extra time (turn 7)
        if match.home_score == match.away_score:
            # Extra time — let it continue (current_turn is now 7)
            pass
        else:
            match.status = 'completed'
            finalize_match(match)
    elif match.current_turn > 7:
        # After turn 7: always complete
        match.status = 'completed'
        finalize_match(match)


def finalize_match(match):
    """Apply match end effects to real Player objects."""
    from app import db
    from app.models.team import Player, Team

    # Apply injury maluses (can go negative)
    injuries = json.loads(match.injuries_json or '[]')
    for inj in injuries:
        pid = inj.get('player_id')
        malus = inj.get('malus', 0)
        if isinstance(pid, int):
            player = Player.query.get(pid)
            if player:
                player.freshness = round(player.freshness + malus, 1)

    # Streaming revenue: home team earns 100k per facility_stream star
    home_team = Team.query.get(match.home_team_id)
    if home_team and home_team.facility_stream > 0:
        from app.utils import ledger
        ledger.record(home_team, home_team.facility_stream * 100_000,
                      ledger.CAT_STREAMING, 'Ricavi streaming partita')

    # Social influence: per-home-match bonuses for active effects
    if home_team:
        from app.utils import ledger, social
        state = social.compute_state(home_team)
        mult = state['multiplier']
        match_bonus = 0
        for key in state['active']:
            if state['applies'][key] and not social.SOCIAL_EFFECTS[key].get('doubler'):
                match_bonus += social.SOCIAL_EFFECTS[key]['match_bonus']
        match_bonus *= mult
        if match_bonus > 0:
            ledger.record(home_team, match_bonus, ledger.CAT_SOCIAL,
                          'Influenza: incasso partita in casa')

    db.session.commit()


def _home_ground_stars(match):
    return match.home_team.facility_ground if match.home_team else 0


def advance_match_if_due(match, turn_seconds):
    """Advance one turn if the turn timer has elapsed. Used by the live view and
    by the scheduler so abandoned matches still progress turn by turn."""
    from datetime import datetime as _dt, timedelta as _td
    if match.status != 'active' or match.last_turn_at is None:
        return False
    if _dt.utcnow() >= match.last_turn_at + _td(seconds=turn_seconds):
        process_turn(match, _home_ground_stars(match))
        return True
    return False


def simulate_match_to_completion(match, max_turns=50):
    """Run all remaining turns instantly until the match is completed.
    Used to auto-resolve a Sunday match when neither manager connects."""
    guard = 0
    while match.status == 'active' and guard < max_turns:
        process_turn(match, _home_ground_stars(match))
        guard += 1
