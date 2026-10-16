"""Prepare reviewable retailer email drafts; never send email."""
import io
import json
import re
from datetime import datetime
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path
from string import Formatter
from zoneinfo import ZoneInfo
from model import connect, observation
from catalog_tools import edit

DEFAULT_TEMPLATE = '''Dear {greeting},

We noticed an advertised price below Amazing Herbs' minimum advertised price (MAP) for the following item:

Product: {product}
SKU: {sku}
Retailer: {retailer}
Observed price: {price}
MAP at the time of the check: {map_price}
Observed on: {checked_at}
Seller / offer details: {offer_details}
Product link: {url}

Please review this listing and update the advertised price to meet MAP as soon as possible. {response_request}
If this should be handled by another department, please direct us to the appropriate contact.

Thank you,
{signature}'''
FIELDS={'greeting','product','sku','retailer','price','map_price','checked_at','offer_details','url','response_request','signature'}


def validate_template(template):
    for _, field, spec, conversion in Formatter().parse(template):
        if field is not None and (field not in FIELDS or spec or conversion):
            raise ValueError('Use only the listed template placeholders, without formatting modifiers.')
    if not template.strip():raise ValueError('Enter an email template.')


def profile(database, retailer):
    with connect(database) as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='retailer_email_profiles'").fetchone():return {}
        row=c.execute('SELECT settings FROM retailer_email_profiles WHERE retailer=?',(retailer,)).fetchone()
        return json.loads(row[0]) if row else {}


def save_profile(database, retailer, settings, mode):
    validate_template(settings['template'])
    with edit(database,mode) as c:
        c.execute('CREATE TABLE IF NOT EXISTS retailer_email_profiles(retailer TEXT PRIMARY KEY,settings TEXT NOT NULL)')
        c.execute('INSERT OR REPLACE INTO retailer_email_profiles VALUES(?,?)',(retailer,json.dumps(settings)))


def context_for(database,runtime,row):
    cid=row.get('check_id')
    if not cid:return {}
    with connect(database) as c:
        if c.execute("SELECT 1 FROM sqlite_master WHERE name='manual_observations'").fetchone():
            result=c.execute('SELECT context FROM manual_observations WHERE check_id=?',(cid,)).fetchone()
            if result:return json.loads(result[0])
    return observation(runtime,cid) or {}


def checked_time(row,context,zone):
    # Never substitute the email creation time or a failed attempt for observation time.
    raw=context.get('observed_at') or context.get('fetched_at')
    if raw:
        try:
            dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
            if dt.tzinfo is not None:return dt.astimezone(ZoneInfo(zone)).strftime('%Y-%m-%d at %I:%M:%S %p %Z (UTC%z)')
        except (ValueError,TypeError):pass
    return str(row.get('date_checked') or 'Date not recorded')+' (time not recorded)'


def make_body(row,context,settings,zone):
    validate_template(settings['template'])
    greeting=settings.get('contact','').strip() or settings.get('department','').strip() or row['retailer_name']+' Team'
    if settings.get('contact','').strip() and settings.get('department','').strip():
        greeting += ' ('+settings['department'].strip()+')'
    details='; '.join(str(context[k]) for k in ('seller','delivery','price_source','note') if context.get(k)) or 'Not recorded'
    values=dict(greeting=greeting,product=row['product_name']+' · '+row['size'],sku=row['sku'],retailer=row['retailer_name'],
                price=f"${row['current_price']:.2f}",map_price=f"${row['checked_map']:.2f}",checked_at=checked_time(row,context,zone),
                offer_details=details,url=row['product_url'],response_request=settings.get('response_request',''),signature=settings.get('signature',''))
    return settings['template'].format_map(values)


def image_attachment(data,name):
    from PIL import Image
    if len(data)>10*1024*1024:raise ValueError('Each image must be 10 MB or smaller.')
    try:
        with Image.open(io.BytesIO(data)) as img:
            fmt=img.format
            if fmt not in {'PNG','JPEG'}:raise ValueError('Use a PNG or JPEG image.')
            img.verify()
    except Exception as e:raise ValueError('Use a valid PNG or JPEG image (up to 10 MB).') from e
    filename=re.sub(r'[^A-Za-z0-9_.-]','_',Path(name).name) or 'screenshot.png'
    return filename, data, 'png' if fmt=='PNG' else 'jpeg'


def saved_image(runtime,context):
    path=context.get('screenshot_path')
    if not path:return None
    root=Path(runtime).resolve();p=Path(path)
    from storage import safe
    if not p.is_absolute() or not safe(p,root) or not p.is_file():return None
    if p.stat().st_size>10*1024*1024:return None
    return image_attachment(p.read_bytes(),p.name)


