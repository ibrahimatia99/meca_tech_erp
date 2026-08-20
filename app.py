import os
from flask import Flask
from config import Config
from extensions import db, login_manager
from models import User, SystemSetting
from utils.settings import inject_global_settings

# Import Blueprints
from routes.auth import auth_bp
from routes.admin_history import admin_history_bp
from routes.worker_portal import worker_portal_bp
from routes.cash import cash_bp
from routes.settings import settings_bp
from routes.expenses import expenses_bp
from routes.clients import clients_bp
from routes.stock import stock_bp
from routes.machines import machines_bp
from routes.workers import workers_bp
from routes.quotes import quotes_bp
from routes.jobs import jobs_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Inject global setting context variables
    app.context_processor(inject_global_settings)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_history_bp)
    app.register_blueprint(worker_portal_bp)
    app.register_blueprint(cash_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(expenses_bp)
    app.register_blueprint(clients_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(machines_bp)
    app.register_blueprint(workers_bp)
    app.register_blueprint(quotes_bp)
    app.register_blueprint(jobs_bp)  # Moved inside create_app()

    return app

def init_db(app):
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                email='admin@mecatechatia.tn',
                full_name='Ibrahim Atia',
                role='admin',
                can_access_settings=True
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()

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
        for key, val in defaults.items():
            if not SystemSetting.query.filter_by(setting_key=key).first():
                db.session.add(SystemSetting(setting_key=key, setting_value=val))
        db.session.commit()

if __name__ == '__main__':
    app = create_app()
    init_db(app)
    app.run(debug=True, port=8080)