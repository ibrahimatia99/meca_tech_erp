import os
import re
import json
import calendar
from datetime import datetime, date
from flask import Flask, render_template, redirect, url_for, flash, request, send_file, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from num2words import num2words
from sqlalchemy import extract

from models import (
    db, User, SystemSetting, Client, Supplier, Quote, QuoteItem, PaymentHistory,
    StockItem, Machine, MaintenanceLog, Worker, SalaryAdvance, WorkerAttendance, 
    DirectCashIncome, Expense, AuditLog
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'meca-tech-atia-v2-secret-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///meca_tech.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'svg', 'ico'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------------------------------------------------------------------
# SETTINGS HELPERS
# ---------------------------------------------------------------------------
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

@app.context_processor
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

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ---------------------------------------------------------------------------
# UTILITIES
# ---------------------------------------------------------------------------
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

def generate_monthly_ref():
    now = datetime.now()
    month_str = now.strftime('%m')
    prefix = f"DEV-MTA-{month_str}-"
    
    existing_quotes = Quote.query.filter(Quote.quote_number.like(f"{prefix}%")).all()
    max_seq = 149
    for q in existing_quotes:
        match = re.search(r'DEV-MTA-\d{2}-(\d+)', q.quote_number)
        if match:
            seq = int(match.group(1))
            if seq > max_seq:
                max_seq = seq
    return f"DEV-MTA-{month_str}-{max_seq + 1}"

def init_db():
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
            'pdf_margin': '10',
            'pdf_header_text': 'MECA-TECH ATIA - Fabrication Mécanique & Métallique'
        }
        for key, val in defaults.items():
            if not SystemSetting.query.filter_by(setting_key=key).first():
                db.session.add(SystemSetting(setting_key=key, setting_value=val))
        db.session.commit()

# ---------------------------------------------------------------------------
# AUTH & DASHBOARD
# ---------------------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    total_clients = Client.query.count()
    total_quotes = Quote.query.count()
    low_stock_items = StockItem.query.filter(StockItem.quantity <= StockItem.min_stock_alert).all()
    maintenance_machines = Machine.query.filter(Machine.status != 'Operational').all()

    approved_quotes = Quote.query.filter_by(status='Approved').all()
    all_quotes = Quote.query.all()

    direct_cash_entries = DirectCashIncome.query.order_by(DirectCashIncome.date_received.desc()).all()
    total_direct_cash = sum(c.amount for c in direct_cash_entries)

    total_revenue = sum(q.total_amount for q in approved_quotes) + total_direct_cash
    total_collected = sum(q.amount_paid for q in all_quotes) + total_direct_cash
    outstanding_balance = sum(q.total_amount for q in approved_quotes) - sum(q.amount_paid for q in all_quotes)

    current_year = datetime.now().year
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_revenue = [0.0] * 12
    monthly_expenses = [0.0] * 12

    for q in approved_quotes:
        if q.date_created.year == current_year:
            m = q.date_created.month - 1
            monthly_revenue[m] += q.total_amount

    for c in direct_cash_entries:
        if c.date_received.year == current_year:
            m = c.date_received.month - 1
            monthly_revenue[m] += c.amount

    all_expenses = Expense.query.order_by(Expense.date_logged.desc()).all()
    for e in all_expenses:
        if e.date_logged.year == current_year:
            m = e.date_logged.month - 1
            monthly_expenses[m] += e.amount

    activity_feed = AuditLog.query.order_by(AuditLog.date_created.desc()).limit(20).all()

    return render_template(
        'dashboard.html', 
        total_clients=total_clients,
        total_quotes=total_quotes,
        low_stock_count=len(low_stock_items),
        low_stock_items=low_stock_items,
        maintenance_machines=maintenance_machines,
        total_revenue=total_revenue,
        total_collected=total_collected,
        outstanding_balance=outstanding_balance,
        total_direct_cash=total_direct_cash,
        direct_cash_entries=direct_cash_entries,
        month_names_json=json.dumps(month_names),
        monthly_revenue_json=json.dumps(monthly_revenue),
        monthly_expenses_json=json.dumps(monthly_expenses),
        expenses_log=all_expenses,
        activity_feed=activity_feed
    )

