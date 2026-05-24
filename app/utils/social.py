"""Social system: per-player channels, hidden charisma and team influence.

Player influence = (open channels * avg skill * max skill * charisma) / 100.
Team influence points = floor of the sum of all players' influence.

Influence is a spendable budget: activating an effect costs (and reserves)
its threshold in points. An effect's bonuses apply only while the team's
total influence still covers the sum of all active effects' costs and the
team-type constraint holds. "Doubler" effects double every other active
bonus.
"""
import json
import random

# (key, label, icon) — each open channel drains freshness weekly (Monday)
SOCIAL_CHANNELS = [
    ('instok',      'Instok',      '📸'),
    ('sportsocial', 'SportSocial', '🏟️'),
    ('fantasoccer', 'FantaSoccer', '🎮'),
]
CHANNEL_KEYS = [c[0] for c in SOCIAL_CHANNELS]
CHANNEL_FRESHNESS_COST = 0.5  # per open channel, per week

# Hidden charisma range by player type (min, max inclusive)
CARISMA_RANGE = {
    'uomo':  (1, 8),
    'cyber': (1, 5),
    'donna': (4, 12),
}

MAX_ACTIVE_EFFECTS = 3
EFFECT_RELOCK_DAYS = 180   # an effect off for >=180 game days can't be reactivated
CHANNEL_REOPEN_COOLDOWN_DAYS = 90  # a closed channel can't reopen for 90 game days

