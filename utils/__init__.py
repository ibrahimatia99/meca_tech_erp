import re
from datetime import datetime
from num2words import num2words
from extensions import db
from models import AuditLog, Quote

def parse_float(val, default=0.0):
    if val is None:
        return default
    val_str = str(val).strip()
    if not val_str:
        return default
    try:
        return float(val_str)
    except (ValueError, TypeError):
        return default

def parse_int(val, default=0):
    if val is None:
        return default
    val_str = str(val).strip()
    if not val_str:
        return default
    try:
        return int(val_str)
    except (ValueError, TypeError):
        return default

def format_amount_in_words(amount):
    dinars = int(amount)
    millimes = int(round((amount - dinars) * 1000))
    dinars_text = num2words(dinars, lang='fr').capitalize()
    if millimes > 0:
        return f"{dinars_text} Dinars et {millimes} Millimes"
    return f"{dinars_text} Dinars"

def log_notification(title, desc, category='General', icon='bell', color='text-brand'):
    try:
        new_log = AuditLog(
            event_title=title,
            event_desc=desc,
            category=category,
            icon=icon,
            color=color,
            date_created=datetime.now()
        )
        db.session.add(new_log)
        db.session.commit()
    except Exception:
        db.session.rollback()

def clean_doc_number(quote_number, target_type):
    """
    Strips existing prefixes and returns the target type (DEV, FAC, or BL) 
    along with the core sequence number.
    """
    if not quote_number:
        return ""
    
    clean_core = quote_number
    for pfx in ['DEV-MTA-', 'FAC-MTA-', 'BL-MTA-', 'DEV-', 'FAC-', 'BL-', 'MTA-']:
        clean_core = clean_core.replace(pfx, '')
    
    clean_core = clean_core.strip('-')
    
    prefix_map = {
        'devis': 'DEV',
        'facture': 'FAC',
        'bl': 'BL'
    }
    target_prefix = prefix_map.get(target_type, 'DEV')
    
    return f"{target_prefix}-MTA-{clean_core}"

def generate_document_ref(doc_type):
    now = datetime.now()
    month_str = now.strftime('%m')
    
    prefix_map = {
        'devis': f"DEV-MTA-{month_str}-",
        'facture': f"FAC-MTA-{month_str}-",
        'bl': f"BL-MTA-{month_str}-"
    }
    prefix = prefix_map.get(doc_type, f"DEV-MTA-{month_str}-")
    
    existing_docs = Quote.query.filter(Quote.quote_number.like(f"{prefix}%")).all()
    max_seq = 149
    for q in existing_docs:
        match = re.search(r'(?:DEV|FAC|BL)-MTA-\d{2}-(\d+)', q.quote_number)
        if match:
            seq = int(match.group(1))
            if seq > max_seq:
                max_seq = seq
    return f"{prefix}{max_seq + 1}"