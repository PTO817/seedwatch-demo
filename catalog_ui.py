import streamlit as st
from datetime import date
from catalog_tools import products, listings, save_product, save_listing, record_price, retailers, save_retailer
from model import COLLECTORS, MANUAL

def render_catalog(config):
    st.write('Add products, attach retailer pages, and keep your catalog up to date.')
    if config.DEMO:
        st.info('Catalog editing is available in the private workspace. The public demo does not change company data.')
        return
    if st.session_state.get('catalog_saved'):
        st.success(st.session_state.pop('catalog_saved'))
    ps=products(config.DATABASE);ls=listings(config.DATABASE)
    action=st.radio('Manage',['Products','Retailers','Retailer listings','Record a manual price'],horizontal=True)
    labels={p['product_id']:f"{p['sku']} · {p['brand']} · {p['product_name']} · {p['size']}" for p in ps}
    if action=='Products':
        choice=st.selectbox('Product to edit',[None]+list(labels),format_func=lambda x:'Add a new product' if x is None else labels[x])
        p=next((p for p in ps if p['product_id']==choice),{})
        with st.form('product_'+str(choice)):
            brand=st.text_input('Brand',value=p.get('brand','Amazing Herbs'))
            sku=st.text_input('SKU',value=p.get('sku',''),disabled=choice is not None,help='Use a unique catalog SKU. Leading zeros are preserved.')
            name=st.text_input('Product name',value=p.get('product_name',''))
            size=st.text_input('Size / strength / count',value=p.get('size',''))
            upc=st.text_input('UPC / GTIN (optional)',value=p.get('upc') or '')
            mp=st.number_input('MAP (USD)',min_value=0.01,value=float(p['map_price']) if p.get('map_price') else None,step=.01,format='%.2f')
            st.caption('MAP changes apply to future checks. Saved price history retains the MAP recorded at the time.')
            submit=st.form_submit_button('Save product',type='primary')
        if submit:
            try:
                save_product(config.DATABASE,sku=sku,name=name,size=size,brand=brand,upc=upc,map_price=mp,product_id=choice,mode=config.MODE)
                st.session_state.catalog_saved='Product saved. Use Retailer listings to attach its product pages.';st.rerun()
            except ValueError as e:st.error(str(e))
    elif action=='Retailers':
        st.subheader('Add a retailer')
        st.write('Save a retailer here, then attach its product pages under Retailer listings.')
        with st.form('add_retailer'):
            name=st.text_input('Retailer name',placeholder='Walmart')
            website=st.text_input('Retailer website',placeholder='https://www.walmart.com')
            notes=st.text_area('Notes (optional)',help='For example, the seller or store location you want to monitor.')
            submitted=st.form_submit_button('Save retailer',type='primary')
        st.caption('New retailers start with manual checks unless Seedwatch has a compatible automatic collector. Saving a website does not enable automatic collection.')
        if submitted:
            try:
                saved=save_retailer(config.DATABASE,name=name,website=website,notes=notes,mode=config.MODE)
                st.session_state.catalog_saved=f'{saved} saved. Select Retailer listings to add its product pages.';st.rerun()
            except ValueError as e:st.error(str(e))
        st.subheader('Your retailers')
        st.dataframe(retailers(config.DATABASE),hide_index=True,use_container_width=True,column_config={'name':'Retailer','domain':'Website','checks':'Price checks','notes':'Notes'})
    elif action=='Retailer listings':
        if not ps:st.info('Add a product first.');return
        pid=st.selectbox('Product',list(labels),format_func=labels.get)
        matches=[l for l in ls if l['product_id']==pid]
        lids={l['listing_id']:f"{l['retailer_name']} · {l['active_status']}" for l in matches}
        lid=st.selectbox('Listing to edit',[None]+list(lids),format_func=lambda x:'Add a retailer listing' if x is None else lids[x])
        l=next((l for l in matches if l['listing_id']==lid),{})
        names=[r['name'] for r in retailers(config.DATABASE)]
        retailer=st.selectbox('Retailer',names+['Add a new retailer…'],index=names.index(l['retailer_name']) if l else 0,disabled=lid is not None)
        if retailer=='Add a new retailer…':
            st.info('Select Retailers above to save the retailer first, then return here.');return
        p=next(p for p in ps if p['product_id']==pid)
        auto=retailer in COLLECTORS and p['brand'].casefold()=='amazing herbs'
        st.info('New retailers and brands can be tracked here with manual prices. Automatic collection requires a compatible retailer collector.')
        from listing_test import preview,suggest_id,fingerprint
        prefix=f'listing_{pid}_{lid}_{retailer}'
        url=st.text_input('Product page URL',value=l.get('product_url',''),key=prefix+'_url').strip()
        guessed=suggest_id(retailer,url)
        rid=st.text_input('Retailer product ID / ASIN',value=l.get('retailer_product_id') or guessed,key=prefix+'_id_'+guessed).strip()
        if guessed:st.caption('Product ID found in the URL: '+guessed)
        elif retailer=='Amazing Herbs':st.caption('Use the SKU shown on the Amazing Herbs product page. It is not an Amazon ASIN.')
        modes=['Manual','Automatic'] if auto else ['Manual']
        cm=st.selectbox('How to check prices',modes,index=modes.index(l.get('collection_mode')) if l.get('collection_mode') in modes else 0,key=prefix+'_mode')
        active=st.checkbox('Active listing',value=l.get('active_status','Active')=='Active',key=prefix+'_active')
        fp=fingerprint(p,retailer,url,rid)
        if st.button('Test listing',disabled=not auto or not url or not rid,key=prefix+'_test'):
            try:
                with st.spinner('Testing only this listing. Your catalog and price history are unchanged…'):
                    st.session_state[prefix+'_result']=preview(config.DATABASE,pid,retailer,url,rid,lid,mode=config.MODE)
            except (ValueError,OSError) as e:
                st.session_state.pop(prefix+'_result',None);st.error(str(e))
        result=st.session_state.get(prefix+'_result')
        if result and result.get('fingerprint')!=fp:result=None
        if result:
            (st.success if result['passed'] else st.warning)(result['detail'])
            if result['passed']:
                st.write(f"Test price: **${result['price']:.2f} USD** · Catalog size: **{p['size']}**")
                if result.get('offer'):st.json(result['offer'])
            with st.expander('Test details'):st.code(result.get('output',''),language='text')
        if not auto:st.caption('This retailer or brand requires a manual review; automatic testing is unavailable.')
        if url.startswith(('https://','http://')):st.link_button('Review product page ↗',url)
        confirmed=st.checkbox('I confirmed the product, size/count, and retailer ID match this catalog product.',key=prefix+'_confirmed_'+fp)
        st.caption('Testing cannot guarantee a perfect match. Review the page and test details. Saving adds the listing only; test prices are not added to history.')
        unchanged=bool(l and url==l.get('product_url') and rid==(l.get('retailer_product_id') or '') and cm==l.get('collection_mode') and l.get('active_status')=='Active')
        can_save=confirmed and (cm=='Manual' or not active or unchanged or bool(result and result.get('passed')))
        if st.button('Save listing',type='primary',disabled=not can_save,key=prefix+'_save'):
            try:
                save_listing(config.DATABASE,product_id=pid,retailer=retailer,url=url,retailer_id=rid,collection_mode=cm,active=active,listing_id=lid,mode=config.MODE,test_result=result,identity_confirmed=confirmed)
                st.session_state.catalog_saved='Retailer listing saved. Run a price check to add its first observation.';st.rerun()
            except ValueError as e:st.error(str(e))
    else:
        active=[l for l in ls if l['active_status']=='Active']
        if not active:st.info('Add an active retailer listing first.');return
        opts={l['listing_id']:f"{l['sku']} · {l['product_name']} · {l['size']} · {l['retailer_name']}" for l in active}
        lid=st.selectbox('Listing checked',list(opts),format_func=opts.get)
        l=next(l for l in active if l['listing_id']==lid)
        st.link_button('Open retailer page ↗',l['product_url'])
        with st.form('manual_'+str(lid)):
            price=st.number_input('Observed one-time price (USD)',min_value=.01,value=None,step=.01,format='%.2f')
            day=st.date_input('Date checked',value=date.today(),max_value=date.today())
            context=st.text_area('Seller, location, shopping method, and offer notes')
            confirmed=st.checkbox('I verified the exact product, size/count, and one-time price (excluding shipping).')
            submit=st.form_submit_button('Save manual price',type='primary')
        if submit:
            if not confirmed:st.error('Verify the product and offer before recording a price.')
            else:
                try:
                    record_price(config.DATABASE,listing_id=lid,price=price,checked_on=day,context=context,mode=config.MODE)
                    st.session_state.catalog_saved='Manual observation saved to price history.';st.rerun()
                except ValueError as e:st.error(str(e))
    st.caption('Each save creates a database backup. Inactive listings retain their history. Catalog editing pauses while a price-check run is active.')
