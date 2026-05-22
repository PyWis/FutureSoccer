"""Social system: per-player channels, hidden charisma and team influence.

Player influence = (open channels * avg skill * max skill * charisma) / 100.
Team influence points = floor of the sum of all players' influence.
With this scaling the effect thresholds (2 → 20) are reachable as a team
grows, and the 20-point "Squadra Rosa" stays an end-game goal for all-women
squads (women have the highest charisma range).
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

# Effect catalogue. Bonuses:
#   match_bonus       → € credited on each completed home match
#   monthly_money     → € credited on the 1st of each game month
#   monthly_resistenza→ +X resistenza to every player on the 1st of the month
#   monthly_green_bond→ a free Green bond granted on the 1st of the month
#   women_only        → only activatable if the whole squad is women
SOCIAL_EFFECTS = {
    'posti_live':     {'label': 'Posti stadio live',     'icon': '🎟️', 'threshold': 2,
                       'desc': '+€100k per ogni partita in casa',
                       'match_bonus': 100_000, 'monthly_money': 0, 'monthly_resistenza': 0.0,
                       'monthly_green_bond': False, 'women_only': False},
    'merch_base':     {'label': 'Merchandising base',    'icon': '🧢', 'threshold': 5,
                       'desc': '+€500k ogni mese',
                       'match_bonus': 0, 'monthly_money': 500_000, 'monthly_resistenza': 0.0,
                       'monthly_green_bond': False, 'women_only': False},
    'interviste':     {'label': 'Circuito intervista',   'icon': '🎤', 'threshold': 7,
                       'desc': '+0,2 resistenza a giocatore ogni mese',
                       'match_bonus': 0, 'monthly_money': 0, 'monthly_resistenza': 0.2,
                       'monthly_green_bond': False, 'women_only': False},
    'merch_adv':      {'label': 'Merchandising avanzato', 'icon': '👕', 'threshold': 9,
                       'desc': '+€1M ogni mese',
                       'match_bonus': 0, 'monthly_money': 1_000_000, 'monthly_resistenza': 0.0,
                       'monthly_green_bond': False, 'women_only': False},
    'social_channel': {'label': 'Canale social squadra', 'icon': '📡', 'threshold': 10,
                       'desc': 'Cedola Green gratis ogni mese',
                       'match_bonus': 0, 'monthly_money': 0, 'monthly_resistenza': 0.0,
                       'monthly_green_bond': True, 'women_only': False},
    'rivista':        {'label': 'Rivista sport',         'icon': '📰', 'threshold': 12,
                       'desc': '+€200k per partita in casa · Cedola Green gratis ogni mese',
                       'match_bonus': 200_000, 'monthly_money': 0, 'monthly_resistenza': 0.0,
                       'monthly_green_bond': True, 'women_only': False},
    'squadra_rosa':   {'label': 'Squadra Rosa',          'icon': '🌹', 'threshold': 20,
                       'desc': 'Solo squadre tutte donne: +0,2 resistenza/giocatore ogni mese · '
                               '+€200k per partita in casa · Cedola Green gratis ogni mese',
                       'match_bonus': 200_000, 'monthly_money': 0, 'monthly_resistenza': 0.2,
                       'monthly_green_bond': True, 'women_only': True},
}


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
    total = sum(player_influence(p) for p in team.players.all())
    return int(total)


def is_all_women(team):
    players = team.players.all()
    return len(players) > 0 and all(p.type == 'donna' for p in players)


def get_active_effects(team):
    try:
        data = json.loads(team.social_effects_json or '[]')
    except (ValueError, TypeError):
        return []
    return [k for k in data if k in SOCIAL_EFFECTS]


def set_active_effects(team, keys):
    team.social_effects_json = json.dumps(keys)


def effect_applies(team, key, points=None):
    """True if the effect is selected, its threshold is met and women-only is satisfied."""
    if key not in get_active_effects(team):
        return False
    spec = SOCIAL_EFFECTS.get(key)
    if not spec:
        return False
    if points is None:
        points = team_influence_points(team)
    if points < spec['threshold']:
        return False
    if spec['women_only'] and not is_all_women(team):
        return False
    return True
