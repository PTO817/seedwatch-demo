"""Per-visitor synthetic workspace. No production paths or network collectors."""
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime,timezone,timedelta
import tempfile,uuid
import streamlit as st
from demo_data import create_demo
from model import open_sqlite,state_path,snapshot,COLLECTORS,automatic_retailers,manual_reason,today

def workspace():
    if 'demo_workspace_v7' not in st.session_state:
        root=Path(tempfile.mkdtemp(prefix='seedwatch-public-'))
        st.session_state.demo_workspace_v7=str(root)
        db=root/'data'/'sample.db';create_demo(db)
        from catalog_tools import save_retailer,save_listing
        from listing_test import preview
        with open_sqlite(db) as c:
            c.execute('CREATE TABLE retailers(name TEXT PRIMARY KEY COLLATE NOCASE,domain TEXT NOT NULL UNIQUE,notes TEXT NOT NULL)')
            c.execute("INSERT INTO retailers VALUES('Walmart','walmart.com','Synthetic setup example')")
        url='https://www.walmart.com'
        test=preview(db,1,'Walmart',url,'DEMO-18',18)
        test['selected_offer']=test['offers'][0]
        save_listing(db,product_id=1,retailer='Walmart',url=url,retailer_id='DEMO-18',collection_mode='Automatic',listing_id=18,mode='private',test_result=test,identity_confirmed=True)
        runtime=root/'runtime';state=state_path(runtime)
        # One disposable diagnostic file demonstrates the real cleanup rules.
        rid=uuid.uuid4().hex
        old=(datetime.now(timezone.utc)-timedelta(days=40)).isoformat()
        with open_sqlite(state) as c:
            c.execute("INSERT INTO runs(id,started,finished,status) VALUES(?,?,?,?)",(rid,old,old,'Completed'))

        folder=runtime/'runs'/rid/'sample';folder.mkdir(parents=True)
        (folder/'collector.log').write_text('Synthetic old diagnostic log.\n'*1000)
        seed_recent_run(db,runtime)
    root=Path(st.session_state.demo_workspace_v7)
    values=dict(DATABASE=root/'data'/'sample.db',RUNTIME=root/'runtime',TIMEZONE='America/New_York',LOCAL=True,TEST_WORKSPACE=False)
    edit=SimpleNamespace(**values,DEMO=False,MODE='private')
    return SimpleNamespace(**values,DEMO=True,MODE='demo',EDIT=edit)

def simulate_run(config,chosen):
    from catalog_tools import record_price
    from datetime import date
    # Use the same validation and history writes as manual observations, in the session DB only.
    counts={name:0 for name in chosen}
    skipped={name:0 for name in chosen}
    manual={name:0 for name in chosen}
    allowed=set(automatic_retailers(config.DATABASE))
    for row in snapshot(config.DATABASE):
        if row['retailer_name'] in chosen and manual_reason(row):manual[row['retailer_name']]+=1
        if row['retailer_name'] in chosen and row['retailer_name'] in allowed and not manual_reason(row):
            price=row['current_price'] or row['catalog_map']
            if row['retailer_name']=='Amazing Herbs':price=max(price,row['catalog_map'])
            if row['date_checked']==today():
                skipped[row['retailer_name']]+=1
                continue
            counts[row['retailer_name']]+=1
            record_price(config.DATABASE,listing_id=row['listing_id'],price=price,checked_on=date.fromisoformat(today()),context='Synthetic demo check',mode='private')
    rid=uuid.uuid4().hex;now=datetime.now(timezone.utc).isoformat()
    with open_sqlite(state_path(config.RUNTIME)) as c:
        c.execute('INSERT INTO runs(id,started,finished,status) VALUES(?,?,?,?)',(rid,now,now,'Completed'))
        for retailer,count in counts.items():
            c.execute('INSERT INTO attempts(run_id,retailer,status,detail,inserted,skipped,manual) VALUES(?,?,?,?,?,?,?)',(rid,retailer,'Completed','Simulated sample prices; no live requests',count,skipped[retailer],manual[retailer]))


def seed_recent_run(database,runtime):
    """Run totals are derived from the sample observations, not decorative counters."""
    import json
    from collections import defaultdict
    rows=snapshot(database);groups=defaultdict(list)
    for row in rows:
        if row['date_checked']==today() or manual_reason(row):groups[row['retailer_name']].append(row)
    rid=uuid.uuid4().hex;now=datetime.now(timezone.utc).isoformat()
    with open_sqlite(state_path(runtime)) as c:
        c.execute('INSERT INTO runs(id,started,finished,status,retailers) VALUES(?,?,?,?,?)',(rid,now,now,'Completed',json.dumps(list(groups))))
        for retailer,items in groups.items():
            inserted=sum(r['date_checked']==today() and not manual_reason(r) for r in items)
            manual=sum(bool(manual_reason(r)) for r in items)
            omitted=sum(r['retailer_name']==retailer for r in rows)-len(items)
            detail=f'Synthetic run: {inserted} prices saved; {manual} require manual review.'
            if omitted:detail+=f' {omitted} older listings were outside this run’s selection.'
            c.execute('INSERT INTO attempts(run_id,retailer,status,detail,inserted,manual) VALUES(?,?,?,?,?,?)',(rid,retailer,'Completed',detail,inserted,manual))
            for row in items:
                status='Manual check required' if manual_reason(row) else 'Completed'
                c.execute('INSERT INTO listing_attempts VALUES(?,?,?,?)',(row['listing_id'],rid,now,status))
                if status=='Completed':
                    context={'source':'Synthetic demo observation','seller':'Sample seller','observed_at':now,'note':'Fictional portfolio example; no retailer website was contacted.'}
                    c.execute('INSERT INTO observations VALUES(?,?,?)',(row['check_id'],json.dumps(context),rid))