# Effect catalogue. Bonuses:
#   match_bonus        → € on each completed home match
#   monthly_money      → € on the 1st of each game month
#   monthly_resistenza → +X resistenza to every player on the 1st
#   monthly_white_bond → free White bond(s) on the 1st
#   requires           → None | 'women' | 'cyber' | 'lite'
#                        | 'all_instok' | 'all_sportsocial' | 'all_fantasoccer'
#   doubler            → if True, doubles every OTHER active effect's bonus
SOCIAL_EFFECTS = {
    'all_instok':     {'label': 'Boom Instok',           'icon': '📸', 'threshold': 10,
                       'desc': 'Solo se TUTTI i giocatori sono attivi su Instok: +€5M ogni mese',
                       'match_bonus': 0, 'monthly_money': 5_000_000, 'monthly_resistenza': 0.0,
                       'monthly_white_bond': False, 'requires': 'all_instok', 'doubler': False},
    'all_sportsocial':{'label': 'Boom SportSocial',      'icon': '🏟️', 'threshold': 10,
                       'desc': 'Solo se TUTTI i giocatori sono attivi su SportSocial: +€5M ogni mese',
                       'match_bonus': 0, 'monthly_money': 5_000_000, 'monthly_resistenza': 0.0,
                       'monthly_white_bond': False, 'requires': 'all_sportsocial', 'doubler': False},
    'all_fantasoccer':{'label': 'Boom FantaSoccer',      'icon': '🎮', 'threshold': 10,
                       'desc': 'Solo se TUTTI i giocatori sono attivi su FantaSoccer: +€5M ogni mese',
                       'match_bonus': 0, 'monthly_money': 5_000_000, 'monthly_resistenza': 0.0,
                       'monthly_white_bond': False, 'requires': 'all_fantasoccer', 'doubler': False},
    'posti_live':     {'label': 'Posti stadio live',     'icon': '🎟️', 'threshold': 5,
                       'desc': '+€100k per ogni partita in casa',
                       'match_bonus': 100_000, 'monthly_money': 0, 'monthly_resistenza': 0.0,
                       'monthly_white_bond': False, 'requires': None, 'doubler': False},
    'merch_base':     {'label': 'Merchandising base',    'icon': '🧢', 'threshold': 12,
                       'desc': '+€500k ogni mese',
                       'match_bonus': 0, 'monthly_money': 500_000, 'monthly_resistenza': 0.0,
                       'monthly_white_bond': False, 'requires': None, 'doubler': False},
    'interviste':     {'label': 'Circuito intervista',   'icon': '🎤', 'threshold': 20,
                       'desc': '+0,2 resistenza a giocatore ogni mese',
                       'match_bonus': 0, 'monthly_money': 0, 'monthly_resistenza': 0.2,
                       'monthly_white_bond': False, 'requires': None, 'doubler': False},
    'merch_adv':      {'label': 'Merchandising avanzato', 'icon': '👕', 'threshold': 25,
                       'desc': '+€1M ogni mese',
                       'match_bonus': 0, 'monthly_money': 1_000_000, 'monthly_resistenza': 0.0,
                       'monthly_white_bond': False, 'requires': None, 'doubler': False},
    'social_channel': {'label': 'Canale social squadra', 'icon': '📡', 'threshold': 30,
                       'desc': 'Cedola White gratis ogni mese',
                       'match_bonus': 0, 'monthly_money': 0, 'monthly_resistenza': 0.0,
                       'monthly_white_bond': True, 'requires': None, 'doubler': False},
    'rivista':        {'label': 'Rivista sport',         'icon': '📰', 'threshold': 40,
                       'desc': '+€200k per partita in casa · Cedola White gratis ogni mese',
                       'match_bonus': 200_000, 'monthly_money': 0, 'monthly_resistenza': 0.0,
                       'monthly_white_bond': True, 'requires': None, 'doubler': False},
    'girl_power':     {'label': 'Canale Social: Team Girl Power', 'icon': '🌹', 'threshold': 60,
                       'desc': 'Solo squadre tutte donne: +0,2 resistenza/giocatore ogni mese · '
                               '+€200k per partita in casa · Cedola White gratis ogni mese',
                       'match_bonus': 200_000, 'monthly_money': 0, 'monthly_resistenza': 0.2,
                       'monthly_white_bond': True, 'requires': 'women', 'doubler': False},
    'ai_soccer':      {'label': 'Squadra AiSoccer',      'icon': '🤖', 'threshold': 60,
                       'desc': 'Solo squadre tutte cyber: raddoppia gli altri bonus attivi',
                       'match_bonus': 0, 'monthly_money': 0, 'monthly_resistenza': 0.0,
                       'monthly_white_bond': False, 'requires': 'cyber', 'doubler': True},
    'squadra_lite':   {'label': 'Squadra lite',          'icon': '🪶', 'threshold': 60,
                       'desc': 'Solo squadre con 8 o meno componenti: raddoppia gli altri bonus attivi',
                       'match_bonus': 0, 'monthly_money': 0, 'monthly_resistenza': 0.0,
                       'monthly_white_bond': False, 'requires': 'lite', 'doubler': True},
}

LITE_MAX_PLAYERS = 8


def roll_carisma(player_type):
    lo, hi = CARISMA_RANGE.get(player_type, (1, 8))
    return random.randint(lo, hi)


def channel_count(player):
    return sum(1 for k in CHANNEL_KEYS if getattr(player, f'social_{k}', False))


def player_influence(player):
    n = channel_count(player)
    if n == 0:
        return 0.0
    skills = [player.porta, player.difesa, player.attacco, player.resistenza]
    avg = sum(skills) / 4
    mx = max(skills)
    carisma = player.carisma or 1
    return n * avg * mx * carisma / 100.0


def team_influence_points(team):
    return int(sum(player_influence(p) for p in team.players.all()))


def is_all_women(team):
    players = team.players.all()
    return len(players) > 0 and all(p.type == 'donna' for p in players)


def is_all_cyber(team):
    players = team.players.all()
    return len(players) > 0 and all(p.type == 'cyber' for p in players)


def is_lite(team):
    return 0 < team.players.count() <= LITE_MAX_PLAYERS


def all_channel_open(team, channel_key):
    players = team.players.all()
    return len(players) > 0 and all(getattr(p, f'social_{channel_key}', False) for p in players)


