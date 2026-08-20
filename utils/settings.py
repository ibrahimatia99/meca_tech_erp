from extensions import db
from models import SystemSetting

def get_setting(key, default_value=''):
    setting = SystemSetting.query.filter_by(setting_key=key).first()
    return setting.setting_value if setting and setting.setting_value else default_value

def set_setting(key, value, category='general'):
    setting = SystemSetting.query.filter_by(setting_key=key).first()
    if setting:
        setting.setting_value = str(value) if value is not None else ''
    else:
        setting = SystemSetting(setting_key=key, setting_value=str(value) if value is not None else '', category=category)
        db.session.add(setting)
    db.session.commit()

def inject_global_settings():
    """Injects branding and application preferences globally across all Jinja2 templates."""
    # Query all records from the database
    all_settings = SystemSetting.query.all()
    
    # Build dictionary from existing DB records
    settings_dict = {s.setting_key: s.setting_value for s in all_settings if s.setting_value}

    # Fallback defaults for empty/missing settings
    defaults = {
        'brand_name': 'MECA-TECH ATIA',
        'brand_logo': '',
        'brand_icon': '',
        'brand_phone': '+216 99 000 000',
        'brand_email': 'contact@mecatechatia.tn',
        'brand_address': 'Tunisia',
        'brand_tax_id': '1234567/A/M/000',
        'app_theme': '#FF5500',
        'pdf_font_size': '11',
        'pdf_margin': '5',
        'pdf_header_text': 'MECA-TECH ATIA - Fabrication Mécanique & Métallique'
    }

    # Apply defaults if key doesn't exist in DB
    for key, val in defaults.items():
        if key not in settings_dict or not settings_dict[key]:
            settings_dict[key] = val

    # Make settings accessible both via `settings.brand_name` and direct top-level variables
    return {
        'settings': settings_dict,
        'brand_name': settings_dict['brand_name'],
        'brand_logo': settings_dict['brand_logo'],
        'brand_icon': settings_dict['brand_icon'],
        'brand_phone': settings_dict['brand_phone'],
        'brand_email': settings_dict['brand_email'],
        'brand_address': settings_dict['brand_address'],
        'brand_tax_id': settings_dict['brand_tax_id'],
        'app_theme': settings_dict['app_theme'],
        'pdf_font_size': settings_dict['pdf_font_size']
    }