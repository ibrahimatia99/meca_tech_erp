import os
import re
import json
import calendar
from datetime import datetime, date
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from num2words import num2words
from sqlalchemy import extract

from models import (
    db, User, Client, Supplier, Quote, QuoteItem, PaymentHistory,
    StockItem, Machine, MaintenanceLog, 
    Worker, WorkerAttendance, Expense, AuditLog
)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'meca-tech-atia-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///meca_tech.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------------------------------------------------------------------------
# UTILITY HELPER FUNCTIONS (DEFENSIVE TYPE PARSING)
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
                
    next_seq = max_seq + 1
    return f"DEV-MTA-{month_str}-{next_seq}"


def init_db():
    with app.app_context():
        db.create_all()
        
        if not User.query.filter_by(username='admin').first():
            admin_user = User(
                username='admin',
                email='admin@mecatechatia.tn',
                full_name='Ibrahim Atia',
                role='admin'
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            
        if not Client.query.filter_by(company_name='SIGA METAL').first():
            siga_client = Client(
                company_name='SIGA METAL',
                contact_name='Hamza Atia',
                email='hamzaatia1991@gmail.com',
                phone='+216 99 000 000',
                address='Tunisia',
                tax_id='1234567/A/M/000'
            )
            db.session.add(siga_client)
            db.session.commit()
            log_notification('New Client Added', 'Client SIGA METAL was registered in system.', 'Client', 'users', 'text-brand')

        if Machine.query.count() == 0:
            m1 = Machine(name='Press Brake Machine', model_type='Hydraulic CNC 100T', serial_number='PB-2024-001', status='Operational')
            m2 = Machine(name='MIG/MAG Welding Station', model_type='Industrial 400A', serial_number='WS-2023-012', status='Operational')
            db.session.add_all([m1, m2])
            db.session.commit()


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
        else:
            flash('Invalid username or password.', 'error')
            
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
@app.route('/')
@login_required
def dashboard():
    total_clients = Client.query.count()
    total_quotes = Quote.query.count()
    low_stock_items = StockItem.query.filter(StockItem.quantity <= StockItem.min_stock_alert).all()
    maintenance_machines = Machine.query.filter(Machine.status != 'Operational').all()

    approved_quotes = Quote.query.filter_by(status='Approved').all()
    all_quotes = Quote.query.all()

    total_revenue = sum(q.total_amount for q in approved_quotes)
    total_collected = sum(q.amount_paid for q in all_quotes)
    outstanding_balance = total_revenue - total_collected

    current_year = datetime.now().year
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    monthly_revenue = [0.0] * 12
    monthly_expenses = [0.0] * 12

    for q in approved_quotes:
        if q.date_created.year == current_year:
            m = q.date_created.month - 1
            monthly_revenue[m] += q.total_amount

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
        month_names_json=json.dumps(month_names),
        monthly_revenue_json=json.dumps(monthly_revenue),
        monthly_expenses_json=json.dumps(monthly_expenses),
        expenses_log=all_expenses,
        activity_feed=activity_feed
    )


# ---------------------------------------------------------------------------
# EXPENSES MANAGEMENT
# ---------------------------------------------------------------------------
@app.route('/expense/add', methods=['POST'])
@login_required
def add_expense():
    category = request.form.get('category')
    desc = request.form.get('description')
    amount = parse_float(request.form.get('amount'))

    if desc and amount > 0:
        new_expense = Expense(
            category=category,
            description=desc,
            amount=amount,
            date_logged=datetime.now()
        )
        db.session.add(new_expense)
        db.session.commit()

        log_notification(f'Expense Logged ({category})', f'{desc} - Amount: {amount:,.3f} TND', 'Expense', 'wallet', 'text-red-400')
        flash(f'Expense of {amount:,.3f} TND added successfully!', 'success')

    return redirect(url_for('dashboard'))


@app.route('/expense/edit/<int:expense_id>', methods=['POST'])
@login_required
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    expense.category = request.form.get('category')
    expense.description = request.form.get('description')
    expense.amount = parse_float(request.form.get('amount'))

    db.session.commit()

    log_notification('Expense Updated', f'Updated {expense.description} to {expense.amount:,.3f} TND', 'Expense', 'edit-3', 'text-amber-400')
    flash('Expense entry updated successfully!', 'success')
    return redirect(url_for('dashboard'))


