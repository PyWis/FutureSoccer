"""Background scheduler: drives all time-based game events.

Runs every SCHEDULER_INTERVAL seconds (default 15) and, for each tick:
  1. processes matured day/week-tick events for every team
     (sponsor income, loan installments, investments, scouting, wellness,
     stadium degradation, annual events, freshness recovery);
  2. advances any active match whose turn timer has elapsed, so abandoned
     matches still progress and finish;
  3. on Sunday, if neither manager connected within the first 2 game-day
     minutes, auto-creates and fully simulates the pending accepted
     challenges.

Intended for a single-process deployment (the dev server / a single worker).
With multiple worker processes you must run the scheduler in only one of
them, otherwise events would be processed several times.
"""
import os
import json
import logging
from datetime import datetime

log = logging.getLogger('futuresoccer.scheduler')

# Auto-resolve match-day games not started within the first 2 minutes (real seconds).
SUNDAY_AUTOCALC_SECONDS = 120
MATCH_WEEKDAYS = (2, 6)  # Wednesday and Sunday

_started = False


def get_turn_duration():
    return int(os.environ.get('MATCH_TURN_SECONDS', 30))


def run_scheduled_tasks():
    """One scheduler tick. Must run inside an app context."""
    from app import db
    from app.models.team import Team
    from app.models.game import FriendlyMatch
    from app.routes.events import process_due_team_events
    from app.utils.match_engine import advance_match_if_due

    # 1. Matured events for every team
    for team in Team.query.all():
        try:
            process_due_team_events(team)
        except Exception:
            db.session.rollback()
            log.exception('event processing failed for team %s', getattr(team, 'id', '?'))

    # 2. Advance active matches whose turn timer elapsed
    turn_seconds = get_turn_duration()
    for match in FriendlyMatch.query.filter_by(status='active').all():
        try:
            if advance_match_if_due(match, turn_seconds):
                db.session.commit()
        except Exception:
            db.session.rollback()
            log.exception('advancing match %s failed', match.id)

    # 3. Match-day auto-resolution
    try:
        _auto_resolve_match_day_matches()
    except Exception:
        db.session.rollback()
        log.exception('match-day auto-resolution failed')


def _auto_resolve_match_day_matches():
    from app import db
    from app.models.team import Team
    from app.models.game import FriendlyMatch, MatchChallenge, TeamFormation
    from app.utils.gameclock import (get_game_weekday, get_seconds_into_game_day,
                                      get_game_day_number)
    from app.utils.match_engine import build_home_lineup, simulate_match_to_completion

    if get_game_weekday() not in MATCH_WEEKDAYS:
        return
    if get_seconds_into_game_day() < SUNDAY_AUTOCALC_SECONDS:
        return

    week_monday = get_game_day_number() - get_game_weekday()
    challenges = MatchChallenge.query.filter(
        MatchChallenge.status == 'accepted',
        MatchChallenge.match_id == None,
        MatchChallenge.game_day >= week_monday,
    ).all()

    current_day = get_game_day_number()
    for ch in challenges:
        if ch.match_id is not None:  # started in the meantime
            continue
        home = Team.query.get(ch.challenger_id)
        away = Team.query.get(ch.challenged_id)
        cf = TeamFormation.query.filter_by(team_id=ch.challenger_id).first()
        df = TeamFormation.query.filter_by(team_id=ch.challenged_id).first()
        if not (home and away and cf and df):
            continue  # cannot simulate without both formations

        match = FriendlyMatch(
            home_team_id=home.id,
            away_team_id=away.id,
            game_day=current_day,
            home_lineup_json=json.dumps(build_home_lineup(home, cf)),
            away_lineup_json=json.dumps(build_home_lineup(away, df)),
            last_turn_at=datetime.utcnow(),
            status='active',
            current_turn=0,
        )
        db.session.add(match)
        db.session.flush()
        ch.match_id = match.id
        simulate_match_to_completion(match)
        db.session.commit()
        log.info('auto-resolved Sunday match %s (%s vs %s) %d-%d',
                 match.id, home.name, away.name, match.home_score, match.away_score)


def start_scheduler(app):
    """Start the background scheduler once for this process."""
    global _started
    if _started:
        return None
    interval = int(os.environ.get('SCHEDULER_INTERVAL', 15))
    from apscheduler.schedulers.background import BackgroundScheduler

    scheduler = BackgroundScheduler(daemon=True)

    def _job():
        with app.app_context():
            run_scheduled_tasks()

    scheduler.add_job(_job, 'interval', seconds=interval,
                      max_instances=1, coalesce=True, id='game_tick')
    scheduler.start()
    _started = True
    log.info('scheduler started (interval=%ss)', interval)
    return scheduler
