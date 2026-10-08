"""Preview a proposed listing using existing collectors in a disposable workspace."""
import hashlib,json,re,time
from pathlib import Path
from urllib.parse import urlsplit
from model import connect,open_sqlite,COLLECTORS,manual_reason
from catalog_tools import HOSTS,products


def suggest_id(retailer,url):
    path=urlsplit(url).path
    patterns={'Walmart':r'/([0-9]+)/?$', 'Amazon':r'/(?:dp|gp/product)/([A-Za-z0-9]{10})(?:/|$)', 'GNC':r'/([0-9]+)\.html$',
              'Vitacost':r'-([0-9]+)/?$', 'iHerb':r'/([0-9]+)/?$', 'Whole Foods':r'-(b[a-z0-9]{9})/?$',
              'Vitamin Shoppe':r'/([a-zA-Z]{3}[0-9]+)/?$', 'H-E-B':r'/([0-9]+)/?$'}
    match=re.search(patterns.get(retailer,r'(?!)'),path,re.I)
    return match.group(1).upper() if match and retailer in ('Amazon','Whole Foods','Vitamin Shoppe') else match.group(1) if match else ''


def fingerprint(product,retailer,url,retailer_id):
    return hashlib.sha256(json.dumps([product,retailer,url.strip(),retailer_id.strip()],sort_keys=True,default=str).encode()).hexdigest()


def preview(database,product_id,retailer,url,retailer_id,listing_id=None,mode='demo',**kwargs):
    product=next(p for p in products(database) if p['product_id']==product_id)
    host=urlsplit(url).hostname
    domain=HOSTS.get(retailer)
    if not domain or host not in (domain,'www.'+domain) or not retailer_id:
        raise ValueError('Enter the matching retailer URL and product ID.')
    return {'passed':True,'fingerprint':fingerprint(product,retailer,url,retailer_id),'tested_at':time.time(),
            'price':product['map_price'],'detail':'Simulated listing test passed. No website was contacted. Confirm the product details.',
            'output':'Synthetic test result; not a live validation.'}
