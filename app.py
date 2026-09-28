import html
import io
import csv
from pathlib import Path
import pandas as pd
import streamlit as st
import config
from demo_data import create_demo
from model import snapshot,decorate,history,run_status,latest_attempts,observation,COLLECTORS,MANUAL,today

st.set_page_config(page_title='Seedwatch · MAP Monitor',page_icon='🌿',layout='wide',initial_sidebar_state='expanded')
st.markdown('''<style>
.stApp{background:#f7f8f3;color:#1b3329} [data-testid="stSidebar"]{background:#153c31}
[data-testid="stSidebar"] *{color:#f4f6ee} [data-testid="stSidebar"] [data-baseweb="select"] *{color:#17382e}
h1,h2,h3{letter-spacing:-.04em!important} h1{font-size:2.7rem!important;font-weight:650!important}
[data-testid="stMetric"]{background:white;padding:22px;border:1px solid #dfe5d8;border-radius:14px;min-height:125px}
[data-testid="stMetricLabel"]{color:#607164} [data-testid="stMetricValue"]{font-size:2rem}
.stButton>button[kind="primary"]{background:#245943;border-color:#245943;border-radius:8px}
[data-testid="stDataFrame"]{border-radius:12px;overflow:hidden} .eyebrow{letter-spacing:.18em;font-size:.74rem;font-weight:700;color:#64775e;margin-bottom:8px}
.hero-note{font-size:1.05rem;color:#657366;max-width:850px}.brand{font-size:1.6rem;font-weight:700;letter-spacing:-.04em}.brand small{font-size:.65rem;letter-spacing:.2em;display:block;margin-top:4px;color:#b9ccae}
</style>''',unsafe_allow_html=True)

if config.DEMO:create_demo(config.DATABASE)
if not config.DATABASE.is_file():
    st.error('Connect an existing project database before opening the private workspace. See START_HERE.md.');st.stop()

with st.sidebar:
    st.markdown('<div class="brand">Seedwatch<small>RETAIL PRICE MONITOR</small></div>',unsafe_allow_html=True)
    st.write('')
    page=st.radio('Workspace',['Overview','Listings','Product history','Collection activity'],label_visibility='collapsed')
    st.divider()
    st.caption('PUBLIC PORTFOLIO DEMO' if config.DEMO else 'PRIVATE WORKSPACE')
    st.write('Synthetic data · no live checks' if config.DEMO else 'Amazing Herbs · retail monitoring')
    st.caption('Minimum advertised price monitoring with clear source coverage and history.')
    if not config.DEMO and not config.LOCAL:st.button('Sign out',on_click=st.logout)

st.markdown('<div class="eyebrow">PRICE INTELLIGENCE / WORKSPACE</div>',unsafe_allow_html=True)
st.title({'Overview':'A clear view of your retailers.','Listings':'Every listing. One place.','Product history':'See how prices change.','Collection activity':'Know what was checked.'}[page])
if config.DEMO:st.info('Portfolio demo — all products and prices below are synthetic. Retailer links open homepages. Live collection is disabled.')
else:st.caption('Private development preview' if config.LOCAL else 'Private company workspace')

if config.TEST_WORKSPACE:
    st.info('FRESH-PRICE TEST — separate database copy. Results stay in this test workspace; your regular history is unchanged.')

run,attempts=run_status(config.RUNTIME)
rows=decorate(snapshot(config.DATABASE),latest_attempts(config.RUNTIME),today(config.TIMEZONE))
df=pd.DataFrame(rows)
if df.empty:st.info('No active listings found.');st.stop()


def export_csv(frame):
    data=frame.copy()
    # Prevent spreadsheet formulas from interpreting scraped text on export.
    for col in data.select_dtypes(include=['object']).columns:
        data[col]=data[col].map(lambda x: "'"+x if isinstance(x,str) and x.startswith(('=','+','-','@','\t','\r')) else x)
    return data.to_csv(index=False).encode('utf-8-sig')


def table(frame):
    names={'sku':'SKU','product_name':'Product','size':'Size','retailer_name':'Retailer','current_price':'Last price',
           'checked_map':'MAP at check','map_result':'Comparison','collection_state':'Collection status',
           'date_checked':'Last checked','product_url':'Retailer page'}
    view=frame[list(names)].rename(columns=names)
    st.dataframe(view,hide_index=True,width='stretch',column_config={
        'Last price':st.column_config.NumberColumn(format='$%.2f'),
        'MAP at check':st.column_config.NumberColumn(format='$%.2f'),
        'Retailer page':st.column_config.LinkColumn(display_text='Open retailer ↗')})
    return view


