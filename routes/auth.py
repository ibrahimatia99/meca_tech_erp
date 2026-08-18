import json
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app
from flask_login import login_user, logout_user, login_required, current_user

from models import User, Client, Quote, StockItem, Machine, DirectCashIncome, Expense, AuditLog

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@auth_bp.route('/login', methods=['GET', 'POST'], endpoint='login')
def login():
    if current_user.is_authenticated:
        if current_user.role == 'worker':
            return redirect(url_for('worker_portal.worker_dashboard'))
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            if user.role == 'worker':
                return redirect(url_for('worker_portal.worker_dashboard'))
            return redirect(url_for('auth.dashboard'))
        flash('Invalid credentials.', 'error')
    return render_template('login.html')

@auth_bp.route('/logout', endpoint='logout')
@login_required
def logout():
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('auth.login'))

@auth_bp.route('/', endpoint='dashboard')
@auth_bp.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'worker':
        return redirect(url_for('worker_portal.worker_dashboard'))

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