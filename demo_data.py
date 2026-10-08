from model import open_sqlite
"""Synthetic portfolio data only; never reads the company's database."""
import sqlite3
from datetime import date,timedelta
from pathlib import Path

def create_demo(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():return
    with open_sqlite(path) as c:
        c.executescript('''CREATE TABLE products(product_id INTEGER PRIMARY KEY,sku TEXT,upc TEXT,product_name TEXT,size TEXT,map_price REAL,retail_price REAL,product_family TEXT);
        CREATE TABLE retailer_listings(listing_id INTEGER PRIMARY KEY,product_id INTEGER,retailer_name TEXT,retailer_product_id TEXT,product_url TEXT,active_status TEXT);
        CREATE TABLE price_checks(check_id INTEGER PRIMARY KEY,listing_id INTEGER,current_price REAL,date_checked TEXT,map_price REAL,status TEXT);''')
        retailers=['Amazing Herbs','Amazon','GNC','iHerb','Vitacost','Whole Foods','H-E-B','Vitamin Shoppe']
        domains=['amazingherbs.com','amazon.com','gnc.com','iherb.com','vitacost.com','wholefoodsmarket.com','heb.com','vitaminshoppe.com']
        for i,(name,size,mp) in enumerate([('Sample Seed Oil','4 oz',24),('Sample Seed Oil','8 oz',34),('Sample Softgels','90 count',26),('Sample Body Cream','6 oz',21)],1):
            c.execute('INSERT INTO products VALUES(?,?,?,?,?,?,?,?)',(i,f'DEMO-{i:03}',None,name,size,mp,mp+3,'Sample products'))
            for j,retailer in enumerate(retailers):
                lid=i*10+j
                c.execute('INSERT INTO retailer_listings VALUES(?,?,?,?,?,?)',(lid,i,retailer,f'DEMO-{lid}',f'https://www.{domains[j]}','Active'))
                if j>=6:continue
                for days in [14,10,7,3,0]:
                    if i==4 and j==3 and days<7:continue
                    price=round(mp+(i%2)*1.2 if j==0 else mp+((i+j)%5-2)*1.2+(days%4)*.15,2)
                    c.execute('INSERT INTO price_checks(listing_id,current_price,date_checked,map_price,status) VALUES(?,?,?,?,?)',(lid,price,(date.today()-timedelta(days=days)).isoformat(),mp,'Below MAP' if price<mp else 'OK'))
