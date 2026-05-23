import os
import calendar
from datetime import datetime, timedelta, date

GAME_START_DATE = date(2099, 8, 31)
GAME_START_DATETIME = datetime(2099, 8, 31, 0, 0, 0)

WEEKDAY_IT = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
MONTH_IT = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
            'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']


def get_clock_ratio():
    """Real seconds per game day (default 3600 = 1 hour).

    A longer day makes the 2-minute Sunday connect window a small slice of the
    day rather than most of it; tune via GAME_CLOCK_RATIO."""
    return int(os.environ.get('GAME_CLOCK_RATIO', 3600))


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


def game_day_to_date(day_number):
    """Convert a game-day number (days since start) back to a calendar date."""
    return GAME_START_DATE + timedelta(days=day_number)


def format_game_date(d=None):
    if d is None:
        d = get_game_date()
    return f"{WEEKDAY_IT[d.weekday()]} {d.day} {MONTH_IT[d.month - 1]} {d.year}"


def is_training_day():
    """True on Tue (regular), Wed (makeup Tue), Thu (regular), Fri (makeup Thu)."""
    return get_game_weekday() in (1, 2, 3, 4)


def get_training_session_day():
    """
    Returns the canonical game_day for the current training session.
    Wednesday is makeup for Tuesday, Friday is makeup for Thursday:
    returns yesterday's game_day so the unique TrainingRecord constraint
    prevents double training in one session.
    """
    wd = get_game_weekday()
    gd = get_game_day_number()
    if wd in (2, 4):   # Wed = makeup Tue, Fri = makeup Thu
        return gd - 1
    return gd


def is_sponsor_day():
    return get_game_weekday() == 4         # Fri


def get_prev_game_week_id():
    """ISO week_id of the previous game week."""
    gd = get_game_date()
    prev_monday = gd - timedelta(days=gd.weekday() + 7)
    y, w, _ = prev_monday.isocalendar()
    return y * 100 + w


def get_next_game_week_id():
    """ISO week_id of the next game week."""
    gd = get_game_date()
    next_monday = gd + timedelta(days=7 - gd.weekday())
    y, w, _ = next_monday.isocalendar()
    return y * 100 + w


def get_seconds_into_game_day():
    """Real seconds elapsed since the current game day started."""
    from app.models.game import GameConfig
    cfg = GameConfig.query.first()
    if not cfg:
        return 0
    total_elapsed = (datetime.utcnow() - cfg.real_start).total_seconds()
    ratio = get_clock_ratio()
    return total_elapsed % ratio


def get_game_month_id():
    """Unique int for the current game month: year*100 + month."""
    gd = get_game_date()
    return gd.year * 100 + gd.month


def get_game_season(d=None):
    """Season identifier = the calendar year in which the season started.

    Seasons run 1 September → 31 August. So Sep–Dec belong to year Y,
    Jan–Aug belong to season Y-1."""
    if d is None:
        d = get_game_date()
    return d.year if d.month >= 9 else d.year - 1


def format_game_season(season=None):
    if season is None:
        season = get_game_season()
    return f"{season}/{season + 1}"


# ── Monthly championship calendar ──────────────────────────────────────────────

CHAMPIONSHIP_LAST_MATCHDAY = 28   # the fixed final matchday of every month


def _date_to_game_day(d):
    return (d - GAME_START_DATE).days


def get_month_start_game_day(d=None):
    """Game-day number of the 1st of the current game month."""
    if d is None:
        d = get_game_date()
    return _date_to_game_day(date(d.year, d.month, 1))


def get_month_last_matchday_game_day(d=None):
    """Game-day number of the fixed last matchday (the 28th)."""
    if d is None:
        d = get_game_date()
    return _date_to_game_day(date(d.year, d.month, CHAMPIONSHIP_LAST_MATCHDAY))


def get_month_end_game_day(d=None):
    """Game-day number of the last calendar day of the current game month."""
    if d is None:
        d = get_game_date()
    last_day = calendar.monthrange(d.year, d.month)[1]
    return _date_to_game_day(date(d.year, d.month, last_day))


def is_competition_month(d=None):
    """Monthly championships run September–June. July = annual finals, August = off."""
    if d is None:
        d = get_game_date()
    return d.month not in (7, 8)


def is_july_finals(d=None):
    if d is None:
        d = get_game_date()
    return d.month == 7


def is_august_offseason(d=None):
    if d is None:
        d = get_game_date()
    return d.month == 8


def get_july_first_game_day(d=None):
    """Game-day number of 1 July of the current game year (start of the finals)."""
    if d is None:
        d = get_game_date()
    return _date_to_game_day(date(d.year, 7, 1))


def get_july_last_game_day(d=None):
    """Game-day number of 31 July (Supercoppa day)."""
    if d is None:
        d = get_game_date()
    return _date_to_game_day(date(d.year, 7, 31))
