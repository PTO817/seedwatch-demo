"""Compare only listings linked to the same catalog product ID."""
import json
import pandas as pd
import altair as alt
import streamlit as st
from catalog_tools import comparison_history, retailers
from model import observation, connect, open_sqlite, state_path

COLORS={'Amazing Herbs':'#275b42','Amazon':'#e58b24','GNC':'#a94769','H-E-B':'#168c91',
        'Vitacost':'#7960b3','Vitamin Shoppe':'#a17c15','Whole Foods':'#477fcc','iHerb':'#8a5235'}

def retailer_colors(runtime,names):
    """Persist assignments so filtering or adding retailers never changes old colors."""
    import colorsys
    def rgb(value):return tuple(int(value[i:i+2],16) for i in (1,3,5))
    candidates=[]
    for saturation in (.75,.55,.9):
        for light in (.40,.52,.30):
            for hue in range(0,360,7):
                values=colorsys.hls_to_rgb(hue/360,light,saturation)
                linear=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in values]
                luminance=sum(v*w for v,w in zip(linear,(.2126,.7152,.0722)))
                if .06<luminance<.28:  # Readable lines against the light chart background.
                    candidates.append('#'+''.join(f'{round(v*255):02x}' for v in values))
    with open_sqlite(state_path(runtime)) as c:
        c.execute('CREATE TABLE IF NOT EXISTS retailer_colors(name TEXT PRIMARY KEY,color TEXT NOT NULL UNIQUE)')
        for name,color in COLORS.items():
            c.execute('INSERT OR IGNORE INTO retailer_colors VALUES(?,?)',(name,color))
        assigned=dict(c.execute('SELECT name,color FROM retailer_colors'))
        for name in sorted(set(names)-set(assigned)):
            used=[rgb(v) for v in assigned.values()]+[rgb('#555555')]
            available=[v for v in candidates if v not in assigned.values()]
            # Select the most separated remaining shade, never recycle a color.
            if not available:
                available=[f'#{n:06x}' for n in range(1,0xffffff) if f'#{n:06x}' not in assigned.values()][:4096]
            color=max(available,key=lambda v:min(sum((x-y)**2 for x,y in zip(rgb(v),u)) for u in used))
            c.execute('INSERT INTO retailer_colors VALUES(?,?)',(name,color));assigned[name]=color
    return assigned

def render_comparison(config,rows,table,export_csv):
    colors=retailer_colors(config.RUNTIME,[r['name'] for r in retailers(config.DATABASE)])
    opts={r['product_id']:f"{r['sku']} · {r.get('brand','Amazing Herbs')} · {r['product_name']} · {r['size']}" for r in rows}
    pid=st.selectbox('Choose a product',list(opts),format_func=opts.get)
    matches=[r for r in rows if r['product_id']==pid]
    names=sorted({r['retailer_name'] for r in matches})
    selected=st.multiselect('Retailers to compare',names,default=names,key='compare_'+str(pid))
    st.caption('Select any combination, including all retailers carrying this exact catalog product and size. Add missing retailer links in Manage catalog.')
    if not selected:st.info('Select at least one retailer to compare.');return
    selected_rows=[r for r in matches if r['retailer_name'] in selected]
    a,b=st.columns(2)
    a.metric('Retailers selected',len(selected))
    b.metric('Current catalog MAP',f"${matches[0]['catalog_map']:.2f}")
    hist=pd.DataFrame(comparison_history(config.DATABASE,pid))
    if not hist.empty:hist=hist[hist.retailer_name.isin(selected)].copy()
    missing=[r['retailer_name'] for r in selected_rows if r['current_price'] is None]
    if missing:st.info('No saved price yet: '+', '.join(missing)+'. These retailers remain in the table but have no plotted price.')
    if hist.empty:st.info('No price history recorded for the selected retailers.')
    else:
        hist['date_checked']=pd.to_datetime(hist.date_checked)
        # Deterministic latest observation per retailer/day, with all raw rows retained below.
        plot=hist.sort_values('check_id').drop_duplicates(['date_checked','retailer_name'],keep='last')
        scale=alt.Scale(domain=names,range=[colors[n] for n in names])
        chart=alt.Chart(plot).mark_line(point=True).encode(
            x=alt.X('date_checked:T',title='Check date'),y=alt.Y('current_price:Q',title='Price (USD)',scale=alt.Scale(zero=False)),
            color=alt.Color('retailer_name:N',title='Retailer',scale=scale),
            tooltip=[alt.Tooltip('retailer_name:N',title='Retailer'),alt.Tooltip('date_checked:T',title='Checked',format='%Y-%m-%d'),
                     alt.Tooltip('current_price:Q',title='Price',format='$.2f'),alt.Tooltip('map_price:Q',title='MAP at check',format='$.2f')])
        if st.checkbox('Show current catalog MAP',value=True):
            rule=alt.Chart(pd.DataFrame({'MAP':[matches[0]['catalog_map']]})).mark_rule(color='#555555',strokeDash=[6,4]).encode(y='MAP:Q',tooltip=[alt.Tooltip('MAP:Q',format='$.2f',title='Current catalog MAP')])
            chart=chart+rule
        st.altair_chart(chart.properties(height=360),width='stretch')
        st.caption('Dots are saved observations; connecting lines do not imply checks on intervening days. The dashed reference is today’s catalog MAP, not historical MAP. Prices may reflect different sellers, locations, and shopping methods.')
    st.subheader('Latest prices by retailer')
    table(pd.DataFrame(selected_rows))
    from reports import download
    download(config,selected_rows,'Download comparison as Excel')
    st.caption('Check the Last checked column before comparing freshness. Missing prices are never treated as zero.')
    if not hist.empty:
        view=hist[['date_checked','retailer_name','current_price','map_price','status']].copy()
        view['date_checked']=view.date_checked.dt.strftime('%Y-%m-%d')
        view=view.rename(columns={'date_checked':'Date','retailer_name':'Retailer','current_price':'Price','map_price':'MAP at check','status':'Result'})
        with st.expander('All recorded prices'):
            st.dataframe(view,hide_index=True,width='stretch')
            st.download_button('Export comparison',export_csv(view),file_name='seedwatch-comparison.csv',mime='text/csv')
    st.subheader('Latest observation details')
    by_id={r['listing_id']:r for r in selected_rows}
    lid=st.selectbox('Retailer details',list(by_id),format_func=lambda lid:by_id[lid]['retailer_name'])
    row=by_id[lid]
    st.link_button('Open retailer page ↗',row['product_url'])
    if row['reason']:st.caption(row['reason'])
    context=observation(config.RUNTIME,row['check_id']) if row['check_id'] else {}
    if not config.DEMO and row['check_id']:
        with connect(config.DATABASE) as c:
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='manual_observations'").fetchone():
                saved=c.execute('SELECT context FROM manual_observations WHERE check_id=?',(row['check_id'],)).fetchone()
                if saved:context=json.loads(saved[0])
    if config.DEMO:st.caption('Synthetic sample observations.')
    elif context:
        for key in ('seller','store','delivery_zip','method','size_note','note','source'):
            if context.get(key):st.write(f"**{key.replace('_',' ').capitalize()}:** {context[key]}")
    else:st.caption('No seller or location details recorded for this historical observation.')