def meets_constraint(team, requires):
    if requires is None:
        return True
    if requires == 'women':
        return is_all_women(team)
    if requires == 'cyber':
        return is_all_cyber(team)
    if requires == 'lite':
        return is_lite(team)
    if requires == 'all_instok':
        return all_channel_open(team, 'instok')
    if requires == 'all_sportsocial':
        return all_channel_open(team, 'sportsocial')
    if requires == 'all_fantasoccer':
        return all_channel_open(team, 'fantasoccer')
    return True


def get_active_effects(team):
    try:
        data = json.loads(team.social_effects_json or '[]')
    except (ValueError, TypeError):
        return []
    return [k for k in data if k in SOCIAL_EFFECTS]


def set_active_effects(team, keys):
    team.social_effects_json = json.dumps(keys)


# ── 180-day effect relock tracking ────────────────────────────────────────────

def _deactivated_map(team):
    try:
        data = json.loads(team.social_deactivated_json or '{}')
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_deactivated_map(team, m):
    team.social_deactivated_json = json.dumps(m)


def mark_deactivated(team, key, current_day):
    m = _deactivated_map(team)
    m[key] = current_day
    _save_deactivated_map(team, m)


def clear_deactivated(team, key):
    m = _deactivated_map(team)
    if key in m:
        del m[key]
        _save_deactivated_map(team, m)


def is_effect_locked(team, key, current_day):
    """An effect deactivated for >= EFFECT_RELOCK_DAYS can never be reactivated."""
    if key in get_active_effects(team):
        return False
    m = _deactivated_map(team)
    if key not in m:
        return False
    return (current_day - m[key]) >= EFFECT_RELOCK_DAYS


def enforce_affordability(team, current_day):
    """While available influence is negative, deactivate the most expensive
    active effect. Returns the list of effects that were turned off."""
    removed = []
    active = get_active_effects(team)
    total = team_influence_points(team)
    committed = sum(SOCIAL_EFFECTS[k]['threshold'] for k in active)
    while active and committed > total:
        victim = max(active, key=lambda k: SOCIAL_EFFECTS[k]['threshold'])
        active.remove(victim)
        mark_deactivated(team, victim, current_day)
        removed.append(victim)
        committed -= SOCIAL_EFFECTS[victim]['threshold']
    if removed:
        set_active_effects(team, active)
    return removed


# ── 90-day per-player channel reopen cooldown ─────────────────────────────────

def _player_cooldowns(player):
    try:
        data = json.loads(getattr(player, 'social_cooldown_json', None) or '{}')
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def channel_reopen_day(player, channel_key):
    """Game day on which a closed channel becomes reopenable, or None."""
    cd = _player_cooldowns(player)
    if channel_key in cd:
        return cd[channel_key] + CHANNEL_REOPEN_COOLDOWN_DAYS
    return None


def can_reopen_channel(player, channel_key, current_day):
    reopen = channel_reopen_day(player, channel_key)
    return reopen is None or current_day >= reopen


def record_channel_closed(player, channel_key, current_day):
    cd = _player_cooldowns(player)
    cd[channel_key] = current_day
    player.social_cooldown_json = json.dumps(cd)


def clear_channel_cooldown(player, channel_key):
    cd = _player_cooldowns(player)
    if channel_key in cd:
        del cd[channel_key]
        player.social_cooldown_json = json.dumps(cd)


def compute_state(team):
    """Return the full influence/effects state for a team."""
    total = team_influence_points(team)
    active = get_active_effects(team)
    committed = sum(SOCIAL_EFFECTS[k]['threshold'] for k in active)
    affordable = total >= committed
    applies = {}
    for k in active:
        applies[k] = affordable and meets_constraint(team, SOCIAL_EFFECTS[k].get('requires'))
    doublers = sum(1 for k in active if SOCIAL_EFFECTS[k].get('doubler') and applies[k])
    return {
        'total': total,
        'committed': committed,
        'available': total - committed,
        'affordable': affordable,
        'active': active,
        'applies': applies,
        'multiplier': 2 ** doublers,
    }