@app.route('/expense/delete/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    desc = expense.description
    amount = expense.amount
    
    db.session.delete(expense)
    db.session.commit()

    log_notification('Expense Removed', f'Deleted expense: {desc} ({amount:,.3f} TND)', 'Expense', 'trash-2', 'text-slate-400')
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
    
    return render_template(
        'clients/dashboard.html', 
        client=client, 
        quotes=client_quotes,
        total_billed=total_billed,
        total_paid=total_paid,
        balance_due=balance_due
    )


@app.route('/clients/create', methods=['GET', 'POST'])
@login_required
def client_create():
    if request.method == 'POST':
        company_name = request.form.get('company_name')
        contact_name = request.form.get('contact_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        address = request.form.get('address')
        tax_id = request.form.get('tax_id')

        new_client = Client(
            company_name=company_name,
            contact_name=contact_name,
            email=email,
            phone=phone,
            address=address,
            tax_id=tax_id
        )
        db.session.add(new_client)
        db.session.commit()

        log_notification('Client Registered', f'Created profile for client: {company_name}', 'Client', 'users', 'text-blue-400')
        flash(f'Client {company_name} added successfully!', 'success')
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
        log_notification('Client Profile Updated', f'Updated details for {client.company_name}', 'Client', 'user-check', 'text-blue-400')
        flash(f'Client {client.company_name} updated successfully!', 'success')
        return redirect(url_for('clients_list'))

    return render_template('clients/edit.html', client=client)


@app.route('/clients/delete/<int:client_id>', methods=['POST'])
@login_required
def client_delete(client_id):
    client = Client.query.get_or_404(client_id)
    company_name = client.company_name
    db.session.delete(client)
    db.session.commit()

    log_notification('Client Deleted', f'Removed client {company_name} from database', 'Client', 'trash-2', 'text-red-400')
    flash(f'Client {company_name} deleted.', 'info')
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
        name = request.form.get('name')
        qty = parse_float(request.form.get('quantity'))
        min_alert = parse_float(request.form.get('min_stock_alert'), default=5.0)

        new_item = StockItem(
            name=name,
            quantity=qty,
            min_stock_alert=min_alert
        )
        db.session.add(new_item)
        db.session.commit()

        log_notification('Stock Item Created', f'Added material: {name} (Qty: {qty})', 'Stock', 'boxes', 'text-green-400')
        flash(f'Stock item "{name}" added successfully!', 'success')
        return redirect(url_for('stock_list'))

    return render_template('stock/create.html')


@app.route('/stock/update-qty/<int:item_id>', methods=['POST'])
@login_required
def stock_update_qty(item_id):
    item = StockItem.query.get_or_404(item_id)
    new_qty = parse_float(request.form.get('quantity'))
    item.quantity = new_qty
    db.session.commit()

    log_notification('Stock Level Changed', f'Adjusted {item.name} quantity to {new_qty}', 'Stock', 'boxes', 'text-green-400')
    flash(f'Stock for "{item.name}" updated to {item.quantity} units.', 'success')
    return redirect(url_for('stock_list'))


@app.route('/stock/delete/<int:item_id>', methods=['POST'])
@login_required
def stock_delete(item_id):
    item = StockItem.query.get_or_404(item_id)
    name = item.name
    db.session.delete(item)
    db.session.commit()

    log_notification('Stock Item Removed', f'Deleted material item {name}', 'Stock', 'trash-2', 'text-red-400')
    flash(f'Stock item "{name}" removed.', 'info')
    return redirect(url_for('stock_list'))


# ---------------------------------------------------------------------------
# MACHINERY (AUTO-LOGS REPAIR COST TO DASHBOARD EXPENSES)
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
        name = request.form.get('name')
        model_type = request.form.get('model_type')
        serial_number = request.form.get('serial_number')
        status = request.form.get('status', 'Operational')
        notes = request.form.get('notes')

        new_machine = Machine(
            name=name,
            model_type=model_type,
            serial_number=serial_number,
            status=status,
            notes=notes
        )
        db.session.add(new_machine)
        db.session.commit()

        log_notification('Machine Added', f'Registered machine {name} ({model_type})', 'Machine', 'cpu', 'text-amber-400')
        flash(f'Machine "{name}" registered successfully!', 'success')
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
        log_notification('Machine Updated', f'Updated details for {machine.name}', 'Machine', 'cpu', 'text-amber-400')
        flash(f'Machine "{machine.name}" details updated!', 'success')
        return redirect(url_for('machine_detail', machine_id=machine.id))

    return render_template('machines/edit.html', machine=machine)


@app.route('/machines/view/<int:machine_id>')
@login_required
def machine_detail(machine_id):
    machine = Machine.query.get_or_404(machine_id)
    history_logs = MaintenanceLog.query.filter_by(machine_id=machine.id).order_by(MaintenanceLog.date_logged.desc()).all()
    total_maintenance_cost = sum(log.cost for log in history_logs)
    
    return render_template(
        'machines/detail.html', 
        machine=machine, 
        logs=history_logs,
        total_cost=total_maintenance_cost
    )


@app.route('/machines/log-service/<int:machine_id>', methods=['POST'])
@login_required
def machine_log_service(machine_id):
    machine = Machine.query.get_or_404(machine_id)
    new_status = request.form.get('status')
    service_desc = request.form.get('service_description')
    
    cost = parse_float(request.form.get('cost'))
    performed_by = request.form.get('performed_by', current_user.full_name)

    machine.status = new_status

    # 1. Save Maintenance Log Entry
    log_entry = MaintenanceLog(
        machine_id=machine.id,
        status_logged=new_status,
        service_description=service_desc,
        cost=cost,
        performed_by=performed_by
    )
    db.session.add(log_entry)

    # 2. Automatically sync to Overhead Expenses if cost > 0
    if cost > 0:
        maintenance_expense = Expense(
            category='Machine Maintenance',
            description=f"Machine Maintenance ({machine.name}): {service_desc}",
            amount=cost,
            date_logged=datetime.now()
        )
        db.session.add(maintenance_expense)

    db.session.commit()

    log_notification('Machine Service Logged', f'{machine.name} status: {new_status} | Cost: {cost:,.3f} TND', 'Machine', 'cpu', 'text-amber-400')
    flash(f'Maintenance event logged for {machine.name}! Cost ({cost:,.3f} TND) added to dashboard expenses.', 'success')
    return redirect(url_for('machine_detail', machine_id=machine.id))


# ---------------------------------------------------------------------------
# WORKERS MANAGEMENT
# ---------------------------------------------------------------------------
@app.route('/workers')
@login_required
def workers_list():
    workers = Worker.query.order_by(Worker.full_name.asc()).all()
    total_payroll = sum(w.monthly_rate for w in workers)
    return render_template('workers/list.html', workers=workers, total_payroll=total_payroll)


@app.route('/workers/create', methods=['GET', 'POST'])
@login_required
def worker_create():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        role = request.form.get('role')
        phone = request.form.get('phone')
        cin_number = request.form.get('cin_number')
        monthly_rate = parse_float(request.form.get('monthly_rate'))

        new_worker = Worker(
            full_name=full_name,
            role=role,
            phone=phone,
            cin_number=cin_number,
            monthly_rate=monthly_rate,
            hire_date=date.today()
        )
        db.session.add(new_worker)
        db.session.commit()

        log_notification('Worker Added', f'Added worker {full_name} ({role}) - Rate: {monthly_rate:,.3f} TND', 'Worker', 'user-check', 'text-green-400')
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
        log_notification('Worker Updated', f'Updated profile for {worker.full_name}', 'Worker', 'user-check', 'text-blue-400')
        flash(f'Worker profile for {worker.full_name} updated!', 'success')
        return redirect(url_for('workers_list'))

    return render_template('workers/edit.html', worker=worker)


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
        new_att = WorkerAttendance(worker_id=worker.id, date=target_date, status=status)
        db.session.add(new_att)

    db.session.commit()

    log_notification('Attendance Updated', f'Updated attendance for {worker.full_name} on {target_date.strftime("%Y-%m-%d")} to {status}', 'Worker', 'calendar', 'text-blue-400')
    return redirect(url_for('worker_calendar', worker_id=worker.id, year=year, month=month))


@app.route('/workers/delete/<int:worker_id>', methods=['POST'])
@login_required
def worker_delete(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    name = worker.full_name
    db.session.delete(worker)
    db.session.commit()

    log_notification('Worker Deleted', f'Removed worker {name} from roster', 'Worker', 'trash-2', 'text-red-400')
    flash(f'Worker {name} removed from roster.', 'info')
    return redirect(url_for('workers_list'))


# ---------------------------------------------------------------------------
# QUOTES MANAGEMENT
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
                
                item = QuoteItem(
                    item_order=idx + 1,
                    description=desc,
                    quantity=qty,
                    unit_rate=rate,
                    total_price=total
                )
                items_to_add.append(item)
                
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
        
        client_obj = Client.query.get(client_id)
        client_name = client_obj.company_name if client_obj else "Client"
        log_notification('Quote Created', f'Quote #{quote_num} generated for {client_name} - Total: {total_amt:,.3f} TND', 'Quote', 'file-text', 'text-brand')
        
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
        log_notification('Quote Status Changed', f'Document #{quote.quote_number} status updated to {new_status}', 'Quote', 'file-text', 'text-brand')
        flash(f'Status for #{quote.quote_number} updated to {new_status}.', 'success')
    return redirect(request.referrer or url_for('quotes_list'))


@app.route('/quotes/add-payment/<int:quote_id>', methods=['POST'])
@login_required
def add_quote_payment(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    added_amount = parse_float(request.form.get('add_amount'))
    payment_method = request.form.get('payment_method', 'Espèces / Chèque')
    notes = request.form.get('notes', '')

    if added_amount > 0:
        p_entry = PaymentHistory(
            quote_id=quote.id,
            amount=added_amount,
            payment_date=datetime.now(),
            payment_method=payment_method,
            notes=notes
        )
        db.session.add(p_entry)
        db.session.flush()

        quote.recalculate_payment_status()
        db.session.commit()

        log_notification('Payment Received', f'Added payment of {added_amount:,.3f} TND for #{quote.quote_number}', 'Quote', 'wallet', 'text-green-400')
        flash(f'Payment of {added_amount:,.3f} TND recorded for #{quote.quote_number}.', 'success')

    return redirect(request.referrer or url_for('quotes_list'))


@app.route('/quotes/edit-payment/<int:payment_id>', methods=['POST'])
@login_required
def edit_quote_payment(payment_id):
    payment = PaymentHistory.query.get_or_404(payment_id)
    quote = Quote.query.get_or_404(payment.quote_id)

    payment.amount = parse_float(request.form.get('amount'))
    payment.payment_method = request.form.get('payment_method')
    payment.notes = request.form.get('notes')

    date_str = request.form.get('payment_date')
    if date_str:
        try:
            payment.payment_date = datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            pass

    quote.recalculate_payment_status()
    db.session.commit()

    log_notification('Payment Edited', f'Modified payment entry for #{quote.quote_number} (New: {payment.amount:,.3f} TND)', 'Quote', 'edit-3', 'text-amber-400')
    flash('Payment entry updated successfully.', 'success')
    return redirect(request.referrer or url_for('quotes_list'))


@app.route('/quotes/delete-payment/<int:payment_id>', methods=['POST'])
@login_required
def delete_quote_payment(payment_id):
    payment = PaymentHistory.query.get_or_404(payment_id)
    quote = Quote.query.get_or_404(payment.quote_id)
    deleted_amt = payment.amount

    db.session.delete(payment)
    db.session.flush()

    quote.recalculate_payment_status()
    db.session.commit()

    log_notification('Payment Deleted', f'Removed payment entry of {deleted_amt:,.3f} TND from #{quote.quote_number}', 'Quote', 'trash-2', 'text-red-400')
    flash('Payment entry removed.', 'info')
    return redirect(request.referrer or url_for('quotes_list'))


@app.route('/quotes/delete/<int:quote_id>', methods=['POST'])
@login_required
def quote_delete(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    ref = quote.quote_number
    db.session.delete(quote)
    db.session.commit()

    log_notification('Quote Deleted', f'Deleted quote document #{ref}', 'Quote', 'trash-2', 'text-red-400')
    flash(f'Quote #{ref} deleted.', 'info')
    return redirect(url_for('quotes_list'))


@app.route('/quotes/print/<int:quote_id>')
@login_required
def quote_print(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    return render_template('quotes/print.html', quote=quote)


@app.route('/quotes/invoice/<int:quote_id>')
@login_required
def invoice_print(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    paid_pct = (quote.amount_paid / quote.total_amount * 100) if quote.total_amount > 0 else 0
    return render_template('quotes/invoice.html', quote=quote, paid_pct=paid_pct)


@app.route('/quotes/bon-livraison/<int:quote_id>')
@login_required
def bon_livraison_print(quote_id):
    quote = Quote.query.get_or_404(quote_id)
    return render_template('quotes/bon_livraison.html', quote=quote)


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=8080)