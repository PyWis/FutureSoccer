import os
import calendar
from datetime import datetime, timedelta, date

GAME_START_DATE = date(2099, 8, 31)
GAME_START_DATETIME = datetime(2099, 8, 31, 0, 0, 0)

WEEKDAY_IT = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
MONTH_IT = ['gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno',
            'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre']


# ── Time modes ────────────────────────────────────────────────────────────────
# Real seconds per game day, by mode:
WEEK_DAY_SECONDS = 12_000     # 3h20m  → 7 giorni ≈ 23h20m (+ pausa fino all'ora del server = 24h)
MONTH_DAY_SECONDS = 2_880     # 48 min → 30 giorni = 24h
FAST_AUGUST_DAY_SECONDS = 3_600   # 1 ora reale per giorno durante il mese veloce
WEEK_REAL_SECONDS = 86_400        # una settimana di gioco occupa 24h reali (allineate all'ora del server)

# Mese veloce: dal 3 agosto, per 24 giorni di gioco
FAST_AUGUST_START_MONTH = 8
FAST_AUGUST_START_DAY = 3
FAST_AUGUST_DAYS = 24


def get_default_day_seconds():
    """Durata (secondi reali) di un giorno in modalità default (env GAME_CLOCK_RATIO)."""
    return int(os.environ.get('GAME_CLOCK_RATIO', 3600))


def get_base_day_seconds(cfg):
    """Secondi reali per giorno di gioco in base alla modalità tempo configurata."""
    mode = getattr(cfg, 'time_mode', 'default')
    if mode == 'week':
        return WEEK_DAY_SECONDS
    if mode == 'month':
        return MONTH_DAY_SECONDS
    return get_default_day_seconds()


def get_clock_ratio():
    """Secondi reali per giorno di gioco (compatibilità). Usa la modalità configurata."""
    from app.models.game import GameConfig
    cfg = GameConfig.query.first()
    if not cfg:
        return get_default_day_seconds()
    return get_base_day_seconds(cfg)


def _in_fast_august(d):
    """True se la data di gioco d cade nella finestra del mese veloce (3 ago + 24 giorni)."""
    start = date(d.year, FAST_AUGUST_START_MONTH, FAST_AUGUST_START_DAY)
    return start <= d < start + timedelta(days=FAST_AUGUST_DAYS)


def next_aug15(game_dt):
    """Prossimo 15 agosto (datetime) a partire dalla data di gioco corrente."""
    d = game_dt.date()
    cand = datetime(d.year, 8, 15)
    if game_dt >= cand:
        cand = datetime(d.year + 1, 8, 15)
    return cand


def last_server_hour(now, hour):
    """Più recente istante reale con ora == hour (minuti/secondi a 0) non successivo a now."""
    cand = now.replace(hour=hour % 24, minute=0, second=0, microsecond=0)
    if cand > now:
        cand -= timedelta(days=1)
    return cand


