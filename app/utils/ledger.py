"""Budget ledger: every change to a team's budget goes through record()
so we can later split entrate/uscite per week and per season.

amount is signed: positive = entrata (income), negative = uscita (expense).
record() mutates team.budget and adds a BudgetTransaction; the caller is
responsible for committing (matching the existing code style)."""
from app import db
from app.models.game import BudgetTransaction
from app.utils.gameclock import get_game_day_number, get_game_week_id, get_game_season

# Category keys (used as stable ids); labels/icons live in CATEGORIES below.
CAT_SPONSOR = 'sponsor'
CAT_DARK_SPONSOR = 'sponsor_oscuro'
CAT_STREAMING = 'streaming'
CAT_BOND = 'cedola'
CAT_LOAN_IN = 'prestito'
CAT_LOAN_PAY = 'prestito_rata'
CAT_FEDERATION = 'federazione'
CAT_TRANSFER = 'trasferimento'
CAT_MARKET = 'mercato'
CAT_SCOUTING = 'scouting'
CAT_TRAINING = 'allenamento'
CAT_WELLNESS = 'benessere'
CAT_RETREAT = 'ritiro'
CAT_STADIUM = 'stadio'
CAT_FINE = 'multa'

# label + icon for display in the bilancio page
CATEGORIES = {
    CAT_SPONSOR:      ('Sponsor', '💼'),
    CAT_DARK_SPONSOR: ('Sponsor Oscuro', '🕶️'),
    CAT_STREAMING:    ('Streaming', '📡'),
    CAT_BOND:         ('Cedole / Investimenti', '📈'),
    CAT_LOAN_IN:      ('Prestiti incassati', '🏦'),
    CAT_LOAN_PAY:     ('Rate prestiti', '💸'),
    CAT_FEDERATION:   ('Federazione', '🏛️'),
    CAT_TRANSFER:     ('Trasferimenti', '🔄'),
    CAT_MARKET:       ('Mercato settimanale', '🛒'),
    CAT_SCOUTING:     ('Scouting', '🔍'),
    CAT_TRAINING:     ('Allenamenti', '💪'),
    CAT_WELLNESS:     ('Benessere', '🏥'),
    CAT_RETREAT:      ('Ritiro estivo', '🏕️'),
    CAT_STADIUM:      ('Stadio', '🏗️'),
    CAT_FINE:         ('Multe', '🚨'),
}


def category_label(key):
    return CATEGORIES.get(key, (key.capitalize(), '•'))[0]


def category_icon(key):
    return CATEGORIES.get(key, (key, '•'))[1]


def record(team, amount, category, description=''):
    """Apply a signed budget change and log it. Does not commit."""
    team.budget += amount
    tx = BudgetTransaction(
        team_id=team.id,
        amount=amount,
        category=category,
        description=description,
        game_day=get_game_day_number(),
        game_week_id=get_game_week_id(),
        season=get_game_season(),
    )
    db.session.add(tx)
    return tx