@app.route('/cash/add', methods=['POST'])
@login_required
def add_direct_cash():
    description = request.form.get('description')
    amount = parse_float(request.form.get('amount'))
    source_client = request.form.get('source_client', 'Walk-in Cash')

    if description and amount > 0:
        cash_entry = DirectCashIncome(
            description=description,
            amount=amount,
            source_client=source_client,
            date_received=datetime.now(),
            received_by=current_user.full_name
        )
        db.session.add(cash_entry)
        db.session.commit()

        log_notification('Direct Cash Received', f'Received {amount:,.3f} TND from {source_client}: {description}', 'Cash', 'banknote', 'text-emerald-400')
        flash(f'Cash payment of {amount:,.3f} TND logged successfully!', 'success')

    return redirect(url_for('dashboard'))

@app.route('/cash/delete/<int:cash_id>', methods=['POST'])
@login_required
def delete_direct_cash(cash_id):
    cash_entry = DirectCashIncome.query.get_or_404(cash_id)
    amount = cash_entry.amount
    db.session.delete(cash_entry)
    db.session.commit()

    log_notification('Cash Entry Removed', f'Removed cash income entry of {amount:,.3f} TND', 'Cash', 'trash-2', 'text-slate-400')
    flash('Cash transaction entry removed.', 'info')
    return redirect(url_for('dashboard'))

# ---------------------------------------------------------------------------
# SETTINGS
# ---------------------------------------------------------------------------
@app.route('/settings')
@login_required
def settings_dashboard():
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

