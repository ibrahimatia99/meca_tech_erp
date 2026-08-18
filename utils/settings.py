from extensions import db
from models import SystemSetting

def get_setting(key, default_value=''):
    setting = SystemSetting.query.filter_by(setting_key=key).first()
    return setting.setting_value if setting else default_value

def set_setting(key, value, category='general'):
    setting = SystemSetting.query.filter_by(setting_key=key).first()
    if setting:
        setting.setting_value = str(value)
    else:
        setting = SystemSetting(setting_key=key, setting_value=str(value), category=category)
        db.session.add(setting)
    db.session.commit()

def inject_global_settings():
    return {
        'brand_name': get_setting('brand_name', 'MECA-TECH ATIA'),
        'brand_logo': get_setting('brand_logo', ''),
        'brand_icon': get_setting('brand_icon', ''),
        'brand_phone': get_setting('brand_phone', '+216 99 000 000'),
        'brand_email': get_setting('brand_email', 'contact@mecatechatia.tn'),
        'brand_address': get_setting('brand_address', 'Tunisia'),
        'brand_tax_id': get_setting('brand_tax_id', '1234567/A/M/000'),
        'app_theme_color': get_setting('app_theme', '#FF5500')
    }