"""Weekly local scheduling; persists due slots and catches up while the app is running."""
import json
import threading
from datetime import datetime,timedelta,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from filelock import FileLock,Timeout
from model import state_path,open_sqlite,COLLECTORS


def settings(runtime):
    state=state_path(runtime)
    with open_sqlite(state) as c:
        c.execute('CREATE TABLE IF NOT EXISTS schedule_settings(id INTEGER PRIMARY KEY, enabled INTEGER, hour INTEGER, timezone TEXT, enabled_at TEXT)')
        c.execute('CREATE TABLE IF NOT EXISTS scheduled_runs(slot TEXT PRIMARY KEY, run_id TEXT, started TEXT)')
        c.execute('INSERT OR IGNORE INTO schedule_settings VALUES(1,1,9,?,?)',('America/New_York',datetime.now(timezone.utc).isoformat()))
        c.row_factory=__import__('sqlite3').Row
        return dict(c.execute('SELECT * FROM schedule_settings WHERE id=1').fetchone())


def save_settings(runtime,enabled,hour,zone):
    if not 0<=int(hour)<=23:raise ValueError('Choose an hour from 0 to 23.')
    ZoneInfo(zone);old=settings(runtime)
    # Changes begin a new scheduling window; do not manufacture a past missed run.
    since=old['enabled_at'] if (old['enabled']==int(enabled) and old['hour']==hour and old['timezone']==zone) else datetime.now(timezone.utc).isoformat()
    with open_sqlite(state_path(runtime)) as c:c.execute('UPDATE schedule_settings SET enabled=?,hour=?,timezone=?,enabled_at=? WHERE id=1',(int(enabled),int(hour),zone,since))


def slots(config,now=None):
    now=(now or datetime.now(timezone.utc)).astimezone(ZoneInfo(config['timezone']))
    last=(now-timedelta(days=(now.weekday()+1)%7)).replace(hour=config['hour'],minute=0,second=0,microsecond=0)
    if last>now:last-=timedelta(days=7)
    return last,last+timedelta(days=7)


def render_schedule(config):
    import streamlit as st
    st.subheader('Weekly checks')
    if config.DEMO:
        st.info('Weekly collection is available in the private app.');return
    current=settings(config.RUNTIME);last,next_slot=slots(current)
    with st.form('weekly_schedule'):
        enabled=st.checkbox('Enable Sunday checks',value=bool(current['enabled']))
        hour=st.selectbox('Sunday check time',range(24),index=current['hour'],format_func=lambda h:f'{h:02}:00')
        zones={'America/New_York':'Eastern Time','America/Chicago':'Central Time','America/Denver':'Mountain Time','America/Los_Angeles':'Pacific Time'}
        zones.setdefault(current['timezone'],current['timezone'].replace('_',' '))
        zone=st.selectbox('Time zone',list(zones),index=list(zones).index(current['timezone']),format_func=zones.get)
        if st.form_submit_button('Save schedule'):
            save_settings(config.RUNTIME,enabled,hour,zone);st.rerun()
    st.write('Next scheduled check: **'+(next_slot.strftime('%A, %B %d at %I:%M %p %Z') if current['enabled'] else 'Paused')+'**')
    st.caption('Demo schedule only; no background jobs run. All supported retailers are included. Keep Seedwatch running and the computer awake. After a missed Sunday, it runs one catch-up check when reopened; it does not invent prices for missed dates. Failed scheduled runs remain visible and can be retried with Check prices.')
    with open_sqlite(state_path(config.RUNTIME)) as c:
        row=c.execute('SELECT s.started,r.status FROM scheduled_runs s LEFT JOIN runs r ON r.id=s.run_id ORDER BY s.started DESC LIMIT 1').fetchone()
    if row:st.write(f'Last scheduled attempt: {row[0]} · {row[1] or "Starting"}')
    else:st.caption('No scheduled check has run yet.')
    error=Path(config.RUNTIME)/'schedule-error.txt'
    if error.exists():st.warning('The scheduler reported: '+error.read_text()[:400])
