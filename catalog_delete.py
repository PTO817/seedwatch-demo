"""Explicit, backed-up catalog deletion; historical run files remain archives."""
import hashlib
import json
from pathlib import Path
from datetime import datetime
from model import connect, open_sqlite
from catalog_tools import edit, retailers


def _preview(c, listing_id=None, retailer=None):
    if (listing_id is None)==(retailer is None):raise ValueError('Choose one listing or one retailer.')
    tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    rows=c.execute('SELECT * FROM retailer_listings WHERE '+('listing_id=?' if listing_id is not None else 'retailer_name=? COLLATE NOCASE'),(listing_id if listing_id is not None else retailer,)).fetchall()
    if listing_id is not None and not rows:raise ValueError('This listing no longer exists.')
    ids=[r[0] for r in c.execute('SELECT listing_id FROM retailer_listings WHERE '+('listing_id=?' if listing_id is not None else 'retailer_name=? COLLATE NOCASE'),(listing_id if listing_id is not None else retailer,))]
    marks=','.join('?' for _ in ids) or 'NULL'
    checks=c.execute(f'SELECT check_id FROM price_checks WHERE listing_id IN ({marks})',ids).fetchall()
    followups=c.execute(f'SELECT * FROM followup_events WHERE listing_id IN ({marks})',ids).fetchall() if 'followup_events' in tables else []
    profile=c.execute('SELECT * FROM retailer_email_profiles WHERE retailer=? COLLATE NOCASE',(retailer,)).fetchall() if retailer is not None and 'retailer_email_profiles' in tables else []
    token=hashlib.sha256(json.dumps([rows,checks,followups,profile],default=str).encode()).hexdigest()
    return dict(listing_ids=ids,check_ids=[r[0] for r in checks],listings=len(ids),prices=len(checks),followups=len(followups),contacts=len(profile),token=token)


def preview_delete(database, *, listing_id=None, retailer=None):
    with connect(database) as c:return _preview(c,listing_id,retailer)


def delete_catalog(database, runtime, *, listing_id=None, retailer=None, token, confirmed=False, mode='demo'):
    if not confirmed:raise ValueError('Confirm the deletion first.')
    if retailer is not None and retailer not in [r['name'] for r in retailers(database)]:raise ValueError('This retailer no longer exists.')
    with edit(database,mode) as c:
        plan=_preview(c,listing_id,retailer)
        if plan['token']!=token:raise ValueError('The saved data changed. Review the updated counts and confirm again.')
        state=Path(runtime)/'runs.db'
        if state.exists():
            backup=Path(database).parent/'backups'/('catalog-run-state-'+datetime.now().strftime('%Y%m%dT%H%M%S%f')+'.db')
            with open_sqlite(state) as src,open_sqlite(backup) as dst:src.backup(dst)
            c.execute('ATTACH DATABASE ? AS run_state',(str(state.resolve()),))
            state_tables={r[0] for r in c.execute("SELECT name FROM run_state.sqlite_master WHERE type='table'")}
            for lid in plan['listing_ids']:
                if 'listing_attempts' in state_tables:c.execute('DELETE FROM run_state.listing_attempts WHERE listing_id=?',(lid,))
            for cid in plan['check_ids']:
                if 'observations' in state_tables:c.execute('DELETE FROM run_state.observations WHERE check_id=?',(cid,))
        tables={r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        for cid in plan['check_ids']:
            if 'manual_observations' in tables:c.execute('DELETE FROM manual_observations WHERE check_id=?',(cid,))
        for lid in plan['listing_ids']:
            for table in ('listing_settings','listing_automation','followup_events'):
                if table in tables:c.execute(f'DELETE FROM {table} WHERE listing_id=?',(lid,))
            c.execute('DELETE FROM price_checks WHERE listing_id=?',(lid,))
            c.execute('DELETE FROM retailer_listings WHERE listing_id=?',(lid,))
        if retailer is not None:
            for table,column in [('retailers','name'),('retailer_email_profiles','retailer')]:
                if table in tables:c.execute(f'DELETE FROM {table} WHERE {column}=? COLLATE NOCASE',(retailer,))
            # Built-in choices must not reappear merely because a collector exists.
            c.execute('CREATE TABLE IF NOT EXISTS removed_retailers(name TEXT PRIMARY KEY COLLATE NOCASE)')
            c.execute('INSERT OR IGNORE INTO removed_retailers VALUES(?)',(retailer,))
    return plan


def render_delete(config, *, listing_id=None, retailer=None):
    import streamlit as st
    title='Delete retailer' if retailer is not None else 'Delete listing'
    with st.expander(title):
        try:plan=preview_delete(config.DATABASE,listing_id=listing_id,retailer=retailer)
        except ValueError as e:st.info(str(e));return
        st.write(f"This removes {plan['listings']} listing(s), {plan['prices']} saved price(s), and {plan['followups']} follow-up note(s).")
        if retailer is not None:st.write('The retailer and its saved email contact/template are also removed.')
        st.caption('Catalog products stay. Recovery backups and previous run reports/screenshots remain in storage. Deletion is permanent in the working catalog; there is no Undo button.')
        key=f'delete_{retailer}_{listing_id}_{plan["token"]}'
        name_ok=True
        if retailer is not None:name_ok=st.text_input('Type the retailer name to confirm',key=key+'_name')==retailer
        confirmed=st.checkbox('I want to permanently delete the data listed above.',key=key+'_confirm')
        if st.button(title+' permanently',disabled=not confirmed or not name_ok,key=key+'_button'):
            try:
                delete_catalog(config.DATABASE,config.RUNTIME,listing_id=listing_id,retailer=retailer,token=plan['token'],confirmed=confirmed and name_ok,mode=config.MODE)
                st.session_state.catalog_saved=title.replace('Delete ','').capitalize()+' deleted. A recovery backup was saved.'
                st.rerun()
            except ValueError as e:st.error(str(e))
