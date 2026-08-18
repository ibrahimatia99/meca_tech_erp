import calendar
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import extract

from extensions import db
from models import Worker, User, SalaryAdvance, Expense, WorkerAttendance
from utils.helpers import parse_float, parse_int, log_notification

workers_bp = Blueprint('workers', __name__, url_prefix='/workers')

@workers_bp.route('/')
@login_required
def workers_list():
    if current_user.role == 'worker':
        return redirect(url_for('worker_portal.worker_dashboard'))

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

@workers_bp.route('/create', methods=['GET', 'POST'])
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
        return redirect(url_for('workers.workers_list'))

    return render_template('workers/create.html')

@workers_bp.route('/edit/<int:worker_id>', methods=['GET', 'POST'])
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
        return redirect(url_for('workers.workers_list'))
    return render_template('workers/edit.html', worker=worker)

@workers_bp.route('/raise/<int:worker_id>', methods=['POST'])
@login_required
def worker_salary_raise(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    raise_amount = parse_float(request.form.get('raise_amount'))
    raise_type = request.form.get('raise_type', 'amount')
    
    if raise_amount > 0:
        if raise_type == 'percentage':
            increase = worker.monthly_rate * (raise_amount / 100.0)
            worker.monthly_rate += increase
        else:
            worker.monthly_rate += raise_amount
            
        db.session.commit()
        log_notification('Salary Augmentation', f'Updated base rate for {worker.full_name}. New rate: {worker.monthly_rate:,.3f} TND', 'Worker', 'trending-up', 'text-emerald-400')
        flash(f'Salary updated for {worker.full_name}!', 'success')
        
    return redirect(url_for('workers.workers_list'))

@workers_bp.route('/raise/edit/<int:worker_id>', methods=['POST'])
@login_required
def edit_worker_salary(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    new_rate = parse_float(request.form.get('new_rate'))

    if new_rate > 0:
        worker.monthly_rate = new_rate
        db.session.commit()
        flash(f"Base salary for {worker.full_name} updated successfully!", 'success')
        
    return redirect(url_for('workers.workers_list'))

@workers_bp.route('/bonus/<int:worker_id>', methods=['POST'])
@login_required
def worker_add_bonus(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    bonus_amount = parse_float(request.form.get('bonus_amount'))
    notes = request.form.get('notes', 'Prime Exceptionnelle')

    if bonus_amount > 0:
        advance = SalaryAdvance(
            worker_id=worker.id,
            amount=-bonus_amount,
            date_given=datetime.now(),
            notes=f"PRIME: {notes}"
        )
        db.session.add(advance)
        
        db.session.add(Expense(
            category='Worker Prime',
            description=f"Prime for {worker.full_name}: {notes}",
            amount=bonus_amount,
            date_logged=datetime.now()
        ))
        db.session.commit()
        
        flash(f'Prime of {bonus_amount:,.3f} TND granted to {worker.full_name}!', 'success')
        
    return redirect(url_for('workers.workers_list'))

@workers_bp.route('/advance/add/<int:worker_id>', methods=['POST'])
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

    return redirect(url_for('workers.workers_list'))

@workers_bp.route('/advance/edit/<int:advance_id>', methods=['POST'])
@login_required
def edit_worker_advance(advance_id):
    advance = SalaryAdvance.query.get_or_404(advance_id)
    new_amount = parse_float(request.form.get('amount'))
    new_notes = request.form.get('notes', '')

    if new_amount != 0:
        advance.amount = new_amount
        advance.notes = new_notes
        db.session.commit()
        flash('Entry updated successfully!', 'success')
    
    return redirect(url_for('workers.workers_list'))

@workers_bp.route('/advance/delete/<int:advance_id>', methods=['POST'])
@login_required
def delete_worker_advance(advance_id):
    advance = SalaryAdvance.query.get_or_404(advance_id)
    db.session.delete(advance)
    db.session.commit()
    flash('Salary advance entry deleted.', 'info')
    return redirect(url_for('workers.workers_list'))

@workers_bp.route('/calendar/<int:worker_id>')
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

@workers_bp.route('/set-attendance/<int:worker_id>', methods=['POST'])
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
    return redirect(url_for('workers.worker_calendar', worker_id=worker.id, year=year, month=month))

@workers_bp.route('/delete/<int:worker_id>', methods=['POST'])
@login_required
def worker_delete(worker_id):
    worker = Worker.query.get_or_404(worker_id)
    db.session.delete(worker)
    db.session.commit()
    flash('Worker removed from roster.', 'info')
    return redirect(url_for('workers.workers_list'))