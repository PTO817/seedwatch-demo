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
    from catalog_tools import retailers
    from automatic_setup import checked_url
    product=next(p for p in products(database) if p['product_id']==product_id)
    domain=next((r['domain'] for r in retailers(database) if r['name']==retailer),'')
    checked_url(url,domain)
    result={'passed':True,'fingerprint':fingerprint(product,retailer,url,retailer_id),'tested_at':time.time(),
            'price':round(product['map_price']*1.05,2),'detail':'Simulated listing test passed. No website was contacted. Confirm the sample offer details.',
            'output':'Synthetic compatibility result; not a live validation of this retailer.'}
    if retailer not in COLLECTORS:
        rule={'version':1,'domain':domain,'identity':{'sku':product['sku']},'seller':'Sample marketplace seller','currency':'USD','name':product['product_name']}
        offer={'key':hashlib.sha256(json.dumps(rule,sort_keys=True).encode()).hexdigest(),'price':result['price'],'product':product['product_name'],'seller':rule['seller'],'size':product['size'],'rule':rule}
        result['offers']=[offer]
    elif not retailer_id:
        raise ValueError('Enter the retailer product ID before testing.')
    details=[result['output'],f'Retailer: {retailer}',f'Product: {product["product_name"]}',f'Size: {product["size"]}',f'Price: ${result["price"]:.2f} USD']
    if result.get('offers'):
        offer=result['offers'][0]
        details.extend(['Seller: '+offer['seller'],'Identifiers: '+', '.join(f'{k}: {v}' for k,v in offer['rule']['identity'].items())])
    result['output']='\n'.join(details)
    return result
