"""Conservative retention for known Seedwatch files, under the collection lock."""
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from filelock import FileLock, Timeout
from model import connect


def files(root):
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        return
    for base, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if not (Path(base)/d).is_symlink()]
        for name in names:
            path = Path(base)/name
            if not path.is_symlink():
                yield path


def safe(path, root):
    try:
        relative = path.relative_to(root)
        return all(not p.is_symlink() for p in [root, path, *[root.joinpath(*relative.parts[:i]) for i in range(1,len(relative.parts))]])
    except ValueError:
        return False


def candidates(database, runtime, now=None):
    now = now or datetime.now(timezone.utc)
    database, runtime = Path(database).resolve(), Path(runtime).resolve()
    result = {}
    state = runtime/'runs.db'
    if state.is_file() and not state.is_symlink():
        with connect(state) as c:
            runs = c.execute("SELECT id,finished FROM runs WHERE finished IS NOT NULL AND status != 'Running'").fetchall()
        for run_id, finished in runs:
            if not re.fullmatch(r'[0-9a-f]{32}',run_id):
                continue
            try:
                ended = datetime.fromisoformat(finished)
                if ended.tzinfo is None: ended = ended.replace(tzinfo=timezone.utc)
            except (ValueError,TypeError): continue
            run = runtime/'runs'/run_id
            if not safe(run,runtime) or not run.is_dir(): continue
            for stage in run.iterdir():
                if not safe(stage,runtime) or not stage.is_dir(): continue
                # Only newly marked stages have a verified successful import.
                marker = stage/'.import-complete'
                if marker.is_file() and safe(marker,runtime):
                    for p in stage.glob('*.py'):
                        if safe(p,runtime): result[p] = 'Temporary copies'
                    p = stage/'data/amazing_herbs_price_monitor.db'
                    if p.is_file() and safe(p,runtime): result[p] = 'Temporary copies'
                if now-ended > timedelta(days=30):
                    # Do not traverse browser profiles, data, or arbitrary directories.
                    for p in stage.iterdir():
                        if p.is_file() and safe(p,runtime) and p.suffix in {'.log','.html','.png','.txt'}:
                            result[p] = 'Old diagnostics'
                    for folder in stage.glob('*_results'):
                        if not safe(folder,runtime): continue
                        for p in files(folder):
                            if p.suffix in {'.log','.html','.png','.txt'} and safe(p,runtime):
                                result[p] = 'Old diagnostics'
    backups = database.parent/'backups'
    dated = []
    for p in backups.glob('catalog-*.db'):
        if not safe(p,database.parent) or not p.is_file(): continue
        try: date = datetime.strptime(p.stem[8:],'%Y%m%dT%H%M%S%f').replace(tzinfo=timezone.utc)
        except ValueError: continue
        dated.append((date,p))
    dated.sort(reverse=True)
    keep = {p for _,p in dated[:10]}
    months = set()
    for date,p in dated:
        if date >= now-timedelta(days=365):
            month = date.strftime('%Y-%m')
            if month not in months: keep.add(p); months.add(month)
    for _,p in dated:
        if p not in keep: result[p] = 'Older backups'
    return result


def cleanup(database, runtime, mode='demo'):
    if mode != 'private': return {'status':'Disabled in demo','removed':0,'bytes':0}
    lock = FileLock(str(Path(database).resolve())+'.runner.lock')
    try: lock.acquire(timeout=0)
    except Timeout: return {'status':'A price check or catalog edit is active; cleanup postponed.','removed':0,'bytes':0}
    report = {'status':'Completed','removed':0,'bytes':0,'errors':[]}
    try:
        for path in candidates(database,runtime):
            try:
                size = path.stat().st_size
                path.unlink()
                report['removed'] += 1; report['bytes'] += size
            except OSError as e: report['errors'].append(str(e))
        if report['errors']: report['status'] = 'Some files could not be removed.'
    except Exception as e:
        report['status'] = 'Cleanup could not finish.'; report['errors'].append(str(e))
    finally: lock.release()
    return report


def render_storage(config):
    import streamlit as st
    st.write('Price history, products, retailer listings, saved offer details, and JSON reports are retained. Browser profiles are left alone.')
    st.caption('Diagnostics: 30 days. Backups: latest 10 plus one per month from the past year. Temporary database and script copies: removed after verified imports. Failed imports are retained for recovery.')
    if config.DEMO:
        st.info('Storage cleanup is available only in the private workspace.'); return
    try:
        total = sum(p.stat().st_size for p in files(config.RUNTIME))
        backups = sum(p.stat().st_size for p in files(config.DATABASE.parent/'backups'))
        eligible = sum(p.stat().st_size for p in candidates(config.DATABASE,config.RUNTIME))
        a,b,c = st.columns(3)
        a.metric('Run files',f'{total/1024**2:.1f} MB')
        b.metric('Database backups',f'{backups/1024**2:.1f} MB')
        c.metric('Ready to clean',f'{eligible/1024**2:.1f} MB')
    except OSError:
        st.info('Files changed during the storage check. Refresh to update the totals.')
    st.caption('Cleanup runs when you open the app and after a price check. Original project folders and other workspaces are outside its scope.')
    if st.button('Clean up old files'):
        report = cleanup(config.DATABASE,config.RUNTIME,config.MODE)
        st.session_state['storage_report'] = report
        st.rerun()
    report = st.session_state.get('storage_report')
    if report:
        st.info(f"{report['status']} Removed {report['removed']} files ({report['bytes']/1024**2:.1f} MB).")
