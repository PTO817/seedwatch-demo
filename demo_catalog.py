"""Session-only catalog walkthrough. Never contacts retailers or company data."""
import streamlit as st

def render_demo_catalog():
    st.info('Interactive workflow preview. Entries stay in this browser session and do not change the sample charts. Listing tests are simulated; no websites are contacted.')
    action=st.radio('Manage',['Retailers','Retailer listings'],horizontal=True)
    names=st.session_state.setdefault('demo_retailers',['Amazing Herbs','Amazon','GNC','Whole Foods','Vitacost','iHerb','H-E-B','Vitamin Shoppe'])
    if action=='Retailers':
        with st.form('demo_retailer'):
            name=st.text_input('Retailer name',placeholder='Example Retailer')
            website=st.text_input('Retailer website',placeholder='https://example.com')
            save=st.form_submit_button('Add sample retailer')
        if save:
            if not name.strip() or not website.startswith('https://'):st.error('Enter a name and an HTTPS website.')
            elif name.strip().casefold() in [n.casefold() for n in names]:st.error('That retailer is already listed.')
            else:names.append(name.strip());st.success('Sample retailer added. Choose Retailer listings to continue.')
        st.write('Saved sample retailers: '+', '.join(names))
        st.caption('In the private app, new retailers start with manual checks unless an automatic collector is available.')
    else:
        retailer=st.selectbox('Retailer',names)
        product=st.selectbox('Product',['DEMO-001 · Sample Seed Oil · 4 oz','DEMO-002 · Sample Seed Oil · 8 oz'])
        url=st.text_input('Product URL',placeholder='https://example.com/product')
        scenario=st.selectbox('Simulated test outcome',['Matching product and price','Product mismatch','Access blocked'])
        key=(retailer,product,url,scenario)
        if st.button('Test sample listing',disabled=not url.startswith('https://')):
            st.session_state.demo_test=(key,scenario=='Matching product and price')
        result=st.session_state.get('demo_test')
        passed=bool(result and result[0]==key and result[1])
        if result and result[0]==key:
            if passed:st.success('Simulated match: sample price $24.00 USD. Review product and size before saving.')
            else:st.warning('Simulated '+scenario.lower()+'. Automatic activation is blocked; manual review is required.')
        confirmed=st.checkbox('I confirmed the product and size match.',key='confirm_'+str(key))
        if st.button('Save sample listing',disabled=not passed or not confirmed):
            saved=st.session_state.setdefault('demo_saved_listings',[])
            row={'Retailer':retailer,'Product':product,'URL':url}
            if row not in saved:saved.append(row)
            st.success('Sample listing saved for this session.')
        if st.session_state.get('demo_saved_listings'):st.dataframe(st.session_state.demo_saved_listings,hide_index=True)
