from datetime import datetime
from flask import Blueprint, redirect, url_for, flash, request
from flask_login import login_required, current_user

from extensions import db
from models import DirectCashIncome
from utils.helpers import parse_float, log_notification

cash_bp = Blueprint('cash', __name__, url_prefix='/cash')

@cash_bp.route('/add', methods=['POST'])
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

    return redirect(url_for('auth.dashboard'))

@cash_bp.route('/edit/<int:cash_id>', methods=['POST'])
@login_required
def edit_direct_cash(cash_id):
    cash_entry = DirectCashIncome.query.get_or_404(cash_id)
    description = request.form.get('description')
    amount = parse_float(request.form.get('amount'))
    source_client = request.form.get('source_client', 'Walk-in Cash')

    if description and amount > 0:
        cash_entry.description = description
        cash_entry.amount = amount
        cash_entry.source_client = source_client
        db.session.commit()
        flash('Direct cash entry updated successfully!', 'success')

    return redirect(url_for('auth.dashboard'))

@cash_bp.route('/delete/<int:cash_id>', methods=['POST'])
@login_required
def delete_direct_cash(cash_id):
    cash_entry = DirectCashIncome.query.get_or_404(cash_id)
    amount = cash_entry.amount
    db.session.delete(cash_entry)
    db.session.commit()

    log_notification('Cash Entry Removed', f'Removed cash income entry of {amount:,.3f} TND', 'Cash', 'trash-2', 'text-slate-400')
    flash('Cash transaction entry removed.', 'info')
    return redirect(url_for('auth.dashboard'))