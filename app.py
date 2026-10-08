# Verify the deployment is a complete, matching release before importing app modules.
from pathlib import Path as _Path
import hashlib as _hashlib
import streamlit as _st
_EXPECTED = {'config.py': 'e30d58d6b373070827f36e4801fbfb30c2f643ebac6525941d2233c58334270d', 'catalog_tools.py': '64c6d70ce493ff434eeaec58c9b74a958245401c565475499ecf27ed27afb4a9', 'catalog_ui.py': '960741f7fe7feed32a1b947ae7a336fa25b1d900be2202c84801c72565ea2cc7', 'comparison_ui.py': 'c7609dc6fe261e75bf1750c246ecd9675aebc4a50871b614763981d64272d1ab', 'demo_workspace.py': '47256f188496564946a91deace063f9a297a72568a75df5dc578f7597b078e81', 'demo_data.py': '443fb7cd3ae46fd15ff10c8304b4081683077e510f7057f63382db46ed7942c3', 'model.py': '0afbce23b48639041e1f824b2dbfd1d21208387b60db18756179e9746a318fdf', 'reports.py': '1949ba60de8085b05c3e182190ca54de1450adc8d79cd3c0f6f58a568ef68dec', 'scheduling.py': 'bdadcc385ba18a4e85eae2fa1b246284115dca5a11bed19fbd5571ab7a865001', 'storage.py': '5b42ce2afbc23719fc436d858224c7613844757cd2da08d4bbf3edd6f2f159e1', 'listing_test.py': '6cd18eee6c4406d18abf975e9c9d3485aa0ad2c1b9bbb242b2e162a7dd68344f'}
_root = _Path(__file__).resolve().parent
_bad = [name for name, digest in _EXPECTED.items() if not (_root/name).is_file() or _hashlib.sha256((_root/name).read_bytes()).hexdigest()!=digest]
if _bad:
    _st.error('The demo update is incomplete. Upload every file from Seedwatch_Demo_Complete, then reboot the app. Files needing update: '+', '.join(_bad))
    _st.stop()

import html
import io
import csv
from pathlib import Path
import pandas as pd
import streamlit as st
import config
from demo_workspace import workspace, simulate_run
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

config=workspace()

with st.sidebar:
    st.markdown('<div class="brand">Seedwatch<small>RETAIL PRICE MONITOR</small></div>',unsafe_allow_html=True)
    st.write('')
    page=st.radio('Workspace',['Overview','Listings','Product history','Manage catalog','Collection activity','Reports','Storage'],label_visibility='collapsed')
    st.divider()
    st.caption('PUBLIC PORTFOLIO DEMO' if config.DEMO else 'PRIVATE WORKSPACE')
    st.write('Synthetic data · no live checks' if config.DEMO else 'Amazing Herbs · retail monitoring')
    st.caption('Minimum advertised price monitoring with clear source coverage and history.')
    if not config.DEMO and not config.LOCAL:st.button('Sign out',on_click=st.logout)

st.markdown('<div class="eyebrow">PRICE INTELLIGENCE / WORKSPACE</div>',unsafe_allow_html=True)
st.title({'Overview':'A clear view of your retailers.','Listings':'Every listing. One place.','Product history':'See how prices change.','Collection activity':'Know what was checked.','Manage catalog':'Keep your catalog growing.','Storage':'Keep your workspace tidy.','Reports':'Take your pricing data with you.'}[page])
if config.DEMO:st.info('Portfolio demo — all products and prices below are synthetic. Retailer links open homepages. Live collection is disabled.')
else:st.caption('Private development preview' if config.LOCAL else 'Private company workspace')

if config.TEST_WORKSPACE:
    st.info('FRESH-PRICE TEST — separate database copy. Results stay in this test workspace; your regular history is unchanged.')

from scheduling import settings
schedule=settings(config.RUNTIME)
if page=='Storage':
    from storage import render_storage
    render_storage(config.EDIT)
    st.stop()

run,attempts=run_status(config.RUNTIME)
rows=decorate(snapshot(config.DATABASE),latest_attempts(config.RUNTIME),today(schedule['timezone'] if schedule else config.TIMEZONE),schedule)
df=pd.DataFrame(rows)
if page=='Manage catalog':
    from catalog_ui import render_catalog
    render_catalog(config.EDIT)
    st.stop()
if page=='Reports':
    from reports import render_reports
    render_reports(config,rows)
    st.stop()
if df.empty:st.info('No active listings found. Add products and retailer links in Manage catalog.');st.stop()


def export_csv(frame):
    data=frame.copy()
    # Prevent spreadsheet formulas from interpreting scraped text on export.
    for col in data.select_dtypes(include=['object']).columns:
        data[col]=data[col].map(lambda x: "'"+x if isinstance(x,str) and x.startswith(('=','+','-','@','\t','\r')) else x)
    return data.to_csv(index=False).encode('utf-8-sig')


def table(frame):
    names={'sku':'SKU','product_name':'Product','size':'Size','retailer_name':'Retailer','current_price':'Last price',
           'checked_map':'MAP at check','map_result':'Comparison','collection_state':'Collection status',
           'freshness':'Freshness','date_checked':'Last checked','last_attempted':'Last attempted','next_check_due':'Next review due','product_url':'Retailer page'}
    view=frame[list(names)].rename(columns=names)
    st.dataframe(view,hide_index=True,width='stretch',column_config={
        'Last price':st.column_config.NumberColumn(format='$%.2f'),
        'MAP at check':st.column_config.NumberColumn(format='$%.2f'),
        'Retailer page':st.column_config.LinkColumn(display_text='Open retailer ↗')})
    return view


