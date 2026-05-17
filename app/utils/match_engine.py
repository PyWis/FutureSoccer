"""
match_engine.py — Sunday Friendly Match simulation logic.
"""
import json
import random
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
    """Reduce freshness of all starters (not reserves) by delta (min 0). Modifies in-place."""
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
        prob = max(0.0, 0.010 - p['resistenza'] / 2500 - 0.001 * facility_field_stars)
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
    # Away subs only if real away team
    if match.away_team_id is not None:
        # For simplicity, away team doesn't submit subs via this flow
        pass

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

    # 7. Compute valore_goal
    home_denom = away_str['difesa'] + away_str['attacco']
    away_denom = home_str['difesa'] + home_str['attacco']

    home_vg = home_str['attacco'] / home_denom if home_denom > 0 else 2.0
    away_vg = away_str['attacco'] / away_denom if away_denom > 0 else 2.0

    # 8. Roll goals
    home_scores = (random.random() < min(0.3 * home_vg, 0.95)) and (home_vg < 2.0)
    away_scores = (random.random() < min(0.3 * away_vg, 0.95)) and (away_vg < 2.0)

    if home_scores:
        match.home_score += 1
    if away_scores:
        match.away_score += 1

    # 9. Build events list
    events = []
    if home_scores:
        events.append({'team': 'home', 'type': 'goal', 'text': 'GOAL! La squadra di casa segna!'})
    if away_scores:
        events.append({'team': 'away', 'type': 'goal', 'text': 'GOAL! La squadra ospite segna!'})

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
        'home_vg': round(home_vg, 3),
        'away_vg': round(away_vg, 3),
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
    from app.models.team import Player

    # Update freshness of all home players from their end-of-match lineup snapshot
    home_lineup = json.loads(match.home_lineup_json or '{}')
    all_home_players = []
    gk = home_lineup.get('goalkeeper')
    if gk:
        all_home_players.append(gk)
    all_home_players.extend(home_lineup.get('defenders') or [])
    all_home_players.extend(home_lineup.get('attackers') or [])
    all_home_players.extend(home_lineup.get('reserves') or [])

    for p_dict in all_home_players:
        pid = p_dict.get('player_id')
        if isinstance(pid, int):
            player = Player.query.get(pid)
            if player and player.team_id == match.home_team_id:
                player.freshness = round(p_dict['freshness'], 1)

    # Apply injury maluses on top of end-of-match freshness (can go negative)
    injuries = json.loads(match.injuries_json or '[]')
    for inj in injuries:
        pid = inj.get('player_id')
        malus = inj.get('malus', 0)
        if isinstance(pid, int):
            player = Player.query.get(pid)
            if player:
                player.freshness = round(player.freshness + malus, 1)

    db.session.commit()
