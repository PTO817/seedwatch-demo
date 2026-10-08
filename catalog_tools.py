"""Catalog editing and manual observations; writes are locked and backed up."""
from contextlib import contextmanager
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.parse import urlsplit
import sqlite3
from filelock import FileLock, Timeout
from model import connect, open_sqlite, COLLECTORS, today

HOSTS = {'Amazing Herbs':'amazingherbs.com','Amazon':'amazon.com','GNC':'gnc.com',
         'iHerb':'iherb.com','Vitacost':'vitacost.com','Whole Foods':'wholefoodsmarket.com'}


def retailers(database):
    """Include built-ins and legacy listing names without changing the database."""
    from model import MANUAL
    result={name:{'name':name,'domain':HOSTS.get(name,''),'notes':''} for name in set(COLLECTORS)|set(MANUAL)}
    with connect(database) as c:
        for name, in c.execute('SELECT DISTINCT retailer_name FROM retailer_listings'):
            result.setdefault(name,{'name':name,'domain':'','notes':''})
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='retailers'").fetchone():
            for name,domain,notes in c.execute('SELECT name,domain,notes FROM retailers'):
                result[name]={'name':name,'domain':domain,'notes':notes}
    for row in result.values():
        row['checks']='Automatic · listing test required' if row['name'] in COLLECTORS else 'Manual checks'
    return sorted(result.values(),key=lambda r:r['name'].casefold())


def save_retailer(database, *, name, website, notes='', mode='demo'):
    name=str(name).strip();website=str(website).strip()
    if not name:raise ValueError('Enter a retailer name.')
    u=urlsplit(website if '://' in website else 'https://'+website)
    domain=(u.hostname or '').lower().removeprefix('www.')
    import ipaddress,re
    try:ipaddress.ip_address(domain);is_ip=True
    except ValueError:is_ip=False
    if u.scheme not in ('https','http') or u.username or u.password or is_ip or not re.fullmatch(r'[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}',domain):
        raise ValueError('Enter the retailer’s public website, such as https://www.walmart.com.')
    with edit(database,mode) as c:
        existing=retailers(database)
        if any(r['name'].casefold()==name.casefold() for r in existing):
            raise ValueError('That retailer already exists. Choose it under Retailer listings.')
        if any(r['domain']==domain for r in existing):
            raise ValueError('That website already belongs to a saved retailer.')
        c.execute('CREATE TABLE IF NOT EXISTS retailers(name TEXT PRIMARY KEY COLLATE NOCASE,domain TEXT NOT NULL UNIQUE,notes TEXT NOT NULL)')
        c.execute('INSERT INTO retailers VALUES(?,?,?)',(name,domain,str(notes).strip()))
    return name

