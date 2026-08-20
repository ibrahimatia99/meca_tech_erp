import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from extensions import db
from models import User
from utils.settings import get_setting, set_setting
from utils.helpers import log_notification

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'svg', 'ico'}

@settings_bp.route('/', endpoint='index')
@settings_bp.route('/dashboard', endpoint='settings_dashboard')
@settings_bp.route('/index', endpoint='settings_index')
@login_required
def settings_dashboard():
    if current_user.role == 'worker' and not current_user.can_access_settings:
        return redirect(url_for('worker_portal.worker_dashboard'))
        
    all_users = User.query.order_by(User.username.asc()).all()
    settings_dict = {
        'brand_name': get_setting('brand_name'),
        'brand_logo': get_setting('brand_logo'),
        'brand_icon': get_setting('brand_icon'),
        'brand_phone': get_setting('brand_phone'),
        'brand_email': get_setting('brand_email'),
        'brand_address': get_setting('brand_address'),
        'brand_tax_id': get_setting('brand_tax_id'),
        'app_theme': get_setting('app_theme'),
        'pdf_font_size': get_setting('pdf_font_size'),
        'pdf_margin': get_setting('pdf_margin'),
        'pdf_header_text': get_setting('pdf_header_text')
    }
    return render_template('settings/index.html', users=all_users, settings=settings_dict)

@settings_bp.route('/brand/update', methods=['POST'])
@login_required
def update_brand_settings():
    set_setting('brand_name', request.form.get('brand_name'), 'brand')
    set_setting('brand_phone', request.form.get('brand_phone'), 'brand')
    set_setting('brand_email', request.form.get('brand_email'), 'brand')
    set_setting('brand_address', request.form.get('brand_address'), 'brand')
    set_setting('brand_tax_id', request.form.get('brand_tax_id'), 'brand')
    
    if request.form.get('app_theme'):
        set_setting('app_theme', request.form.get('app_theme'), 'brand')

    upload_folder = current_app.config['UPLOAD_FOLDER']

    if 'brand_logo_file' in request.files:
        file = request.files['brand_logo_file']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"logo_{int(datetime.now().timestamp())}_{file.filename}")
            file.save(os.path.join(upload_folder, filename))
            set_setting('brand_logo', filename, 'brand')

    if 'brand_icon_file' in request.files:
        file = request.files['brand_icon_file']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"icon_{int(datetime.now().timestamp())}_{file.filename}")
            file.save(os.path.join(upload_folder, filename))
            set_setting('brand_icon', filename, 'brand')

    log_notification('Brand & Theme Settings Updated', 'Updated business metadata and theme color.', 'Settings', 'settings', 'text-brand')
    flash('Brand & Theme updated successfully!', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/pdf/update', methods=['POST'])
@login_required
def update_pdf_settings():
    set_setting('pdf_font_size', request.form.get('pdf_font_size'), 'pdf')
    set_setting('pdf_margin', request.form.get('pdf_margin'), 'pdf')
    set_setting('pdf_header_text', request.form.get('pdf_header_text'), 'pdf')
    flash('PDF preferences updated!', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/users/create', methods=['POST'])
@login_required
def create_user():
    username = request.form.get('username')
    email = request.form.get('email')
    full_name = request.form.get('full_name')
    password = request.form.get('password')
    role = request.form.get('role', 'worker')

    if User.query.filter_by(username=username).first():
        flash('Username already exists.', 'error')
        return redirect(url_for('settings.index'))

    new_user = User(
        username=username,
        email=email or f"{username}@mecatechatia.tn",
        full_name=full_name,
        role=role,
        can_manage_clients=bool(request.form.get('can_manage_clients')),
        can_manage_quotes=bool(request.form.get('can_manage_quotes')),
        can_manage_stock=bool(request.form.get('can_manage_stock')),
        can_manage_machines=bool(request.form.get('can_manage_machines')),
        can_manage_workers=bool(request.form.get('can_manage_workers')),
        can_manage_expenses=bool(request.form.get('can_manage_expenses')),
        can_access_settings=bool(request.form.get('can_access_settings'))
    )
    new_user.set_password(password)

    db.session.add(new_user)
    db.session.commit()
    log_notification('User Created', f'Created account for {full_name} ({username})', 'User', 'user-plus', 'text-green-400')
    flash(f'User "{username}" created successfully!', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/users/edit/<int:user_id>', methods=['POST'])
@login_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    user.full_name = request.form.get('full_name')
    user.email = request.form.get('email')
    user.role = request.form.get('role', user.role)
    
    new_password = request.form.get('password')
    if new_password and new_password.strip():
        user.set_password(new_password)

    # Update Granular Section Access Checkboxes
    user.can_manage_clients = bool(request.form.get('can_manage_clients'))
    user.can_manage_quotes = bool(request.form.get('can_manage_quotes'))
    user.can_manage_stock = bool(request.form.get('can_manage_stock'))
    user.can_manage_machines = bool(request.form.get('can_manage_machines'))
    user.can_manage_workers = bool(request.form.get('can_manage_workers'))
    user.can_manage_expenses = bool(request.form.get('can_manage_expenses'))
    user.can_access_settings = bool(request.form.get('can_access_settings'))

    db.session.commit()
    log_notification('User Updated', f'Updated permissions for {user.full_name} ({user.username})', 'User', 'user-check', 'text-brand')
    flash(f'User "{user.username}" updated successfully!', 'success')
    return redirect(url_for('settings.index'))

@settings_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Cannot delete your active session!', 'error')
        return redirect(url_for('settings.index'))

    user = User.query.get_or_404(user_id)
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{username}" deleted.', 'info')
    return redirect(url_for('settings.index'))

@settings_bp.route('/data/backup-db')
@login_required
def download_database_backup():
    db_path = os.path.join(current_app.root_path, 'meca_tech.db')
    
    if not os.path.exists(db_path):
        db_path = os.path.join(current_app.instance_path, 'meca_tech.db')

    if os.path.exists(db_path):
        return send_file(
            db_path, 
            as_attachment=True, 
            download_name=f'meca_tech_backup_{datetime.now().strftime("%Y%m%d_%H%M")}.db'
        )
    
    flash('Database file not found.', 'error')
    return redirect(url_for('settings.index'))