def email_bytes(recipient,subject,body,attachments):
    if '\n' in recipient or '\r' in recipient or '\n' in subject or '\r' in subject:raise ValueError('Email headers must be a single line.')
    if not re.fullmatch(r'[^\s@,;<>]+@[^\s@,;<>]+\.[^\s@,;<>]+',recipient.strip()):raise ValueError('Enter one valid recipient email address.')
    if not subject.strip() or not body.strip():raise ValueError('Enter a subject and message.')
    if sum(len(data) for _,data,_ in attachments)>20*1024*1024:raise ValueError('Keep total attachments under 20 MB.')
    msg=EmailMessage(policy=SMTP);msg['To']=recipient.strip();msg['Subject']=subject.strip();msg['X-Unsent']='1'
    msg.set_content(body)
    for name,data,subtype in attachments:msg.add_attachment(data,maintype='image',subtype=subtype,filename=name)
    return msg.as_bytes()


def render(config,rows):
    import streamlit as st
    st.write('Prepare a retailer email from a saved below-MAP observation. Review it and send it from your email app.')
    choices=[r for r in rows if r.get('historical_status')=='Below MAP' and r.get('current_price') is not None and r.get('checked_map') is not None]
    if not choices:st.info('No saved below-MAP listings to draft an email for.');return
    labels={r['listing_id']:f"{r['sku']} · {r['product_name']} · {r['retailer_name']}" for r in choices}
    lid=st.selectbox('Below-MAP listing',list(labels),format_func=labels.get)
    row=next(r for r in choices if r['listing_id']==lid);retailer=row['retailer_name'];ctx=context_for(config.DATABASE,config.RUNTIME,row)
    key=f"mail_{lid}_{row.get('check_id')}";saved=profile(config.DATABASE,retailer)
    st.caption('Saved observation: '+checked_time(row,ctx,config.TIMEZONE))
    if row.get('freshness')!='Current':st.warning('This observation is outdated. Recheck the listing before sending; the draft refers to the saved observation date.')
    with st.form('mail_contact_'+retailer):
        st.subheader('Retailer contact and template')
        recipient=st.text_input('Recipient email',value=saved.get('recipient',''),placeholder='pricing@example.com')
        contact=st.text_input('Contact name (optional)',value=saved.get('contact',''))
        department=st.text_input('Department (optional)',value=saved.get('department',''),placeholder='Pricing or Marketplace Compliance Team')
        signature=st.text_area('Your signature',value=saved.get('signature','Amazing Herbs'),placeholder='Your name\nYour role\nAmazing Herbs')
        response=st.text_input('Requested response',value=saved.get('response_request','Please confirm once the update is complete.'))
        with st.expander('Edit reusable template'):
            st.caption('Available placeholders: '+', '.join('{'+f+'}' for f in sorted(FIELDS)))
            template=st.text_area('Email template',value=saved.get('template',DEFAULT_TEMPLATE),height=370)
        remember=st.checkbox('Save this contact and template for this retailer',value=True,disabled=config.DEMO)
        generate=st.form_submit_button('Prepare email draft')
    if generate:
        settings=dict(recipient=recipient,contact=contact,department=department,signature=signature,response_request=response,template=template)
        try:
            body=make_body(row,ctx,settings,config.TIMEZONE)
            if remember and not config.DEMO:save_profile(config.DATABASE,retailer,settings,config.MODE)
            st.session_state[key]={'recipient':recipient,'subject':f"Price review requested: {row['product_name']} (SKU {row['sku']})",'body':body}
            for field,value in st.session_state[key].items():st.session_state[key+'_'+field]=value
        except ValueError as e:st.error(str(e))
    if key not in st.session_state:return
    st.subheader('Review email')
    recipient=st.text_input('To',key=key+'_recipient')
    subject=st.text_input('Subject',key=key+'_subject')
    body=st.text_area('Message',key=key+'_body',height=420)
    attachments=[]
    try:auto=saved_image(config.RUNTIME,ctx)
    except ValueError:auto=None
    if auto:
        st.image(auto[1],caption='Screenshot saved with this observation',width=550)
        if st.checkbox('Attach saved screenshot',value=True,key=key+'_auto'):attachments.append(auto)
    else:st.caption('No saved screenshot for this observation. Upload an image below. This demo uses sample observations. You can attach an image to try the same email workflow.')
    uploads=st.file_uploader('Add screenshots or images',type=['png','jpg','jpeg'],accept_multiple_files=True,key=key+'_images')
    valid=True
    for upload in uploads or []:
        try:
            attachment=image_attachment(upload.getvalue(),upload.name);attachments.append(attachment)
            st.image(attachment[1],caption=upload.name,width=400)
        except ValueError as e:st.error(str(e));valid=False
    st.caption('Uploads are included in the downloaded email. Confirm that each image shows the correct product, seller, and price. Preparing or downloading a draft does not mark the retailer as contacted.')
    reviewed=st.checkbox('I reviewed the recipient, observation, message, and attachments.',key=key+'_reviewed')
    try:
        data=email_bytes(recipient,subject,body,attachments)
        st.download_button('Download email with attachments (.eml)',data,file_name=f"MAP-review-{row['sku']}.eml",mime='message/rfc822',disabled=not reviewed or not valid)
        st.caption('Open the downloaded file in your email app. Some apps open .eml files as messages; use Forward if needed. Review the recipient and attachments before sending. Nothing is sent by Seedwatch.')
    except ValueError as e:st.info(str(e))
