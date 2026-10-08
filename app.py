import html
import io
import csv
from datetime import datetime, timezone
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
    page=st.radio('Workspace',['Overview','Listings','Product history','Manage catalog','Collection activity','Reports'],label_visibility='collapsed')
    st.divider()
    st.caption('PUBLIC PORTFOLIO DEMO' if config.DEMO else 'PRIVATE WORKSPACE')
    st.write('Synthetic data · no live checks' if config.DEMO else 'Amazing Herbs · retail monitoring')
    st.caption('Minimum advertised price monitoring with clear source coverage and history.')
    if not config.DEMO and not config.LOCAL:st.button('Sign out',on_click=st.logout)

st.markdown('<div class="eyebrow">PRICE INTELLIGENCE / WORKSPACE</div>',unsafe_allow_html=True)
st.title({'Overview':'A clear view of your retailers.','Listings':'Every listing. One place.','Product history':'See how prices change.','Collection activity':'Know what was checked.','Manage catalog':'Build your retailer catalog.','Reports':'Take your data with you.'}[page])
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
        import altair as alt
        from model import STATUS_COLORS
        plot=df.groupby(['retailer_name','collection_state']).size().reset_index(name='Listings')
        st.altair_chart(alt.Chart(plot).mark_bar().encode(
            y=alt.Y('retailer_name:N',title='Retailer'),x=alt.X('Listings:Q'),
            color=alt.Color('collection_state:N',title='Status',scale=alt.Scale(domain=list(STATUS_COLORS),range=list(STATUS_COLORS.values()))),
            tooltip=['retailer_name','collection_state','Listings']),width='stretch')
        st.caption('Green: current · Yellow: outdated · Gray: not checked · Purple: manual check required · Red: needs review')
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
    from reports import download
    download(config,filtered.to_dict('records'),'Download this view as Excel')
    st.caption('Manual-check listings may have an older saved price. Opening the retailer page does not mark a check as complete.')

elif page=='Product history':
    from comparison_ui import render_comparison
    render_comparison(config,rows,table,export_csv)

elif page=='Reports':
    from reports import render_reports
    st.caption('Downloads contain synthetic portfolio data only.')
    render_reports(config,rows)

elif page=='Manage catalog':
    from demo_catalog import render_demo_catalog
    render_demo_catalog()

else:
    st.write('Try a simulated price check to see how Seedwatch handles accepted prices, duplicate checks, and listings that need attention.')
    st.caption('SIMULATION ONLY · No retailer requests. Results stay in this browser session and do not change the sample dashboard history.')
    with st.expander('Weekly checks · workflow preview'):
        st.caption('The private app supports Sunday checks while the host computer is awake and Seedwatch is running. These demo controls do not schedule jobs.')
        st.checkbox('Enable Sunday checks (preview)',value=True)
        st.selectbox('Sunday check time',[f'{h:02}:00' for h in range(24)],index=9)
        st.selectbox('Time zone',['Eastern Time','Central Time','Mountain Time','Pacific Time'])
    chosen=st.multiselect('Retailers to simulate',sorted(df.retailer_name.unique()),default=sorted(df.retailer_name.unique()))
    if 'sample_checked' not in st.session_state:
        st.session_state.sample_checked={}
    start,reset=st.columns([1,1])
    if reset.button('Reset sample run'):
        st.session_state.sample_checked={}
        st.session_state.pop('sample_report',None)
        st.session_state.pop('sample_run_time',None)
        st.success('Simulation reset. You can run the sample again.')
    if start.button('Run sample check',type='primary',disabled=not chosen):
        results=[]
        for row in rows:
            if row['retailer_name'] not in chosen:continue
            lid=row['listing_id']
            result={'SKU':row['sku'],'Product':row['product_name'],'Retailer':row['retailer_name'],
                    'Sample price':None,'Sample MAP':row['catalog_map'],'Comparison':'Not assessed'}
            if row['retailer_name'] in MANUAL:
                result.update(Outcome='Manual check required',Detail='Scripted manual-review example; no new price assigned.')
            elif lid in st.session_state.sample_checked:
                saved=st.session_state.sample_checked[lid]
                result.update(saved)
                result.update(Outcome='Skipped',Detail='Already accepted in this simulation session. Reset to start again.')
            elif row['sku']=='DEMO-004' and row['retailer_name']=='GNC':
                result.update(Outcome='Needs review',Detail='Scripted missing-price example; no zero price or compliance result assigned.')
            else:
                # Deterministic examples, not market observations or network results.
                offset={'DEMO-001':-2.0,'DEMO-002':1.5,'DEMO-003':0.0,'DEMO-004':-1.0}[row['sku']]
                price=round(row['catalog_map']+offset,2)
                accepted={'Sample price':price,'Comparison':'Below MAP' if price<row['catalog_map'] else 'OK'}
                st.session_state.sample_checked[lid]=accepted
                result.update(accepted)
                result.update(Outcome='Accepted',Detail='Synthetic price accepted for this demonstration.')
            results.append(result)
        st.session_state.sample_report=results
        st.session_state.sample_run_time=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    if 'sample_report' in st.session_state:
        report=pd.DataFrame(st.session_state.sample_report)
        st.subheader('Sample run results')
        st.caption('Simulated run · '+st.session_state.sample_run_time)
        st.success('Simulation complete. No live prices were fetched or saved.')
        cols=st.columns(4)
        for column,label,outcome in zip(cols,['Accepted','Skipped','Manual checks','Needs review'],['Accepted','Skipped','Manual check required','Needs review']):
            column.metric(label,int(report.Outcome.eq(outcome).sum()))
        st.dataframe(report,hide_index=True,width='stretch',column_config={
            'Sample price':st.column_config.NumberColumn(format='$%.2f'),
            'Sample MAP':st.column_config.NumberColumn(format='$%.2f')})
        st.download_button('Export simulated results',export_csv(report),file_name='seedwatch-simulated-results.csv',mime='text/csv')
        st.caption('Run again to see duplicate protection. Reset sample run clears only this session’s simulated results. Other visitors are unaffected.')
    else:
        st.info('Select retailers, then run a sample check. The scenarios are scripted to demonstrate behavior, not current retailer access.')

st.divider()
with st.expander('What I’m working on next'):
    st.write('Make new retailer setup easier by detecting clear product and price data from a pasted URL. Improve automated access to retailers that block price checks, using supported integrations where available. Keep manual review available when a price cannot be validated.')
st.caption('Seedwatch · MAP monitoring workspace · '+'Synthetic portfolio data' if config.DEMO else 'Seedwatch · Results apply to the observed seller, location and shopping method.')
