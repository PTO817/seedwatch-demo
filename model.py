import json
import sqlite3
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

class ClosingConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def open_sqlite(*args, **kwargs):
    return sqlite3.connect(*args, factory=ClosingConnection, **kwargs)


MANUAL = {'H-E-B': 'Automated access blocked; check retailer page manually.',
          'Vitamin Shoppe': 'Automated access blocked; check retailer page manually.'}
COLLECTORS = {'Amazing Herbs': 'amazing_herbs_insert_price.py', 'iHerb': 'iherb_insert_price.py',
              'Vitacost': 'vitacost_insert.py', 'GNC': 'gnc_insert.py',
              'Amazon': 'amazon_insert.py', 'Whole Foods': 'whole_foods_insert.py'}


def today(timezone='America/New_York'):
    return datetime.now(ZoneInfo(timezone)).date().isoformat()


def connect(path, write=False):
    return open_sqlite(Path(path).resolve().as_uri()+('?mode=rw' if write else '?mode=ro'), uri=True, timeout=30)


def snapshot(database):
    with connect(database) as c:
        c.row_factory = sqlite3.Row
        return [dict(r) for r in c.execute('''SELECT l.*,p.sku,p.product_name,p.size,p.upc,
            p.map_price AS catalog_map, pc.current_price, pc.map_price AS checked_map,
            pc.status AS historical_status,pc.date_checked,pc.check_id
            FROM retailer_listings l JOIN products p ON p.product_id=l.product_id
            LEFT JOIN price_checks pc ON pc.check_id=(SELECT check_id FROM price_checks x
                WHERE x.listing_id=l.listing_id ORDER BY date_checked DESC,check_id DESC LIMIT 1)
            WHERE l.active_status='Active' ORDER BY p.sku,l.retailer_name''')]


def history(database, listing_id):
    with connect(database) as c:
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute('SELECT date_checked,current_price,map_price,status FROM price_checks WHERE listing_id=? ORDER BY date_checked,check_id',(listing_id,))]


def state_path(runtime):
    runtime=Path(runtime);runtime.mkdir(parents=True,exist_ok=True)
    path=runtime/'runs.db'
    with open_sqlite(path) as c:
        c.execute('''CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,started TEXT,finished TEXT,status TEXT,retailers TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS attempts(run_id TEXT,retailer TEXT,status TEXT,detail TEXT,inserted INTEGER DEFAULT 0,skipped INTEGER DEFAULT 0,failed INTEGER DEFAULT 0,PRIMARY KEY(run_id,retailer))''')
        if 'manual' not in {r[1] for r in c.execute('PRAGMA table_info(attempts)')}:
            c.execute('ALTER TABLE attempts ADD COLUMN manual INTEGER DEFAULT 0')
        c.execute('''CREATE TABLE IF NOT EXISTS observations(check_id INTEGER PRIMARY KEY,context TEXT,run_id TEXT)''')
    return path


def run_status(runtime):
    with open_sqlite(state_path(runtime)) as c:
        c.row_factory=sqlite3.Row
        run=c.execute('SELECT * FROM runs ORDER BY started DESC LIMIT 1').fetchone()
        if not run:return None,[]
        attempts=[dict(r) for r in c.execute('SELECT * FROM attempts WHERE run_id=? ORDER BY rowid',(run['id'],))]
        return dict(run),attempts


def observation(runtime, check_id):
    if check_id is None:return {}
    with open_sqlite(state_path(runtime)) as c:
        row=c.execute('SELECT context FROM observations WHERE check_id=?',(check_id,)).fetchone()
    return json.loads(row[0]) if row else {}


def manual_reason(row):
    if row['retailer_name'] in MANUAL:return MANUAL[row['retailer_name']]
    if row['retailer_name']=='Amazon' and row['sku']=='08100':return 'Price shown in cart/checkout; page-only collection unavailable.'
    return ''


def decorate(rows, attempts=(), day=None):
    day=day or today(); by_retailer={a['retailer']:a for a in attempts}
    result=[]
    for source in rows:
        r=dict(source);reason=manual_reason(r);attempt=by_retailer.get(r['retailer_name'])
        if reason:state='Manual check required'
        elif attempt and attempt['status'] in ('Failed','Partial','Interrupted'):
            state='Collection needs review'
        elif attempt and attempt['status'] in ('Running','Queued'):state='Check in progress'
        elif not r['date_checked']:state='Not checked'
        elif r['date_checked'] != day:state='Outdated'
        else:state='Checked today'
        # Historical comparison uses the MAP recorded with that observation.
        r['collection_state']=state;r['reason']=reason
        r['map_result']=('Below MAP' if r['current_price'] < r['checked_map'] else 'OK') if r['current_price'] is not None and r['checked_map'] is not None else 'No price'
        if state!='Checked today' and r['map_result']!='No price':r['map_result']+=' (last check)'
        r['gap']=round(r['checked_map']-r['current_price'],2) if r['checked_map'] is not None and r['current_price'] is not None else None
        result.append(r)
    return result


def latest_attempts(runtime):
    with open_sqlite(state_path(runtime)) as c:
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute("""SELECT a.* FROM attempts a JOIN runs r ON r.id=a.run_id
          WHERE r.started=(SELECT MAX(r2.started) FROM attempts a2 JOIN runs r2 ON r2.id=a2.run_id WHERE a2.retailer=a.retailer)""")]
