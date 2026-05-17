import os
from datetime import datetime, timedelta, date

GAME_START_DATE = date(2099, 8, 31)
GAME_START_DATETIME = datetime(2099, 8, 31, 0, 0, 0)

WEEKDAY_IT = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
MONTH_IT = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
            'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']


def get_clock_ratio():
    """Real seconds per game day (default 300 = 5 minutes)."""
    return int(os.environ.get('GAME_CLOCK_RATIO', 300))


def get_game_datetime():
    from app.models.game import GameConfig
    cfg = GameConfig.query.first()
    if not cfg:
        return GAME_START_DATETIME
    elapsed = (datetime.utcnow() - cfg.real_start).total_seconds()
    return GAME_START_DATETIME + timedelta(days=elapsed / get_clock_ratio())


def get_game_date():
    return get_game_datetime().date()


def get_game_weekday():
    """0=Mon … 6=Sun"""
    return get_game_date().weekday()


def get_game_week_id():
    """Unique int for the current ISO Mon-Sun game week."""
    gd = get_game_date()
    y, w, _ = gd.isocalendar()
    return y * 100 + w


def get_game_day_number():
    """Days elapsed since game start."""
    return (get_game_date() - GAME_START_DATE).days


def format_game_date(d=None):
    if d is None:
        d = get_game_date()
    return f"{WEEKDAY_IT[d.weekday()]} {d.day} {MONTH_IT[d.month - 1]} {d.year}"


def is_training_day():
    return get_game_weekday() in (1, 3)   # Tue or Thu


def is_sponsor_day():
    return get_game_weekday() == 4         # Fri


def get_game_month_id():
    """Unique int for the current game month: year*100 + month."""
    gd = get_game_date()
    return gd.year * 100 + gd.month