if page=='Overview':
    st.markdown('<p class="hero-note">Spot prices below MAP, see the last successful check, and follow up on listings that need attention.</p>',unsafe_allow_html=True)
    current=df['collection_state'].eq('Checked today')
    a,b,c,d=st.columns(4)
    a.metric('Active listings',len(df))
    b.metric('Below MAP · current',int((current & df['map_result'].eq('Below MAP')).sum()))
    c.metric('Checked today',int(current.sum()))
    d.metric('Manual checks',int(df['collection_state'].eq('Manual check required').sum()))
    st.write('')
    left,right=st.columns([1.6,1])
    with left:
        st.subheader('Retailer coverage')
        cover=df.groupby(['retailer_name','collection_state']).size().unstack(fill_value=0)
        st.bar_chart(cover,color=['#37664a','#aac495','#e8bc67','#96a8a3','#d47861','#c7cbd3'][:len(cover.columns)],horizontal=True)
    with right:
        st.subheader('What needs attention')
        manual=int(df.collection_state.eq('Manual check required').sum())
        stale=int(df.collection_state.eq('Outdated').sum())
        st.write(f'**{manual} listings** need a manual retailer check.')
        st.write(f"**{stale} {'listing has' if stale == 1 else 'listings have'}** older observations. Previous prices remain visible.")
        st.caption('Below-MAP flags compare the observed price with the MAP recorded at that check. They are review signals, not a claim about every seller or location.')
        st.caption('Open Listings in the sidebar to filter results and follow retailer links.')
    st.subheader('Latest below-MAP observations')
    below=df[df.historical_status.eq('Below MAP')].sort_values('gap',ascending=False)
    if below.empty:st.success('No below-MAP observations in this view.')
    else:table(below.head(12))

elif page=='Listings':
    a,b,c=st.columns([2,1,1])
    query=a.text_input('Search products or SKU',placeholder='Try a product name or SKU')
    retailers=b.multiselect('Retailer',sorted(df.retailer_name.unique()))
    state=c.selectbox('Collection status',['All']+sorted(df.collection_state.unique()))
    below=st.checkbox('Only below-MAP observations')
    filtered=df.copy()
    if query:filtered=filtered[(filtered.product_name+' '+filtered.sku+' '+filtered['size']).str.contains(query,case=False,regex=False)]
    if retailers:filtered=filtered[filtered.retailer_name.isin(retailers)]
    if state!='All':filtered=filtered[filtered.collection_state==state]
    if below:filtered=filtered[filtered.historical_status=='Below MAP']
    st.caption(f'{len(filtered)} of {len(df)} active listings · prices shown in USD')
    view=table(filtered)
    st.download_button('Export this view',export_csv(view),file_name='seedwatch-demo.csv' if config.DEMO else 'seedwatch-prices.csv',mime='text/csv')
    st.caption('Manual-check listings may have an older saved price. Opening the retailer page does not mark a check as complete.')

elif page=='Product history':
    options={r['listing_id']:f"{r['sku']} · {r['product_name']} · {r['size']} · {r['retailer_name']}" for r in rows}
    lid=st.selectbox('Choose a product listing',list(options),format_func=options.get)
    row=next(r for r in rows if r['listing_id']==lid)
    a,b,c=st.columns(3)
    a.metric('Last observed price',f"${row['current_price']:.2f}" if row['current_price'] is not None else '—')
    b.metric('Current catalog MAP',f"${row['catalog_map']:.2f}")
    c.metric('Collection status',row['collection_state'])
    if row['reason']:st.warning(row['reason'])
    st.link_button('Open retailer page ↗',row['product_url'])
    hist=pd.DataFrame(history(config.DATABASE,lid))
    if hist.empty:st.info('No successful price checks recorded for this listing.')
    else:
        st.caption(f"Last successful check: {row['date_checked']}")
        st.line_chart(hist.set_index('date_checked')[['current_price','map_price']],color=['#275b42','#c38b30'],x_label='Check date',y_label='USD')
        st.dataframe(hist.rename(columns={'date_checked':'Date','current_price':'Price','map_price':'MAP at check','status':'Result'}),hide_index=True,width='stretch')
    context=observation(config.RUNTIME,row['check_id']) if not config.DEMO else {'note':'Synthetic demo observation; no real retailer offer.'}
    st.subheader('Observation context')
    if context:
        for key in ('seller','store','delivery_zip','method','size_note','note','source'):
            if context.get(key):st.write(f"**{key.replace('_',' ').capitalize()}:** {context[key]}")
    else:st.caption('Seller/store/location context was not imported for this historical check. New runner checks retain available context. UPC validation depends on the retailer collector.')

else:
    st.write('The working application checks supported retailers in sequence and records collection results separately from price history.')
    st.info('Portfolio demo: live price checks are unavailable. All displayed products and prices are synthetic.')
    st.multiselect('Retailers to check',list(COLLECTORS),default=list(COLLECTORS))
    st.button('Check prices',disabled=True,type='primary')
    st.caption('The public demo contains no collector code or company database.')
    st.write('In the working application, each run reports new observations, already-checked listings, manual checks, and failures. A failed request does not become a zero-dollar price.')
    st.write('Use Listings to explore retailer coverage and manual-check labels, or Product history to compare an observed price with its recorded MAP threshold.')

st.divider()
st.caption('Seedwatch · MAP monitoring workspace · '+'Synthetic portfolio data' if config.DEMO else 'Seedwatch · Results apply to the observed seller, location and shopping method.')
