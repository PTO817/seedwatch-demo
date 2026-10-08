"""Native XLSX exports without executable cell formulas or extra runtime dependencies."""
import io,json,math
from datetime import datetime,timezone
from zipfile import ZipFile,ZIP_DEFLATED
from xml.sax.saxutils import escape
from model import connect,observation


def column(n):
    name=''
    while n:n,r=divmod(n-1,26);name=chr(65+r)+name
    return name


def xmltext(value):
    # XML 1.0 excludes control characters other than tab/newline/carriage return.
    return escape(''.join(c for c in str(value) if c in '\t\n\r' or ord(c)>=32))


def xlsx(sheets):
    buffer=io.BytesIO()
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    with ZipFile(buffer,'w',ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'+''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,len(sheets)+1))+'</Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml',f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{xmltext(name)}" sheetId="{i}" r:id="rId{i}"/>' for i,(name,_,_) in enumerate(sheets,1))+'</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,len(sheets)+1))+f'<Relationship Id="rId{len(sheets)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/styles.xml',f'''<styleSheet xmlns="{ns}"><numFmts count="1"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00;[Red](&quot;$&quot;#,##0.00)"/></numFmts><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Calibri"/></font></fonts><fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF245943"/><bgColor indexed="64"/></patternFill></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>''')
        for i,(name,headers,rows) in enumerate(sheets,1):
            data=[]
            for rn,row in enumerate([headers]+rows,1):
                cells=[]
                for cn,value in enumerate(row,1):
                    ref=f'{column(cn)}{rn}';style=1 if rn==1 else 2 if headers[cn-1] in ('Price (USD)','MAP at check (USD)','Catalog MAP (USD)','Below MAP by (USD)','Price change (USD)') else 0
                    if value is None or isinstance(value,float) and not math.isfinite(value):continue
                    if isinstance(value,(int,float)) and not isinstance(value,bool):cells.append(f'<c r="{ref}" s="{style}"><v>{value}</v></c>')
                    else:cells.append(f'<c r="{ref}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{xmltext(value)}</t></is></c>')
                data.append(f'<row r="{rn}">'+''.join(cells)+'</row>')
            widths=''.join(f'<col min="{j}" max="{j}" width="{48 if h in ("Product","Retailer URL","Offer context","Meaning") else 24}" customWidth="1"/>' for j,h in enumerate(headers,1))
            z.writestr(f'xl/worksheets/sheet{i}.xml',f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>{widths}</cols><sheetData>'+''.join(data)+f'</sheetData><autoFilter ref="A1:{column(len(headers))}{len(rows)+1}"/></worksheet>')
    return buffer.getvalue()


def enrich(database,rows):
    with connect(database) as c:
        for row in rows:
            r=dict(row)
            prior=c.execute('SELECT current_price,status FROM price_checks WHERE listing_id=? AND check_id!=? ORDER BY date_checked DESC,check_id DESC LIMIT 1',(r['listing_id'],r.get('check_id') or -1)).fetchone()
            r['price_change']=round(r['current_price']-prior[0],2) if prior and r['current_price'] is not None else None
            r['newly_below']=bool(prior and prior[1]!='Below MAP' and r.get('historical_status')=='Below MAP')
            yield r


def export_report(database,runtime,rows):
    rows=list(enrich(database,rows));history=[]
    with connect(database) as c:
        c.row_factory=__import__('sqlite3').Row
        manual={r[0]:json.loads(r[1]) for r in c.execute('SELECT check_id,context FROM manual_observations')} if c.execute("SELECT 1 FROM sqlite_master WHERE name='manual_observations'").fetchone() else {}
        for r in rows:
            for h in c.execute('SELECT * FROM price_checks WHERE listing_id=? ORDER BY date_checked,check_id',(r['listing_id'],)):
                context=manual.get(h['check_id']) or observation(runtime,h['check_id'])
                history.append([r['sku'],r['product_name'],r['size'],r['retailer_name'],h['date_checked'],h['current_price'],h['map_price'],h['status'],r['product_url'],json.dumps(context,ensure_ascii=False) if context else ''])
        latest=[]
        for r in rows:
            context=manual.get(r.get('check_id')) or observation(runtime,r.get('check_id'))
            latest.append([r['sku'],r['product_name'],r['size'],r['retailer_name'],r.get('current_price'),r.get('checked_map'),r.get('catalog_map'),max(0,r['gap']) if r.get('gap') is not None else None,max(0,r['gap_percent']) if r.get('gap_percent') is not None else None,r.get('map_result'),r.get('freshness'),r.get('collection_state'),r.get('date_checked'),r.get('last_attempted'),r.get('next_check_due'),r.get('price_change'),'Yes' if r['newly_below'] else 'No',r['product_url'],json.dumps(context,ensure_ascii=False) if context else ''])
    return xlsx([
        ('Latest prices',['SKU','Product','Size','Retailer','Price (USD)','MAP at check (USD)','Catalog MAP (USD)','Below MAP by (USD)','Below MAP (%)','Comparison','Freshness','Collection status','Last checked','Last attempted','Next review due','Price change (USD)','Newly below MAP','Retailer URL','Offer context'],latest),
        ('Price history',['SKU','Product','Size','Retailer','Date checked','Price (USD)','MAP at check (USD)','Result','Retailer URL','Offer context'],history),
        ('Report notes',['Field','Meaning'],[
            ['Generated',datetime.now(timezone.utc).isoformat()],['Scope','Only the selected/filtered listings; history includes all saved observations for those listings.'],
            ['Freshness','Current means checked since the latest Sunday review time. Collection status separately identifies failed or manual checks.'],
            ['MAP','Comparisons use MAP recorded at the observation. Catalog MAP can change independently.'],
            ['Price change','Latest observed price minus the preceding saved observation for that listing; blank if there is no preceding observation.'],
            ['Newly below MAP','Latest observation is below its recorded MAP and the preceding observation was not. A first observation is not a confirmed transition.'],
            ['Context','Prices apply to the seller, location and shopping method recorded, when available. Missing context was not inferred.'],
            ['Missing values','Blank prices were not converted to zero. Historic retailer URLs reflect the current saved listing URL.'],
            ['Values','This is a static report, not a live connection. User and retailer text is stored as text, never Excel formulas.']])])


def download(config,rows,label='Download Excel report'):
    import streamlit as st
    data=export_report(config.DATABASE,config.RUNTIME,rows)
    st.download_button(label,data,file_name='seedwatch-report-'+datetime.now().strftime('%Y-%m-%d')+'.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',key='xlsx_'+label)


def render_reports(config,rows):
    import streamlit as st
    import pandas as pd
    df=pd.DataFrame(enrich(config.DATABASE,rows))
    if df.empty:st.info('No active listings to report.');return
    retailers=st.multiselect('Retailers in report',sorted(df.retailer_name.unique()))
    kind=st.selectbox('Report focus',['All listings','Below MAP','Newly below MAP','Price changed'])
    fresh=st.checkbox('Only current observations')
    if retailers:df=df[df.retailer_name.isin(retailers)]
    if kind=='Below MAP':df=df[df.historical_status.eq('Below MAP')]
    elif kind=='Newly below MAP':df=df[df.newly_below]
    elif kind=='Price changed':df=df[df.price_change.notna() & df.price_change.ne(0)]
    if fresh:df=df[df.freshness.eq('Current')]
    st.caption(f'{len(df)} listings. Excel includes latest prices, their full saved history, and report notes. Older observations are labeled; these are review signals, not proof of a current violation.')
    st.dataframe(df[['sku','product_name','retailer_name','current_price','checked_map','gap','gap_percent','freshness','date_checked','price_change']],hide_index=True)
    download(config,df.to_dict('records'))