def metadata(c, rows):
    tables={x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    brands=dict(c.execute('SELECT product_id,brand FROM product_brands')) if 'product_brands' in tables else {}
    modes=dict(c.execute('SELECT listing_id,mode FROM listing_settings')) if 'listing_settings' in tables else {}
    for r in rows:
        r['brand']=brands.get(r['product_id'],'Amazing Herbs')
        r['collection_mode']=modes.get(r.get('listing_id'),'Automatic' if r.get('retailer_name') in COLLECTORS else 'Manual')
    return rows

def products(database):
    with connect(database) as c:
        c.row_factory=sqlite3.Row
        return metadata(c,[dict(r) for r in c.execute('SELECT * FROM products ORDER BY sku')])

def listings(database):
    with connect(database) as c:
        c.row_factory=sqlite3.Row
        return metadata(c,[dict(r) for r in c.execute('SELECT l.*,p.sku,p.product_name,p.size FROM retailer_listings l JOIN products p ON p.product_id=l.product_id ORDER BY p.sku,l.retailer_name')])

def money(value):
    try: n=Decimal(str(value))
    except InvalidOperation: raise ValueError('Enter a valid price.')
    if not n.is_finite() or n<=0 or n!=n.quantize(Decimal('.01')):
        raise ValueError('Prices must be positive, with no more than two decimal places.')
    return float(n)

@contextmanager
def edit(database, mode):
    if mode!='private':raise ValueError('Catalog changes are available only in the private workspace.')
    lock=FileLock(str(Path(database).resolve())+'.runner.lock')
    try:lock.acquire(timeout=0)
    except Timeout:raise ValueError('A price check or another edit is running. Please try again when it finishes.')
    try:
        root=Path(database).parent/'backups';root.mkdir(exist_ok=True)
        backup=root/('catalog-'+datetime.now().strftime('%Y%m%dT%H%M%S%f')+'.db')
        with connect(database) as src,open_sqlite(backup) as dst:src.backup(dst)
        with connect(database,write=True) as c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('CREATE TABLE IF NOT EXISTS product_brands(product_id INTEGER PRIMARY KEY,brand TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS listing_settings(listing_id INTEGER PRIMARY KEY,mode TEXT NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS manual_observations(check_id INTEGER PRIMARY KEY,context TEXT NOT NULL)')
            yield c
    finally:lock.release()

def save_product(database, *, sku, name, size, brand, upc, map_price, product_id=None, mode='demo'):
    sku,name,size,brand,upc=[str(x or '').strip() for x in (sku,name,size,brand,upc)]
    if not all((sku,name,size,brand)):raise ValueError('SKU, product name, size, and brand are required.')
    if upc and (not upc.isdigit() or len(upc) not in (8,12,13,14)):raise ValueError('UPC/GTIN must contain 8, 12, 13, or 14 digits, or be left blank.')
    mp=money(map_price)
    with edit(database,mode) as c:
        if c.execute('SELECT 1 FROM products WHERE lower(trim(sku))=lower(?) AND product_id!=?',(sku,product_id or -1)).fetchone():
            raise ValueError('That SKU already exists. Edit the existing product or use a unique SKU.')
        if product_id is None:
            product_id=c.execute('INSERT INTO products(sku,product_name,size,upc,map_price) VALUES(?,?,?,?,?)',(sku,name,size,upc or None,mp)).lastrowid
        else:
            old=c.execute('SELECT sku FROM products WHERE product_id=?',(product_id,)).fetchone()
            if not old:raise ValueError('Product no longer exists.')
            if old[0]!=sku:raise ValueError('An existing SKU cannot be changed; add a separate product instead.')
            c.execute('UPDATE products SET product_name=?,size=?,upc=?,map_price=? WHERE product_id=?',(name,size,upc or None,mp,product_id))
        c.execute('INSERT OR REPLACE INTO product_brands VALUES(?,?)',(product_id,brand))
    return product_id

def save_listing(database, *, product_id, retailer, url, retailer_id='', collection_mode='Manual', active=True, listing_id=None, mode='demo', test_result=None, identity_confirmed=False):
    retailer,url,retailer_id=[str(x or '').strip() for x in (retailer,url,retailer_id)]
    u=urlsplit(url)
    if not retailer or u.scheme not in ('http','https') or not u.hostname or u.username or u.password:
        raise ValueError('Enter a retailer name and a full public http:// or https:// product URL without login details.')
    if collection_mode not in ('Automatic','Manual'):raise ValueError('Choose Automatic or Manual.')
    with edit(database,mode) as c:
        if not c.execute('SELECT 1 FROM products WHERE product_id=?',(product_id,)).fetchone():raise ValueError('Select an existing product.')
        registry=retailers(database)
        names=[r['name'] for r in registry]
        retailer=next((n for n in names if n.casefold()==retailer.casefold()),retailer)
        registered=next((r for r in registry if r['name']==retailer),None)
        if registered and registered['domain'] and not (u.hostname==registered['domain'] or u.hostname.endswith('.'+registered['domain'])):
            raise ValueError('The product URL must belong to the selected retailer’s website.')
        if collection_mode=='Automatic':
            brand=c.execute('SELECT brand FROM product_brands WHERE product_id=?',(product_id,)).fetchone()
            if brand and brand[0].casefold()!='amazing herbs':raise ValueError('New brands start with manual checks; existing collectors are configured for Amazing Herbs.')
            domain=HOSTS.get(retailer)
            if not domain or not (u.hostname==domain or u.hostname.endswith('.'+domain)):
                raise ValueError('Automatic collection requires a supported retailer and its matching website.')
            if not retailer_id:raise ValueError('Automatic checks need the exact retailer product ID (for example, Amazon ASIN).')
        if c.execute('SELECT 1 FROM retailer_listings WHERE product_id=? AND lower(retailer_name)=lower(?) AND listing_id!=?',(product_id,retailer,listing_id or -1)).fetchone():
            raise ValueError('This product already has a listing at that retailer. Edit that listing instead.')
        if c.execute('SELECT 1 FROM retailer_listings WHERE product_url=? AND listing_id!=?',(url,listing_id or -1)).fetchone():
            raise ValueError('That URL is already assigned to another listing.')
        if collection_mode=='Automatic':
            old=c.execute('SELECT retailer_product_id,product_url,active_status FROM retailer_listings WHERE listing_id=?',(listing_id or -1,)).fetchone()
            old_mode=c.execute('SELECT mode FROM listing_settings WHERE listing_id=?',(listing_id or -1,)).fetchone()
            changed=not old or old[:2]!=(retailer_id,url) or old[2]!='Active' or (old_mode and old_mode[0]!='Automatic')
            if changed and active:
                import time
                from listing_test import fingerprint
                c.row_factory=sqlite3.Row
                product=dict(c.execute('SELECT * FROM products WHERE product_id=?',(product_id,)).fetchone())
                product=metadata(c,[product])[0]
                c.row_factory=None
                valid=test_result and test_result.get('passed') and 0<=time.time()-test_result.get('tested_at',0)<900 and test_result.get('fingerprint')==fingerprint(product,retailer,url,retailer_id)
                if not valid or not identity_confirmed:
                    raise ValueError('Test this listing successfully and confirm its product and size before enabling automatic checks. Tests expire after 15 minutes.')
        args=(product_id,retailer,retailer_id,url,'Active' if active else 'Inactive')
        if listing_id is None:
            listing_id=c.execute('INSERT INTO retailer_listings(product_id,retailer_name,retailer_product_id,product_url,active_status) VALUES(?,?,?,?,?)',args).lastrowid
        else:
            old=c.execute('SELECT product_id,retailer_name FROM retailer_listings WHERE listing_id=?',(listing_id,)).fetchone()
            if not old or old!=(product_id,retailer):raise ValueError('Existing listings must stay attached to the same product and retailer.')
            c.execute('UPDATE retailer_listings SET product_id=?,retailer_name=?,retailer_product_id=?,product_url=?,active_status=? WHERE listing_id=?',args+(listing_id,))
        c.execute('INSERT OR REPLACE INTO listing_settings VALUES(?,?)',(listing_id,collection_mode))
    return listing_id

def record_price(database, *, listing_id, price, checked_on, context, mode='demo'):
    import json
    price=money(price)
    day=date.fromisoformat(str(checked_on)).isoformat()
    if day>today():raise ValueError('A price check cannot be dated in the future.')
    if not context.strip():raise ValueError('Record the seller, location/shopping method, or other offer details you verified.')
    with edit(database,mode) as c:
        r=c.execute("SELECT p.map_price FROM retailer_listings l JOIN products p ON p.product_id=l.product_id WHERE l.listing_id=? AND l.active_status='Active'",(listing_id,)).fetchone()
        if not r:raise ValueError('Choose an active listing.')
        if c.execute('SELECT 1 FROM price_checks WHERE listing_id=? AND date_checked=?',(listing_id,day)).fetchone():raise ValueError('A price is already recorded for this listing on that date; history was preserved.')
        mp=money(r[0])
        cid=c.execute('INSERT INTO price_checks(listing_id,current_price,date_checked,map_price,status) VALUES(?,?,?,?,?)',(listing_id,price,day,mp,'Below MAP' if price<mp else 'OK')).lastrowid
        c.execute('INSERT INTO manual_observations VALUES(?,?)',(cid,json.dumps({'source':'Manual entry','note':context.strip()})))
    return cid

def comparison_history(database, product_id):
    with connect(database) as c:
        c.row_factory=sqlite3.Row
        return [dict(r) for r in c.execute('''SELECT pc.*,l.retailer_name,l.product_url FROM price_checks pc
            JOIN retailer_listings l ON l.listing_id=pc.listing_id WHERE l.product_id=? AND l.active_status='Active'
            ORDER BY pc.date_checked,pc.check_id''',(product_id,))]
