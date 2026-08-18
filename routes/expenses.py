from datetime import datetime
from flask import Blueprint, redirect, url_for, flash, request
from flask_login import login_required

from extensions import db
from models import Expense
from utils.helpers import parse_float, log_notification

expenses_bp = Blueprint('expenses', __name__, url_prefix='/expense')

@expenses_bp.route('/add', methods=['POST'])
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

    return redirect(url_for('auth.dashboard'))

@expenses_bp.route('/edit/<int:expense_id>', methods=['POST'])
@login_required
def edit_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    expense.category = request.form.get('category')
    expense.description = request.form.get('description')
    expense.amount = parse_float(request.form.get('amount'))
    db.session.commit()
    flash('Expense entry updated successfully!', 'success')
    return redirect(url_for('auth.dashboard'))

@expenses_bp.route('/delete/<int:expense_id>', methods=['POST'])
@login_required
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    db.session.delete(expense)
    db.session.commit()
    flash('Expense entry deleted.', 'info')
    return redirect(url_for('auth.dashboard'))