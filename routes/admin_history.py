import calendar
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import extract

from models import Quote, DirectCashIncome, Expense, MaintenanceLog

admin_history_bp = Blueprint('admin_history', __name__, url_prefix='/history')

@admin_history_bp.route('/')
@login_required
def admin_history():
    if current_user.role != 'admin' and not current_user.can_manage_expenses:
        flash('Access denied to Financial Archives.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    earliest_quote = Quote.query.order_by(Quote.date_created.asc()).first()
    earliest_cash = DirectCashIncome.query.order_by(DirectCashIncome.date_received.asc()).first()
    earliest_exp = Expense.query.order_by(Expense.date_logged.asc()).first()

    dates = []
    if earliest_quote and earliest_quote.date_created:
        dates.append(earliest_quote.date_created)
    if earliest_cash and earliest_cash.date_received:
        dates.append(earliest_cash.date_received)
    if earliest_exp and earliest_exp.date_logged:
        dates.append(earliest_exp.date_logged)

    start_year = min([d.year for d in dates]) if dates else datetime.now().year
    start_month = min([d.month for d in dates if d.year == start_year]) if dates else datetime.now().month

    now = datetime.now()
    cur_year = now.year
    cur_month = now.month

    history_records = []
    y = cur_year
    m = cur_month

    while (y > start_year) or (y == start_year and m >= start_month):
        month_quotes = Quote.query.filter(
            Quote.status == 'Approved',
            extract('year', Quote.date_created) == y,
            extract('month', Quote.date_created) == m
        ).all()
        billed_rev = sum(q.total_amount for q in month_quotes)

        month_cash = DirectCashIncome.query.filter(
            extract('year', DirectCashIncome.date_received) == y,
            extract('month', DirectCashIncome.date_received) == m
        ).all()
        cash_rev = sum(c.amount for c in month_cash)

        month_exp = Expense.query.filter(
            extract('year', Expense.date_logged) == y,
            extract('month', Expense.date_logged) == m
        ).all()
        tot_exp = sum(e.amount for e in month_exp)

        tot_rev = billed_rev + cash_rev
        net_prof = tot_rev - tot_exp
        margin = (net_prof / tot_rev * 100.0) if tot_rev > 0 else 0.0

        history_records.append({
            'year': y,
            'month': m,
            'month_name': calendar.month_name[m],
            'billed_revenue': billed_rev,
            'cash_revenue': cash_rev,
            'total_revenue': tot_rev,
            'total_expenses': tot_exp,
            'net_profit': net_prof,
            'margin_pct': margin
        })

        m -= 1
        if m == 0:
            m = 12
            y -= 1

    total_billed_all_time = sum(r['billed_revenue'] for r in history_records)
    total_cash_all_time = sum(r['cash_revenue'] for r in history_records)
    lifetime_revenue = total_billed_all_time + total_cash_all_time
    total_expenses_all_time = sum(r['total_expenses'] for r in history_records)
    lifetime_profit = lifetime_revenue - total_expenses_all_time

    return render_template(
        'admin/history.html',
        history_records=history_records,
        total_billed_all_time=total_billed_all_time,
        total_cash_all_time=total_cash_all_time,
        lifetime_revenue=lifetime_revenue,
        total_expenses_all_time=total_expenses_all_time,
        lifetime_profit=lifetime_profit
    )

@admin_history_bp.route('/<int:year>/<int:month>')
@login_required
def admin_month_detail(year, month):
    if current_user.role != 'admin' and not current_user.can_manage_expenses:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    month_quotes = Quote.query.filter(
        Quote.status == 'Approved',
        extract('year', Quote.date_created) == year,
        extract('month', Quote.date_created) == month
    ).order_by(Quote.date_created.desc()).all()

    month_cash = DirectCashIncome.query.filter(
        extract('year', DirectCashIncome.date_received) == year,
        extract('month', DirectCashIncome.date_received) == month
    ).order_by(DirectCashIncome.date_received.desc()).all()

    month_expenses = Expense.query.filter(
        extract('year', Expense.date_logged) == year,
        extract('month', Expense.date_logged) == month
    ).order_by(Expense.date_logged.desc()).all()

    month_maintenance = MaintenanceLog.query.filter(
        extract('year', MaintenanceLog.date_logged) == year,
        extract('month', MaintenanceLog.date_logged) == month
    ).order_by(MaintenanceLog.date_logged.desc()).all()

    billed_revenue = sum(q.total_amount for q in month_quotes)
    cash_revenue = sum(c.amount for c in month_cash)
    total_revenue = billed_revenue + cash_revenue
    total_expenses = sum(e.amount for e in month_expenses)
    net_profit = total_revenue - total_expenses
    margin_pct = (net_profit / total_revenue * 100.0) if total_revenue > 0 else 0.0

    return render_template(
        'admin/month_detail.html',
        year=year,
        month=month,
        month_name=calendar.month_name[month],
        month_quotes=month_quotes,
        month_cash=month_cash,
        month_expenses=month_expenses,
        month_maintenance=month_maintenance,
        billed_revenue=billed_revenue,
        cash_revenue=cash_revenue,
        total_revenue=total_revenue,
        total_expenses=total_expenses,
        net_profit=net_profit,
        margin_pct=margin_pct
    )