if page=='Overview':
    st.markdown('<p class="hero-note">Spot prices below MAP, see the last successful check, and follow up on listings that need attention.</p>',unsafe_allow_html=True)
    current=df['freshness'].eq('Current')
    a,b,c,d=st.columns(4)
    a.metric('Active listings',len(df))
    b.metric('Below MAP · current',int((current & df['map_result'].eq('Below MAP')).sum()))
    c.metric('Current this week',int(current.sum()))
    d.metric('Manual checks',int(df['collection_state'].eq('Manual check required').sum()))
    st.write('')
    left,right=st.columns([1.6,1])
    with left:
        st.subheader('Retailer coverage')
        cover=df.groupby(['retailer_name','collection_state']).size().unstack(fill_value=0)
        import altair as alt
        from model import STATUS_COLORS
        colors={name:color for name,color in STATUS_COLORS.items() if name!='Check in progress'}
        coverage_rows=df.copy()
        running=coverage_rows.collection_state.eq('Check in progress')
        coverage_rows.loc[running,'collection_state']=coverage_rows.loc[running,'freshness']
        plot=coverage_rows.groupby(['retailer_name','collection_state']).size().reset_index(name='Listings')
        st.altair_chart(alt.Chart(plot).mark_bar().encode(
            y=alt.Y('retailer_name:N',title='Retailer'),x=alt.X('Listings:Q'),
            color=alt.Color('collection_state:N',title='Status',scale=alt.Scale(domain=list(colors),range=list(colors.values()))),
            tooltip=['retailer_name','collection_state','Listings']),width='stretch')
        st.caption('Green: current · Yellow: outdated · Red: collection needs review · Gray: not checked · Purple: manual check required')
    with right:
        st.subheader('What needs attention')
        manual=int(df.collection_state.eq('Manual check required').sum())
        stale=int(df.freshness.eq('Outdated').sum())
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
    state=c.selectbox('Collection status',['All']+sorted(s for s in df.collection_state.unique() if s!='Check in progress'))
    below=st.checkbox('Only below-MAP observations')
    filtered=df.copy()
    if query:filtered=filtered[(filtered.product_name+' '+filtered.sku+' '+filtered['size']).str.contains(query,case=False,regex=False)]
    if retailers:filtered=filtered[filtered.retailer_name.isin(retailers)]
    if state!='All':filtered=filtered[filtered.collection_state==state]
    if below:filtered=filtered[filtered.historical_status=='Below MAP']
    st.caption(f'{len(filtered)} of {len(df)} active listings · prices shown in USD')
    view=table(filtered)
    st.download_button('Export this view',export_csv(view),file_name='seedwatch-demo.csv' if config.DEMO else 'seedwatch-prices.csv',mime='text/csv')
    from reports import download
    download(config,filtered.to_dict('records'),'Download this view as Excel')
    st.caption('Manual-check listings may have an older saved price. Opening the retailer page does not mark a check as complete.')

elif page=='Product history':
    from comparison_ui import render_comparison
    render_comparison(config,rows,table,export_csv)

else:
    st.write('Run supported retailers in sequence. Failures stay visible and do not stop the remaining retailers.')
    st.warning('H-E-B and Vitamin Shoppe require manual checks. Amazon’s checkout-only listing remains unresolved.')
    chosen=st.multiselect('Retailers to check',list(COLLECTORS),default=['Amazon','Whole Foods'] if config.TEST_WORKSPACE else list(COLLECTORS))
    st.caption('Demo: price checks are simulated using sample data; no retailer websites are contacted.')
    if st.button('Check prices',type='primary',disabled=not chosen):
        simulate_run(config,chosen)
        st.rerun()
    from scheduling import render_schedule
    render_schedule(config.EDIT)
    @st.fragment(run_every='3s')
    def progress():
        current,items=run_status(config.RUNTIME)
        if not current:
            st.info('No collection runs yet.' if not config.DEMO else 'Demo only. Live run history appears in the private workspace.');return
        st.subheader('Latest run')
        st.write(f"**{current['status']}** · Started {current['started'][:19].replace('T',' ')} UTC")
        done=sum(x['status'] not in ('Running','Queued') for x in items)
        st.progress(done/max(len(items),1),text=f'{done} of {len(items)} retailers finished')
        st.dataframe(pd.DataFrame(items)[['retailer','status','inserted','skipped','manual','failed','detail']],hide_index=True,width='stretch')
        if current['status']=='Running':st.caption('Keep this app process running until the check finishes. If the app is stopped, an interrupted run may require a restart.')
        if not config.DEMO:
            for item in items:
                logfile=config.RUNTIME/'runs'/current['id']/item['retailer'].replace(' ','_')/'collector.log'
                if logfile.is_file():
                    problem=collector_problem(logfile.read_text(errors='replace'))
                    if problem:st.error(item['retailer']+': '+problem)
            with st.expander('Diagnostic output'):
                for item in items:
                    log=config.RUNTIME/'runs'/current['id']/item['retailer'].replace(' ','_')/'collector.log'
                    if log.is_file():
                        st.caption(item['retailer']);st.code(log.read_text(errors='replace')[-12000:],language='text')
    progress()

st.divider()
st.caption('Seedwatch · MAP monitoring workspace · '+'Synthetic portfolio data' if config.DEMO else 'Seedwatch · Results apply to the observed seller, location and shopping method.')
