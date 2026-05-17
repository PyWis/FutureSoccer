import random
from app.utils.names import random_player_name, random_sponsor_name

# 70% uomo, 15% donna, 15% cyber
_TYPE_POPULATION = ['uomo'] * 70 + ['donna'] * 15 + ['cyber'] * 15

def _random_type():
    return random.choice(_TYPE_POPULATION)

SKILLS = ['porta', 'difesa', 'attacco', 'resistenza']
MAX_SKILL_INITIAL = 4.5
MAX_SKILL_ABSOLUTE = 6.5


def _generate_skills(target_avg, max_val=MAX_SKILL_INITIAL, min_val=0.5):
    """4 random skills whose average ≈ target_avg, clamped to [min_val, max_val]."""
    raw = [random.uniform(min_val, max_val) for _ in range(4)]
    raw_avg = sum(raw) / 4
    if raw_avg > 0:
        raw = [s * (target_avg / raw_avg) for s in raw]
    return [max(min_val, min(max_val, round(s, 1))) for s in raw]


def generate_new_team_player(team_id):
    """Player for auto-assignment on team creation (avg 3.0, age 18-21)."""
    from app.models.team import Player
    ptype = _random_type()
    skills = _generate_skills(3.0)
    return Player(
        name=random_player_name(ptype),
        type=ptype,
        age=random.randint(18, 21),
        porta=skills[0],
        difesa=skills[1],
        attacco=skills[2],
        resistenza=skills[3],
        is_free_agent=False,
        team_id=team_id,
    )


def generate_market_offer_data(scouted=False):
    """Stats for a weekly market offer (not yet persisted as Player)."""
    if not scouted:
        avg = 3.0
    else:
        r = random.random()
        if r < 0.40:
            avg = random.uniform(3.0, 3.5)
        elif r < 0.70:
            avg = random.uniform(3.5, 4.0)
        elif r < 0.90:
            avg = random.uniform(4.0, 4.5)
        else:
            avg = random.uniform(4.5, 5.0)
    avg = round(avg, 2)
    ptype = _random_type()
    skills = _generate_skills(avg, max_val=min(MAX_SKILL_ABSOLUTE, avg + 1.5))
    return {
        'name': random_player_name(ptype),
        'type': ptype,
        'age': random.randint(18, 25),
        'porta': skills[0],
        'difesa': skills[1],
        'attacco': skills[2],
        'resistenza': skills[3],
        'avg': round(sum(skills) / 4, 2),
        'is_scouted': scouted,
    }


def generate_sponsor_offer_data(top7_avg, existing_names=None):
    """Generate a sponsor offer dict based on team top-7 average skill."""
    max_value = (top7_avg / 10.0) * 10_000_000
    weekly = round(max_value * random.uniform(0.5, 1.0), -3)  # round to nearest 1000
    duration = random.randint(4, 10)
    name = random_sponsor_name()
    if existing_names:
        for _ in range(10):
            if name not in existing_names:
                break
            name = random_sponsor_name()
    return {'name': name, 'weekly_amount': weekly, 'duration_weeks': duration}
