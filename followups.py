"""Human follow-up decisions, independent of observed price compliance."""
from datetime import datetime, timezone
from model import connect
from catalog_tools import edit

STATES=['Needs review','Contacted retailer','Resolved']

def records(database):
    with connect(database) as c:
        c.row_factory=__import__('sqlite3').Row
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='followup_events'").fetchone():return []
        return [dict(r) for r in c.execute('SELECT * FROM followup_events ORDER BY event_id DESC')]

def save(database,listing_id,status,notes,mode='demo'):
    if status not in STATES:raise ValueError('Choose a follow-up status.')
    if not notes.strip():raise ValueError('Add a note explaining the follow-up.')
    with edit(database,mode) as c:
        if not c.execute('SELECT 1 FROM retailer_listings WHERE listing_id=?',(listing_id,)).fetchone():raise ValueError('Listing no longer exists.')
        c.execute('CREATE TABLE IF NOT EXISTS followup_events(event_id INTEGER PRIMARY KEY,listing_id INTEGER NOT NULL,status TEXT NOT NULL,notes TEXT NOT NULL,updated TEXT NOT NULL)')
        c.execute('INSERT INTO followup_events(listing_id,status,notes,updated) VALUES(?,?,?,?)',(listing_id,status,notes.strip(),datetime.now(timezone.utc).isoformat()))

def render(config,rows):
    import streamlit as st
    import pandas as pd
    st.write('Track retailer conversations and next steps alongside the observed prices.')
    st.caption('Resolving a follow-up does not change prices or remove below-MAP flags. New issues can be reopened with Needs review.')
    events=records(config.DATABASE);latest={}
    for event in events:latest.setdefault(event['listing_id'],event)
    scope=st.selectbox('Show listings',['Needs attention or tracked','All listings'])
    choices=[r for r in rows if scope=='All listings' or r['listing_id'] in latest or r.get('historical_status')=='Below MAP']
    if not choices:st.info('No below-MAP or tracked listings. Choose All listings to start a follow-up.');return
    labels={r['listing_id']:f"{r['sku']} · {r['product_name']} · {r['retailer_name']}" for r in choices}
    lid=st.selectbox('Listing',list(labels),format_func=labels.get)
    event=latest.get(lid,{})
    with st.form('followup_'+str(lid)):
        state=st.selectbox('Follow-up status',STATES,index=STATES.index(event.get('status','Needs review')))
        notes=st.text_area('Follow-up notes',placeholder='Who you contacted, what you learned, or the next step')
        submit=st.form_submit_button('Save follow-up',disabled=config.DEMO)
    if submit:
        try:save(config.DATABASE,lid,state,notes,config.MODE);st.rerun()
        except ValueError as e:st.error(str(e))
    if event:st.caption('Last updated (UTC): '+event['updated'])
    if latest:
        names={r['listing_id']:f"{r['sku']} · {r['retailer_name']}" for r in rows}
        st.subheader('Tracked follow-ups')
        st.dataframe([{'Listing':names.get(k,str(k)),'Status':v['status'],'Notes':v['notes'],'Updated (UTC)':v['updated']} for k,v in latest.items()],hide_index=True)
    history=[{'Status':e['status'],'Notes':e['notes'],'Updated (UTC)':e['updated']} for e in events if e['listing_id']==lid]
    if history:
        st.subheader('Follow-up history');st.dataframe(history,hide_index=True)