@app.route('/settings/brand/update', methods=['POST'])
@login_required
def update_brand_settings():
    set_setting('brand_name', request.form.get('brand_name'), 'brand')
    set_setting('brand_phone', request.form.get('brand_phone'), 'brand')
    set_setting('brand_email', request.form.get('brand_email'), 'brand')
    set_setting('brand_address', request.form.get('brand_address'), 'brand')
    set_setting('brand_tax_id', request.form.get('brand_tax_id'), 'brand')
    
    if request.form.get('app_theme'):
        set_setting('app_theme', request.form.get('app_theme'), 'brand')

    if 'brand_logo_file' in request.files:
        file = request.files['brand_logo_file']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"logo_{int(datetime.now().timestamp())}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            set_setting('brand_logo', f"/static/uploads/{filename}", 'brand')

    if 'brand_icon_file' in request.files:
        file = request.files['brand_icon_file']
        if file and allowed_file(file.filename):
            filename = secure_filename(f"icon_{int(datetime.now().timestamp())}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            set_setting('brand_icon', f"/static/uploads/{filename}", 'brand')

    log_notification('Brand & Theme Settings Updated', 'Updated business metadata and theme color.', 'Settings', 'settings', 'text-brand')
    flash('Brand & Theme updated successfully!', 'success')
    return redirect(url_for('settings_dashboard'))

@app.route('/settings/pdf/update', methods=['POST'])
@login_required
def update_pdf_settings():
    set_setting('pdf_font_size', request.form.get('pdf_font_size'), 'pdf')
    set_setting('pdf_margin', request.form.get('pdf_margin'), 'pdf')
    set_setting('pdf_header_text', request.form.get('pdf_header_text'), 'pdf')
    flash('PDF preferences updated!', 'success')
    return redirect(url_for('settings_dashboard'))

@app.route('/settings/users/create', methods=['POST'])
@login_required
def create_user():
    username = request.form.get('username')
    email = request.form.get('email')
    full_name = request.form.get('full_name')
    password = request.form.get('password')
    role = request.form.get('role', 'worker')

    if User.query.filter_by(username=username).first():
        flash('Username already exists.', 'error')
        return redirect(url_for('settings_dashboard'))

    new_user = User(
        username=username,
        email=email,
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
    return redirect(url_for('settings_dashboard'))

@app.route('/settings/users/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Cannot delete your active session!', 'error')
        return redirect(url_for('settings_dashboard'))

    user = User.query.get_or_404(user_id)
    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'User "{username}" deleted.', 'info')
    return redirect(url_for('settings_dashboard'))

@app.route('/settings/data/backup-db')
@login_required
def download_database_backup():
    db_path = os.path.join(app.root_path, 'meca_tech.db')
    if os.path.exists(db_path):
        return send_file(db_path, as_attachment=True, download_name=f'meca_tech_backup_{datetime.now().strftime("%Y%m%d_%H%M")}.db')
    flash('Database file not found.', 'error')
    return redirect(url_for('settings_dashboard'))

# ---------------------------------------------------------------------------
# EXPENSES
# ---------------------------------------------------------------------------
@app.route('/expense/add', methods=['POST'])
@login_required
def add_expense():
    category = request.form.get('category')
    desc = request.form.get('description')
    amount = parse_float(request.form.get('amount'))

    if desc and amount > 0:
        new_expense = Expense(category=category, description=desc, amount=amount, date_logged=datetime.now())
        db.session.add(new_expense)
        db.session.commit()
        log_notification(f'Expense Logged ({category})', f'{desc} - Amount: {amount:,.3f} TND', 'Expense', 'wallet', 'text-red-400')
        flash(f'Expense of {amount:,.3f} TND added!', 'success')

    return redirect(url_for('dashboard'))

@app.route('/expense/edit/<int:expense_id>', methods=['POST'])
@login_required
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    expense.category = request.form.get('category')
    expense.description = request.form.get('description')
    expense.amount = parse_float(request.form.get('amount'))
    db.session.commit()
    flash('Expense entry updated successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/expense/delete/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    db.session.delete(expense)
    db.session.commit()
    flash('Expense entry deleted.', 'info')
    return redirect(url_for('dashboard'))

# ---------------------------------------------------------------------------
# CLIENTS
# ---------------------------------------------------------------------------
@app.route('/clients')
@login_required
def clients_list():
    all_clients = Client.query.order_by(Client.company_name.asc()).all()
    return render_template('clients/list.html', clients=all_clients)

@app.route('/clients/view/<int:client_id>')
@login_required
def client_dashboard(client_id):
    client = Client.query.get_or_404(client_id)
    client_quotes = Quote.query.filter_by(client_id=client.id).order_by(Quote.date_created.desc()).all()
    approved_quotes = [q for q in client_quotes if q.status == 'Approved']
    total_billed = sum(q.total_amount for q in approved_quotes)
    total_paid = sum(q.amount_paid for q in client_quotes)
    balance_due = total_billed - total_paid
    return render_template('clients/dashboard.html', client=client, quotes=client_quotes, total_billed=total_billed, total_paid=total_paid, balance_due=balance_due)

@app.route('/clients/create', methods=['GET', 'POST'])
@login_required
def client_create():
    if request.method == 'POST':
        new_client = Client(
            company_name=request.form.get('company_name'),
            contact_name=request.form.get('contact_name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            address=request.form.get('address'),
            tax_id=request.form.get('tax_id')
        )
        db.session.add(new_client)
        db.session.commit()
        log_notification('Client Registered', f'Created profile for: {new_client.company_name}', 'Client', 'users', 'text-blue-400')
        flash(f'Client {new_client.company_name} added!', 'success')
        return redirect(url_for('clients_list'))
    return render_template('clients/create.html')

@app.route('/clients/edit/<int:client_id>', methods=['GET', 'POST'])
@login_required
def client_edit(client_id):
    client = Client.query.get_or_404(client_id)
    if request.method == 'POST':
        client.company_name = request.form.get('company_name')
        client.contact_name = request.form.get('contact_name')
        client.email = request.form.get('email')
        client.phone = request.form.get('phone')
        client.address = request.form.get('address')
        client.tax_id = request.form.get('tax_id')
        db.session.commit()
        flash(f'Client {client.company_name} updated!', 'success')
        return redirect(url_for('clients_list'))
    return render_template('clients/edit.html', client=client)

@app.route('/clients/delete/<int:client_id>', methods=['POST'])
@login_required
def client_delete(client_id):
    client = Client.query.get_or_404(client_id)
    db.session.delete(client)
    db.session.commit()
    flash('Client deleted.', 'info')
    return redirect(url_for('clients_list'))

# ---------------------------------------------------------------------------
# STOCK
# ---------------------------------------------------------------------------
@app.route('/stock')
@login_required
def stock_list():
    all_stock = StockItem.query.order_by(StockItem.name.asc()).all()
    return render_template('stock/list.html', stock=all_stock)

@app.route('/stock/create', methods=['GET', 'POST'])
@login_required
def stock_create():
    if request.method == 'POST':
        new_item = StockItem(
            name=request.form.get('name'),
            quantity=parse_float(request.form.get('quantity')),
            min_stock_alert=parse_float(request.form.get('min_stock_alert'), default=5.0)
        )
        db.session.add(new_item)
        db.session.commit()
        flash(f'Stock item "{new_item.name}" added!', 'success')
        return redirect(url_for('stock_list'))
    return render_template('stock/create.html')

@app.route('/stock/update-qty/<int:item_id>', methods=['POST'])
@login_required
def stock_update_qty(item_id):
    item = StockItem.query.get_or_404(item_id)
    item.quantity = parse_float(request.form.get('quantity'))
    db.session.commit()
    flash(f'Stock for "{item.name}" updated.', 'success')
    return redirect(url_for('stock_list'))

@app.route('/stock/delete/<int:item_id>', methods=['POST'])
@login_required
def stock_delete(item_id):
    item = StockItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash('Stock item removed.', 'info')
    return redirect(url_for('stock_list'))

# ---------------------------------------------------------------------------
# MACHINERY
# ---------------------------------------------------------------------------
@app.route('/machines')
@login_required
def machines_list():
    machines = Machine.query.order_by(Machine.name.asc()).all()
    return render_template('machines/list.html', machines=machines)

@app.route('/machines/create', methods=['GET', 'POST'])
@login_required
def machine_create():
    if request.method == 'POST':
        new_machine = Machine(
            name=request.form.get('name'),
            model_type=request.form.get('model_type'),
            serial_number=request.form.get('serial_number'),
            status=request.form.get('status', 'Operational'),
            notes=request.form.get('notes')
        )
        db.session.add(new_machine)
        db.session.commit()
        flash(f'Machine "{new_machine.name}" registered!', 'success')
        return redirect(url_for('machines_list'))
    return render_template('machines/create.html')

@app.route('/machines/edit/<int:machine_id>', methods=['GET', 'POST'])
@login_required
def machine_edit(machine_id):
    machine = Machine.query.get_or_404(machine_id)
    if request.method == 'POST':
        machine.name = request.form.get('name')
        machine.model_type = request.form.get('model_type')
        machine.serial_number = request.form.get('serial_number')
        machine.notes = request.form.get('notes')
        db.session.commit()
        flash(f'Machine "{machine.name}" updated!', 'success')
        return redirect(url_for('machine_detail', machine_id=machine.id))
    return render_template('machines/edit.html', machine=machine)

@app.route('/machines/view/<int:machine_id>')
@login_required
def machine_detail(machine_id):
    machine = Machine.query.get_or_404(machine_id)
    history_logs = MaintenanceLog.query.filter_by(machine_id=machine.id).order_by(MaintenanceLog.date_logged.desc()).all()
    total_cost = sum(log.cost for log in history_logs)
    return render_template('machines/detail.html', machine=machine, logs=history_logs, total_cost=total_cost)

@app.route('/machines/log-service/<int:machine_id>', methods=['POST'])
@login_required
def machine_log_service(machine_id):
    machine = Machine.query.get_or_404(machine_id)
    new_status = request.form.get('status')
    service_desc = request.form.get('service_description')
    cost = parse_float(request.form.get('cost'))

    machine.status = new_status
    log_entry = MaintenanceLog(
        machine_id=machine.id,
        status_logged=new_status,
        service_description=service_desc,
        cost=cost,
        performed_by=request.form.get('performed_by', current_user.full_name)
    )
    db.session.add(log_entry)

    if cost > 0:
        db.session.add(Expense(
            category='Machine Maintenance',
            description=f"Machine Maintenance ({machine.name}): {service_desc}",
            amount=cost,
            date_logged=datetime.now()
        ))

    db.session.commit()
    flash(f'Maintenance event logged for {machine.name}!', 'success')
    return redirect(url_for('machine_detail', machine_id=machine.id))

# ---------------------------------------------------------------------------
# WORKERS MODULE
# ---------------------------------------------------------------------------
@app.route('/workers')
@login_required
def workers_list():
    workers = Worker.query.order_by(Worker.full_name.asc()).all()
    current_month = datetime.now().month
    current_year = datetime.now().year

    worker_data = []
    for w in workers:
        current_advances = SalaryAdvance.query.filter(
            SalaryAdvance.worker_id == w.id,
            extract('month', SalaryAdvance.date_given) == current_month,
            extract('year', SalaryAdvance.date_given) == current_year
        ).all()
        
        total_advances = sum(a.amount for a in current_advances)
        net_salary = max(0.0, w.monthly_rate - total_advances)

        worker_data.append({
            'worker': w,
            'advances': current_advances,
            'total_advances': total_advances,
            'net_salary': net_salary
        })

    total_payroll = sum(w.monthly_rate for w in workers)
    return render_template('workers/list.html', worker_data=worker_data, total_payroll=total_payroll)

@app.route('/workers/create', methods=['GET', 'POST'])
@login_required
def worker_create():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        role = request.form.get('role')
        phone = request.form.get('phone')
        cin_number = request.form.get('cin_number')
        monthly_rate = parse_float(request.form.get('monthly_rate'))

        linked_user_id = None
        if request.form.get('create_system_account'):
            username = request.form.get('account_username')
            password = request.form.get('account_password')
            email = request.form.get('account_email') or f"{username}@mecatechatia.tn"

            if username and password:
                if not User.query.filter_by(username=username).first():
                    new_user = User(
                        username=username,
                        email=email,
                        full_name=full_name,
                        role='worker',
                        can_manage_stock=bool(request.form.get('can_manage_stock')),
                        can_manage_machines=bool(request.form.get('can_manage_machines'))
                    )
                    new_user.set_password(password)
                    db.session.add(new_user)
                    db.session.flush()
                    linked_user_id = new_user.id

        new_worker = Worker(
            user_id=linked_user_id,
            full_name=full_name,
            role=role,
            phone=phone,
            cin_number=cin_number,
            monthly_rate=monthly_rate,
            hire_date=date.today()
        )
        db.session.add(new_worker)
        db.session.commit()

        log_notification('Worker Registered', f'Added worker {full_name} ({role})', 'Worker', 'user-check', 'text-green-400')
        flash(f'Worker {full_name} added to roster!', 'success')
        return redirect(url_for('workers_list'))

    return render_template('workers/create.html')

@app.route('/workers/edit/<int:worker_id>', methods=['GET', 'POST'])
@login_required
def worker_edit(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    if request.method == 'POST':
        worker.full_name = request.form.get('full_name')
        worker.role = request.form.get('role')
        worker.phone = request.form.get('phone')
        worker.cin_number = request.form.get('cin_number')
        worker.monthly_rate = parse_float(request.form.get('monthly_rate'))
        db.session.commit()
        flash(f'Profile for {worker.full_name} updated!', 'success')
        return redirect(url_for('workers_list'))
    return render_template('workers/edit.html', worker=worker)

@app.route('/workers/advance/add/<int:worker_id>', methods=['POST'])
@login_required
def add_worker_advance(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    amount = parse_float(request.form.get('amount'))
    notes = request.form.get('notes', '')

    if amount > 0:
        advance = SalaryAdvance(
            worker_id=worker.id,
            amount=amount,
            date_given=datetime.now(),
            notes=notes
        )
        db.session.add(advance)

        db.session.add(Expense(
            category='Salary Advance',
            description=f"Salary Advance for {worker.full_name}: {notes}",
            amount=amount,
            date_logged=datetime.now()
        ))
        db.session.commit()

        log_notification('Salary Advance', f'Issued {amount:,.3f} TND advance to {worker.full_name}', 'Worker', 'wallet', 'text-amber-400')
        flash(f'Advance of {amount:,.3f} TND recorded for {worker.full_name}.', 'success')

    return redirect(url_for('workers_list'))

@app.route('/workers/advance/delete/<int:advance_id>', methods=['POST'])
@login_required
def delete_worker_advance(advance_id):
    advance = SalaryAdvance.query.get_or_404(advance_id)
    db.session.delete(advance)
    db.session.commit()
    flash('Salary advance entry deleted.', 'info')
    return redirect(url_for('workers_list'))

@app.route('/workers/calendar/<int:worker_id>')
@login_required
def worker_calendar(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    year = parse_int(request.args.get('year'), default=datetime.now().year)
    month = parse_int(request.args.get('month'), default=datetime.now().month)

    today = date.today()
    hire_date = worker.hire_date or today
    months_employed = max(1, (today.year - hire_date.year) * 12 + (today.month - hire_date.month) + 1)
    total_conge_earned = months_employed * 0.5

    start_date = date(year, month, 1)
    _, days_in_month = calendar.monthrange(year, month)
    end_date = date(year, month, days_in_month)

    attendance_records = WorkerAttendance.query.filter(
        WorkerAttendance.worker_id == worker.id,
        WorkerAttendance.date >= start_date,
        WorkerAttendance.date <= end_date
    ).all()

    attendance_dict = {a.date.day: a.status for a in attendance_records}
    all_conge_count = WorkerAttendance.query.filter_by(worker_id=worker.id, status='Congé').count()
    remaining_conge = max(0.0, total_conge_earned - all_conge_count)

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(year, month)

    days_worked = 0.0
    days_off = 0
    conge_days = 0

    for day_num, status in attendance_dict.items():
        if status == 'Worked':
            day_of_week = calendar.weekday(year, month, day_num)
            if day_of_week == 5:
                days_worked += 0.5
            else:
                days_worked += 1.0
        elif status == 'DayOff':
            days_off += 1
        elif status == 'Congé':
            conge_days += 1

    return render_template(
        'workers/calendar.html',
        worker=worker,
        year=year,
        month=month,
        month_name=calendar.month_name[month],
        month_days=month_days,
        attendance_dict=attendance_dict,
        total_conge_earned=total_conge_earned,
        remaining_conge=remaining_conge,
        days_worked=days_worked,
        days_off=days_off,
        conge_days=conge_days
    )

@app.route('/workers/set-attendance/<int:worker_id>', methods=['POST'])
@login_required
def set_worker_attendance(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    day = parse_int(request.form.get('day'))
    month = parse_int(request.form.get('month'))
    year = parse_int(request.form.get('year'))
    status = request.form.get('status')

    target_date = date(year, month, day)
    existing = WorkerAttendance.query.filter_by(worker_id=worker.id, date=target_date).first()
    if existing:
        existing.status = status
    else:
        db.session.add(WorkerAttendance(worker_id=worker.id, date=target_date, status=status))

    db.session.commit()
    return redirect(url_for('worker_calendar', worker_id=worker.id, year=year, month=month))

@app.route('/workers/delete/<int:worker_id>', methods=['POST'])
@login_required
def worker_delete(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    db.session.delete(worker)
    db.session.commit()
    flash('Worker removed from roster.', 'info')
    return redirect(url_for('workers_list'))

# ---------------------------------------------------------------------------
# QUOTES
# ---------------------------------------------------------------------------
@app.route('/quotes')
@login_required
def quotes_list():
    selected_year = request.args.get('year', type=int)
    selected_month = request.args.get('month', type=int)
    
    query = Quote.query
    if selected_year:
        query = query.filter(extract('year', Quote.date_created) == selected_year)
    if selected_month:
        query = query.filter(extract('month', Quote.date_created) == selected_month)
        
    filtered_quotes = query.order_by(Quote.date_created.desc()).all()
    period_total = sum(q.total_amount for q in filtered_quotes if q.status == 'Approved')
    period_paid = sum(q.amount_paid for q in filtered_quotes)
    
    years_db = db.session.query(extract('year', Quote.date_created)).distinct().all()
    available_years = sorted([int(y[0]) for y in years_db if y[0] is not None], reverse=True)
    if not available_years:
        available_years = [datetime.now().year]
        
    return render_template(
        'quotes/list.html', 
        quotes=filtered_quotes,
        selected_year=selected_year,
        selected_month=selected_month,
        available_years=available_years,
        period_total=period_total,
        period_paid=period_paid
    )

@app.route('/quotes/create', methods=['GET', 'POST'])
@login_required
def quote_create():
    clients = Client.query.all()
    auto_ref = generate_monthly_ref()
    
    if request.method == 'POST':
        quote_num = request.form.get('quote_number') or auto_ref
        client_id = parse_int(request.form.get('client_id'))
        
        remarque = request.form.get('remarque', '')
        payment_terms = request.form.get('payment_terms', 'Paiement à la livraison / Chèque')
        validite_offre = request.form.get('validite_offre', '30 Jours')
        delai_livraison = request.form.get('delai_livraison', 'Selon disponibilité du stock / Planning atelier')
        mode_expedition = request.form.get('mode_expedition', 'Par nos soins / Transport client')
        
        notes = request.form.get('notes', '')
        discount_rate = parse_float(request.form.get('discount_rate'))
        
        driver_name = request.form.get('driver_name', '')
        driver_cin = request.form.get('driver_cin', '')
        vehicle_plate = request.form.get('vehicle_plate', '')
        
        descriptions = request.form.getlist('item_description[]')
        quantities = request.form.getlist('item_quantity[]')
        unit_rates = request.form.getlist('item_rate[]')
        
        subtotal = 0.0
        items_to_add = []
        for idx, desc in enumerate(descriptions):
            if desc.strip():
                qty = parse_float(quantities[idx] if idx < len(quantities) else 1.0, default=1.0)
                rate = parse_float(unit_rates[idx] if idx < len(unit_rates) else 0.0)
                total = qty * rate
                subtotal += total
                items_to_add.append(QuoteItem(
                    item_order=idx + 1,
                    description=desc,
                    quantity=qty,
                    unit_rate=rate,
                    total_price=total
                ))
                
        discount_amt = subtotal * (discount_rate / 100.0)
        after_discount = subtotal - discount_amt
        tax_amt = after_discount * 0.19
        stamp_tax = 1.000
        total_amt = after_discount + tax_amt + stamp_tax
        words_text = f"Arrêté la présente offre à la somme de : {format_amount_in_words(total_amt)}."
        
        new_quote = Quote(
            quote_number=quote_num,
            client_id=client_id,
            subtotal=subtotal,
            discount_rate=discount_rate,
            discount_amount=discount_amt,
            tax_rate=19.0,
            tax_amount=tax_amt,
            stamp_tax=stamp_tax,
            total_amount=total_amt,
            total_in_words=words_text,
            remarque=remarque,
            payment_terms=payment_terms,
            validite_offre=validite_offre,
            delai_livraison=delai_livraison,
            mode_expedition=mode_expedition,
            notes=notes,
            driver_name=driver_name,
            driver_cin=driver_cin,
            vehicle_plate=vehicle_plate,
            status='Draft',
            amount_paid=0.0,
            payment_status='Unpaid'
        )
        new_quote.items.extend(items_to_add)
        db.session.add(new_quote)
        db.session.commit()
        
        flash(f'Document {quote_num} created successfully!', 'success')
        return redirect(url_for('quotes_list'))
        
    return render_template('quotes/create.html', clients=clients, auto_ref=auto_ref)

@app.route('/quotes/update-status/<int:quote_id>', methods=['POST'])
@login_required
def update_quote_status(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    new_status = request.form.get('status')
    if new_status:
        quote.status = new_status
        db.session.commit()
        flash(f'Status for #{quote.quote_number} updated to {new_status}.', 'success')
    return redirect(request.referrer or url_for('quotes_list'))

@app.route('/quotes/add-payment/<int:quote_id>', methods=['POST'])
@login_required
def add_quote_payment(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    added_amount = parse_float(request.form.get('add_amount'))

    if added_amount > 0:
        db.session.add(PaymentHistory(
            quote_id=quote.id,
            amount=added_amount,
            payment_date=datetime.now(),
            payment_method=request.form.get('payment_method', 'Espèces / Chèque'),
            notes=request.form.get('notes', '')
        ))
        db.session.flush()
        quote.recalculate_payment_status()
        db.session.commit()
        flash(f'Payment of {added_amount:,.3f} TND recorded for #{quote.quote_number}.', 'success')

    return redirect(request.referrer or url_for('quotes_list'))

@app.route('/quotes/delete/<int:quote_id>', methods=['POST'])
@login_required
def quote_delete(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    db.session.delete(quote)
    db.session.commit()
    flash('Quote deleted.', 'info')
    return redirect(url_for('quotes_list'))

@app.route('/quotes/print/<int:quote_id>')
@login_required
def quote_print(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    return render_template('quotes/print.html', quote=quote, pdf_font_size=get_setting('pdf_font_size', '11'), pdf_margin=get_setting('pdf_margin', '10'))

@app.route('/quotes/invoice/<int:quote_id>')
@login_required
def invoice_print(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    return render_template('quotes/invoice.html', quote=quote, pdf_font_size=get_setting('pdf_font_size', '11'), pdf_margin=get_setting('pdf_margin', '10'))

@app.route('/quotes/bon-livraison/<int:quote_id>')
@login_required
def bon_livraison_print(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    return render_template('quotes/bon_livraison.html', quote=quote, pdf_font_size=get_setting('pdf_font_size', '11'), pdf_margin=get_setting('pdf_margin', '10'))

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=8080)