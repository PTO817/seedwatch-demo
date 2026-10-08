"""Per-visitor synthetic workspace. No production paths or network collectors."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone,timedelta
import tempfile,uuid
import streamlit as st
from demo_data import create_demo
from model import open_sqlite,state_path,snapshot,COLLECTORS

def workspace():
    if 'demo_workspace_v3' not in st.session_state:
        root=Path(tempfile.mkdtemp(prefix='seedwatch-public-'))
        st.session_state.demo_workspace_v3=str(root)
        db=root/'data'/'sample.db';create_demo(db)
        runtime=root/'runtime';state=state_path(runtime)
        # One disposable diagnostic file demonstrates the real cleanup rules.
        rid=uuid.uuid4().hex
        old=(datetime.now(timezone.utc)-timedelta(days=40)).isoformat()
        with open_sqlite(state) as c:
            c.execute("INSERT INTO runs(id,started,finished,status) VALUES(?,?,?,?)",(rid,old,old,'Completed'))
            c.execute("INSERT INTO attempts(run_id,retailer,status,detail) VALUES(?,?,?,?)",(rid,'Amazing Herbs','Completed','Synthetic previous check'))
        folder=runtime/'runs'/rid/'sample';folder.mkdir(parents=True)
        (folder/'collector.log').write_text('Synthetic old diagnostic log.\n'*1000)
    root=Path(st.session_state.demo_workspace_v3)
    values=dict(DATABASE=root/'data'/'sample.db',RUNTIME=root/'runtime',TIMEZONE='America/New_York',LOCAL=True,TEST_WORKSPACE=False)
    edit=SimpleNamespace(**values,DEMO=False,MODE='private')
    return SimpleNamespace(**values,DEMO=True,MODE='demo',EDIT=edit)

def simulate_run(config,chosen):
    from catalog_tools import record_price
    from datetime import date
    # Use the same validation and history writes as manual observations, in the session DB only.
    counts={name:0 for name in chosen}
    for row in snapshot(config.DATABASE):
        if row['retailer_name'] in chosen and row['retailer_name'] in COLLECTORS:
            price=row['current_price'] or row['catalog_map']
            if row['retailer_name']=='Amazing Herbs':price=max(price,row['catalog_map'])
            if row['date_checked']==date.today().isoformat():continue
            counts[row['retailer_name']]+=1
            record_price(config.DATABASE,listing_id=row['listing_id'],price=price,checked_on=date.today(),context='Synthetic demo check',mode='private')
    rid=uuid.uuid4().hex;now=datetime.now(timezone.utc).isoformat()
    with open_sqlite(state_path(config.RUNTIME)) as c:
        c.execute('INSERT INTO runs(id,started,finished,status) VALUES(?,?,?,?)',(rid,now,now,'Completed'))
        for retailer,count in counts.items():
            c.execute('INSERT INTO attempts(run_id,retailer,status,detail,inserted) VALUES(?,?,?,?,?)',(rid,retailer,'Completed','Simulated sample prices; no live requests',count))
