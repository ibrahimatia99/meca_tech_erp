import calendar
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import extract

from models import Worker, SalaryAdvance, WorkerAttendance
from utils.helpers import format_amount_in_words

worker_portal_bp = Blueprint('worker_portal', __name__, url_prefix='/worker')

@worker_portal_bp.route('/dashboard')
@login_required
def worker_dashboard():
    worker = Worker.query.filter_by(user_id=current_user.id).first() or Worker.query.filter_by(full_name=current_user.full_name).first()

    current_month = datetime.now().month
    current_year = datetime.now().year
    
    monthly_rate = worker.monthly_rate if worker else 0.0
    worker_id = worker.id if worker else 0

    advances = SalaryAdvance.query.filter(
        SalaryAdvance.worker_id == worker_id,
        extract('month', SalaryAdvance.date_given) == current_month,
        extract('year', SalaryAdvance.date_given) == current_year
    ).order_by(SalaryAdvance.date_given.desc()).all()

    total_advances = sum(a.amount for a in advances)
    net_salary = max(0.0, monthly_rate - total_advances)

    start_date = date(current_year, current_month, 1)
    _, days_in_month = calendar.monthrange(current_year, current_month)
    end_date = date(current_year, current_month, days_in_month)

    attendance_records = WorkerAttendance.query.filter(
        WorkerAttendance.worker_id == worker_id,
        WorkerAttendance.date >= start_date,
        WorkerAttendance.date <= end_date
    ).all()

    attendance_dict = {a.date.day: a.status for a in attendance_records}

    days_worked = 0.0
    days_off = 0
    conge_days = 0

    for day_num, status in attendance_dict.items():
        if status == 'Worked':
            day_of_week = calendar.weekday(current_year, current_month, day_num)
            if day_of_week == 5:
                days_worked += 0.5
            else:
                days_worked += 1.0
        elif status == 'DayOff':
            days_off += 1
        elif status == 'Congé':
            conge_days += 1

    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(current_year, current_month)

    return render_template(
        'worker/dashboard.html',
        worker=worker,
        monthly_rate=monthly_rate,
        advances=advances,
        total_advances=total_advances,
        net_salary=net_salary,
        days_worked=days_worked,
        days_off=days_off,
        conge_days=conge_days,
        month_name=calendar.month_name[current_month],
        current_year=current_year,
        month_days=month_days,
        attendance_dict=attendance_dict
    )

@worker_portal_bp.route('/history')
@login_required
def worker_history():
    worker = Worker.query.filter_by(user_id=current_user.id).first() or Worker.query.filter_by(full_name=current_user.full_name).first()
    if not worker:
        flash("Worker profile not found.", "error")
        return redirect(url_for('worker_portal.worker_dashboard'))

    today = date.today()
    history_records = []
    current_m = today.month
    current_y = today.year

    for i in range(12):
        calc_month = current_m - i
        calc_year = current_y
        while calc_month <= 0:
            calc_month += 12
            calc_year -= 1

        m_advances = SalaryAdvance.query.filter(
            SalaryAdvance.worker_id == worker.id,
            extract('month', SalaryAdvance.date_given) == calc_month,
            extract('year', SalaryAdvance.date_given) == calc_year
        ).all()

        total_adv = sum(a.amount for a in m_advances)

        start_date = date(calc_year, calc_month, 1)
        _, days_in_month = calendar.monthrange(calc_year, calc_month)
        end_date = date(calc_year, calc_month, days_in_month)

        attendance = WorkerAttendance.query.filter(
            WorkerAttendance.worker_id == worker.id,
            WorkerAttendance.date >= start_date,
            WorkerAttendance.date <= end_date
        ).all()

        days_worked = 0.0
        for att in attendance:
            if att.status == 'Worked':
                if calendar.weekday(att.date.year, att.date.month, att.date.day) == 5:
                    days_worked += 0.5
                else:
                    days_worked += 1.0

        if days_worked > 0 or len(m_advances) > 0:
            net_pay = max(0.0, worker.monthly_rate - total_adv)

            history_records.append({
                'year': calc_year,
                'month': calc_month,
                'month_name': calendar.month_name[calc_month],
                'base_rate': worker.monthly_rate,
                'days_worked': days_worked,
                'advances_count': len(m_advances),
                'total_advances': total_adv,
                'net_pay': net_pay
            })

    return render_template('worker/history.html', worker=worker, history_records=history_records)

@worker_portal_bp.route('/fiche-de-paie/<int:year>/<int:month>')
@login_required
def print_fiche_de_paie(year, month):
    worker = Worker.query.filter_by(user_id=current_user.id).first() or Worker.query.filter_by(full_name=current_user.full_name).first()
    if not worker and current_user.role != 'admin':
        flash("Unauthorized access.", "error")
        return redirect(url_for('auth.dashboard'))

    target_worker_id = request.args.get('worker_id', type=int)
    if current_user.role == 'admin' and target_worker_id:
        worker = Worker.query.get_or_404(target_worker_id)

    advances = SalaryAdvance.query.filter(
        SalaryAdvance.worker_id == worker.id,
        extract('month', SalaryAdvance.date_given) == month,
        extract('year', SalaryAdvance.date_given) == year
    ).all()

    total_advances = sum(a.amount for a in advances)
    net_salary = max(0.0, worker.monthly_rate - total_advances)
    net_in_words = format_amount_in_words(net_salary)

    start_date = date(year, month, 1)
    _, days_in_month = calendar.monthrange(year, month)
    end_date = date(year, month, days_in_month)

    attendance = WorkerAttendance.query.filter(
        WorkerAttendance.worker_id == worker.id,
        WorkerAttendance.date >= start_date,
        WorkerAttendance.date <= end_date
    ).all()

    days_worked = 0.0
    for att in attendance:
        if att.status == 'Worked':
            if calendar.weekday(att.date.year, att.date.month, att.date.day) == 5:
                days_worked += 0.5
            else:
                days_worked += 1.0

    return render_template(
        'worker/fiche_de_paie.html',
        worker=worker,
        year=year,
        month=month,
        month_name=calendar.month_name[month],
        advances=advances,
        total_advances=total_advances,
        net_salary=net_salary,
        net_in_words=net_in_words,
        days_worked=days_worked
    )

@worker_portal_bp.route('/jobs')
@login_required
def worker_jobs():
    return render_template('worker/jobs.html')