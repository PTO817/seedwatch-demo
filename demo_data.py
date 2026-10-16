"""Fictional catalog and varied histories, dated in the app's Eastern time zone."""
from datetime import date,timedelta
from pathlib import Path
from model import open_sqlite,today

RETAILERS=[('Amazing Herbs','amazingherbs.com',36),('Amazon','amazon.com',28),('GNC','gnc.com',3),('iHerb','iherb.com',18),('Vitacost','vitacost.com',21),('Whole Foods','wholefoodsmarket.com',2),('H-E-B','heb.com',2),('Vitamin Shoppe','vitaminshoppe.com',5),('Walmart','walmart.com',1)]

def create_demo(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():return
    day=date.fromisoformat(today())
    with open_sqlite(path) as c:
        c.executescript('''CREATE TABLE products(product_id INTEGER PRIMARY KEY,sku TEXT,upc TEXT,product_name TEXT,size TEXT,map_price REAL,retail_price REAL,product_family TEXT);
        CREATE TABLE retailer_listings(listing_id INTEGER PRIMARY KEY,product_id INTEGER,retailer_name TEXT,retailer_product_id TEXT,product_url TEXT,active_status TEXT);
        CREATE TABLE price_checks(check_id INTEGER PRIMARY KEY,listing_id INTEGER,current_price REAL,date_checked TEXT,map_price REAL,status TEXT);
        CREATE TABLE listing_settings(listing_id INTEGER PRIMARY KEY,mode TEXT);''')
        names=['Sample Seed Oil','Sample Botanical Oil','Sample Softgels','Sample Body Cream','Sample Seed Blend','Sample Skin Oil']
        trajectories=[[-.12,-.08,-.05,.02,.05],[.08,.08,.1,.06,.09],[-.1,-.08,-.06,-.03,.02],[-.15,-.12,-.1,-.08,-.05],[.04,.02,.01,.02,-.04]]
        for i in range(1,37):
            name=names[(i-1)%6];size=f'{2+(i-1)//6*2} oz' if 'Softgels' not in name else f'{30+(i-1)//6*15} count'
            mp=round(16+(i%7)*2.5+(i//6)*3,2)
            c.execute('INSERT INTO products VALUES(?,?,?,?,?,?,?,?)',(i,f'DEMO-{i:03}',None,name,size,mp,round(mp*1.3,2),'Sample products'))
            for j,(retailer,domain,count) in enumerate(RETAILERS):
                if i>count:continue
                lid=i*10+j
                c.execute('INSERT INTO retailer_listings VALUES(?,?,?,?,?,?)',(lid,i,retailer,f'DEMO-{lid}',f'https://www.{domain}','Active'))
                manual=j in (6,7) or (j==1 and i==28)
                if manual:c.execute('INSERT INTO listing_settings VALUES(?,?)',(lid,'Manual'))
                if j==8:continue
                # Manual observations and deliberately older observations stay visible.
                stale=j==2 or (j==3 and i>13) or manual
                latest=day-timedelta(days=14 if stale else 0)
                # The brand has sample observations from the earliest demo date.
                history_days=[42,35,28,21,14,7,0] if j==0 else [28,21,14,7,0]
                for step,days in enumerate(history_days):
                    price=round(mp*(1.3 if j==0 else 1+trajectories[(i+j)%5][step]),2)
                    c.execute('INSERT INTO price_checks(listing_id,current_price,date_checked,map_price,status) VALUES(?,?,?,?,?)',(lid,price,(latest-timedelta(days=days)).isoformat(),mp,'Below MAP' if price<mp else 'OK'))