def _week_clock_state(cfg, now):
    """(game_dt, seconds_into_day, day_total_seconds) per il week mode allineato.

    Una settimana di gioco occupa 24h reali allineate all'ora del server: i 7
    giorni scorrono (12000s ciascuno, o 3600s nel mese veloce) e poi il tempo
    resta fermo a fine Domenica fino al successivo confine delle 24h, realizzando
    il passaggio Domenica→Lunedì solo all'ora del server scelta."""
    anchor_real = cfg.week_anchor_real or cfg.real_start
    anchor_day = cfg.week_anchor_day if cfg.week_anchor_day is not None else 0
    delta = (now - anchor_real).total_seconds()
    if delta < 0:
        delta = 0.0
    weeks = int(delta // WEEK_REAL_SECONDS)
    into_week = delta - weeks * WEEK_REAL_SECONDS
    monday_day = anchor_day + 7 * weeks

    acc = 0.0
    for i in range(7):
        d = game_day_to_date(monday_day + i)
        rate = FAST_AUGUST_DAY_SECONDS if (cfg.fast_august and _in_fast_august(d)) else WEEK_DAY_SECONDS
        if into_week < acc + rate:
            frac = (into_week - acc) / rate
            game_dt = datetime(d.year, d.month, d.day) + timedelta(days=frac)
            return game_dt, into_week - acc, rate
        acc += rate
    # Pausa: tempo fermo a fine Domenica fino al prossimo confine settimanale
    d = game_day_to_date(monday_day + 6)
    sunday_end = datetime(d.year, d.month, d.day) + timedelta(days=1) - timedelta(seconds=1)
    return sunday_end, WEEK_DAY_SECONDS, WEEK_DAY_SECONDS


def _clock_state(cfg, now=None):
    """(game_dt, seconds_into_day, day_total_seconds) tenendo conto di modalità,
    pausa settimanale, mese veloce e freeze al 15 agosto."""
    if now is None:
        now = datetime.utcnow()
    if getattr(cfg, 'time_mode', 'default') == 'week':
        game_dt, into_day, day_total = _week_clock_state(cfg, now)
    else:
        ratio = get_base_day_seconds(cfg)
        elapsed = (now - cfg.real_start).total_seconds()
        game_dt = GAME_START_DATETIME + timedelta(seconds=elapsed / ratio * 86400)
        into_day = elapsed % ratio
        day_total = ratio
    # Freeze al 15 agosto
    if getattr(cfg, 'freeze_aug15', False) and cfg.freeze_target and game_dt >= cfg.freeze_target:
        game_dt = cfg.freeze_target
        into_day = 0.0
    return game_dt, into_day, day_total


def get_game_datetime():
    from app.models.game import GameConfig
    cfg = GameConfig.query.first()
    if not cfg:
        return GAME_START_DATETIME
    return _clock_state(cfg)[0]


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
    return _clock_state(cfg)[1]


# ── Re-anchoring helpers (superadmin time control) ──────────────────────────────

def _anchor_week(cfg, target_dt, now):
    """Allinea il week mode all'ora del server, posizionando il Lunedì della
    settimana di target_dt. Comporta uno snap al confine dell'ora del server."""
    td = target_dt.date()
    monday = td - timedelta(days=td.weekday())
    cfg.week_anchor_day = (monday - GAME_START_DATE).days
    cfg.week_anchor_real = last_server_hour(now, cfg.week_transition_hour)


def _reanchor_linear(cfg, target_dt, now):
    ratio = get_base_day_seconds(cfg)
    gdays = (target_dt - GAME_START_DATETIME).total_seconds() / 86400.0
    cfg.real_start = now - timedelta(seconds=gdays * ratio)


def set_game_datetime(cfg, target_dt, now=None):
    """Re-anchor so the clock reads target_dt at `now`, under the current mode."""
    if now is None:
        now = datetime.utcnow()
    if cfg.time_mode == 'week':
        _anchor_week(cfg, target_dt, now)
    else:
        _reanchor_linear(cfg, target_dt, now)


def apply_time_mode(cfg, new_mode, now=None):
    """Cambia modalità tempo preservando (per quanto possibile) la data corrente.
    Il week mode comporta uno snap di allineamento all'ora del server."""
    if now is None:
        now = datetime.utcnow()
    if new_mode not in ('default', 'week', 'month'):
        return
    current, _, _ = _clock_state(cfg, now)
    cfg.time_mode = new_mode
    set_game_datetime(cfg, current, now)


def set_week_transition_hour(cfg, hour, now=None):
    if now is None:
        now = datetime.utcnow()
    cfg.week_transition_hour = max(0, min(23, int(hour)))
    if cfg.time_mode == 'week':
        current, _, _ = _clock_state(cfg, now)
        _anchor_week(cfg, current, now)


def set_freeze_aug15(cfg, enabled, now=None):
    """Attiva/disattiva il blocco al 15 agosto. All'attivazione fissa il prossimo
    15 agosto; alla disattivazione riparte da lì senza salti."""
    if now is None:
        now = datetime.utcnow()
    enabled = bool(enabled)
    if enabled and not cfg.freeze_aug15:
        current, _, _ = _clock_state(cfg, now)
        cfg.freeze_aug15 = True
        cfg.freeze_target = next_aug15(current)
    elif not enabled and cfg.freeze_aug15:
        target = cfg.freeze_target
        cfg.freeze_aug15 = False
        if target:
            set_game_datetime(cfg, target, now)
        cfg.freeze_target = None


def advance_game_days(cfg, days, now=None):
    """Avanza l'orologio di `days` giorni di gioco, in modo coerente con la modalità."""
    if now is None:
        now = datetime.utcnow()
    if cfg.time_mode == 'week':
        anchor = cfg.week_anchor_real or cfg.real_start
        cfg.week_anchor_real = anchor - timedelta(seconds=days * WEEK_DAY_SECONDS)
    else:
        cfg.real_start -= timedelta(seconds=days * get_base_day_seconds(cfg))


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
