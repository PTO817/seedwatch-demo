"""Public demo validation only: no network access or live collection."""
from urllib.parse import urlsplit

def checked_url(url,domain):
    parsed=urlsplit(url)
    if not domain or parsed.scheme!='https' or parsed.hostname not in (domain,'www.'+domain) or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Enter a matching HTTPS product URL for this retailer.')
    return url

def catalog_binding(product):
    return {key:str(product.get(key) or '') for key in ('product_name','size','upc','brand')}
