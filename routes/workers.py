# routes/workers.py
import calendar
from datetime import datetime, date
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import extract

from extensions import db
from models import Worker, User, SalaryAdvance, WorkerBonus, Expense, WorkerAttendance
from utils.helpers import parse_float, parse_int, log_notification

workers_bp = Blueprint('workers', __name__, url_prefix='/workers')


def check_and_process_auto_payrolls():
    """Automates salary expense entry when current date hits or passes a worker's set payday."""
    today = date.today()
    current_month_str = today.strftime('%Y-%m')

    workers = Worker.query.filter(Worker.monthly_rate > 0).all()
    for worker in workers:
        if today.day >= worker.salary_pay_day and worker.last_payroll_processed != current_month_str:
            advances = SalaryAdvance.query.filter(
                SalaryAdvance.worker_id == worker.id,
                extract('month', SalaryAdvance.date_given) == today.month,
                extract('year', SalaryAdvance.date_given) == today.year
            ).all()
            bonuses = WorkerBonus.query.filter(
                WorkerBonus.worker_id == worker.id,
                extract('month', WorkerBonus.date_given) == today.month,
                extract('year', WorkerBonus.date_given) == today.year
            ).all()

            total_advances = sum(a.amount for a in advances)
            total_bonuses = sum(b.amount for b in bonuses)
            net_salary = max(0.0, (worker.monthly_rate + total_bonuses) - total_advances)

            salary_expense = Expense(
                category="Salaries",
                description=f"Monthly Salary - {worker.full_name} ({today.strftime('%B %Y')})",
                amount=net_salary,
                date_logged=datetime.now()
            )
            db.session.add(salary_expense)
            worker.last_payroll_processed = current_month_str
            log_notification('Auto Payroll Executed', f'Salary expense of {net_salary:,.3f} TND logged for {worker.full_name}.', 'Financials', 'dollar-sign', 'text-emerald-400')
    
    db.session.commit()


@workers_bp.route('/')
@login_required
def workers_list():
    if current_user.role != 'admin' and not current_user.can_manage_workers:
        flash('Access denied to Workers section.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    check_and_process_auto_payrolls()

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

        current_bonuses = WorkerBonus.query.filter(
            WorkerBonus.worker_id == w.id,
            extract('month', WorkerBonus.date_given) == current_month,
            extract('year', WorkerBonus.date_given) == current_year
        ).all()
        
        total_advances = sum(a.amount for a in current_advances)
        total_bonuses = sum(b.amount for b in current_bonuses)
        net_salary = max(0.0, (w.monthly_rate + total_bonuses) - total_advances)

        worker_data.append({
            'worker': w,
            'advances': current_advances,
            'bonuses': current_bonuses,
            'total_advances': total_advances,
            'total_bonuses': total_bonuses,
            'net_salary': net_salary
        })

    total_payroll = sum(w.monthly_rate for w in workers)
    return render_template('workers/list.html', workers=workers, worker_data=worker_data, total_payroll=total_payroll)


@workers_bp.route('/<int:worker_id>')
@login_required
def worker_detail(worker_id):
    """Dedicated Worker Profile Hub showing salary controls, active advances/primes, and lifetime history."""
    if current_user.role != 'admin' and not current_user.can_manage_workers:
        flash('Access denied to Workers section.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    worker = Worker.query.get_or_404(worker_id)
    today = date.today()
    current_month = today.month
    current_year = today.year

    # Current Month Advances and Bonuses
    advances = SalaryAdvance.query.filter(
        SalaryAdvance.worker_id == worker.id,
        extract('month', SalaryAdvance.date_given) == current_month,
        extract('year', SalaryAdvance.date_given) == current_year
    ).order_by(SalaryAdvance.date_given.desc()).all()

    bonuses = WorkerBonus.query.filter(
        WorkerBonus.worker_id == worker.id,
        extract('month', WorkerBonus.date_given) == current_month,
        extract('year', WorkerBonus.date_given) == current_year
    ).order_by(WorkerBonus.date_given.desc()).all()

    total_advances = sum(a.amount for a in advances)
    total_bonuses = sum(b.amount for b in bonuses)
    net_salary = max(0.0, (worker.monthly_rate + total_bonuses) - total_advances)

    # Full Lifetime History Generator
    hire_date = worker.hire_date or date(current_year, 1, 1)
    history_records = []
    
    start_year, start_month = hire_date.year, hire_date.month
    y, m = current_year, current_month

    while (y > start_year) or (y == start_year and m >= start_month):
        m_advances = SalaryAdvance.query.filter(
            SalaryAdvance.worker_id == worker.id,
            extract('month', SalaryAdvance.date_given) == m,
            extract('year', SalaryAdvance.date_given) == y
        ).all()

        m_bonuses = WorkerBonus.query.filter(
            WorkerBonus.worker_id == worker.id,
            extract('month', WorkerBonus.date_given) == m,
            extract('year', WorkerBonus.date_given) == y
        ).all()

        start_date = date(y, m, 1)
        _, days_in_month = calendar.monthrange(y, m)
        end_date = date(y, m, days_in_month)

        attendance = WorkerAttendance.query.filter(
            WorkerAttendance.worker_id == worker.id,
            WorkerAttendance.date >= start_date,
            WorkerAttendance.date <= end_date
        ).all()

        days_worked = sum(0.5 if att.status == 'Worked' and calendar.weekday(att.date.year, att.date.month, att.date.day) == 5 else 1.0 for att in attendance if att.status == 'Worked')

        tot_adv = sum(a.amount for a in m_advances)
        tot_bon = sum(b.amount for b in m_bonuses)
        net_pay = max(0.0, (worker.monthly_rate + tot_bon) - tot_adv)

        if days_worked > 0 or len(m_advances) > 0 or len(m_bonuses) > 0 or (y == current_year and m == current_month):
            history_records.append({
                'year': y,
                'month': m,
                'month_name': calendar.month_name[m],
                'base_rate': worker.monthly_rate,
                'days_worked': days_worked,
                'advances_count': len(m_advances),
                'bonuses_count': len(m_bonuses),
                'total_advances': tot_adv,
                'total_bonuses': tot_bon,
                'net_pay': net_pay
            })

        m -= 1
        if m == 0:
            m = 12
            y -= 1

    return render_template(
        'workers/detail.html',
        worker=worker,
        advances=advances,
        bonuses=bonuses,
        total_advances=total_advances,
        total_bonuses=total_bonuses,
        net_salary=net_salary,
        history_records=history_records,
        current_year=current_year,
        current_month=current_month
    )


@workers_bp.route('/<int:worker_id>/edit-salary', methods=['POST'])
@login_required
def worker_edit_salary(worker_id):
    if current_user.role != 'admin' and not current_user.can_manage_workers:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    worker = Worker.query.get_or_404(worker_id)
    adjustment_type = request.form.get('adjustment_type', 'set')
    amount_change = parse_float(request.form.get('amount_change'))

    old_rate = worker.monthly_rate
    if adjustment_type == 'increase':
        worker.monthly_rate += amount_change
    elif adjustment_type == 'decrease':
        worker.monthly_rate = max(0.0, worker.monthly_rate - amount_change)
    else:
        worker.monthly_rate = amount_change

    db.session.commit()
    log_notification('Salary Adjustment', f'Salary for {worker.full_name} updated from {old_rate:,.3f} to {worker.monthly_rate:,.3f} TND', 'Worker', 'dollar-sign', 'text-emerald-400')
    flash(f'Base salary updated to {worker.monthly_rate:,.3f} TND', 'success')
    return redirect(url_for('workers.worker_detail', worker_id=worker.id))


@workers_bp.route('/bonus/add/<int:worker_id>', methods=['POST'])
@login_required
def add_worker_bonus(worker_id):
    if current_user.role != 'admin' and not current_user.can_manage_workers:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    worker = Worker.query.get_or_404(worker_id)
    amount = parse_float(request.form.get('amount'))
    title = request.form.get('title', 'Performance Prime')
    notes = request.form.get('notes', '')

    if amount > 0:
        bonus = WorkerBonus(
            worker_id=worker.id,
            amount=amount,
            title=title,
            date_given=datetime.now(),
            notes=notes
        )
        db.session.add(bonus)
        db.session.commit()

        log_notification('Prime Added', f'Added prime of {amount:,.3f} TND ({title}) for {worker.full_name}', 'Worker', 'award', 'text-amber-400')
        flash(f'Prime of {amount:,.3f} TND recorded for {worker.full_name}.', 'success')

    return redirect(url_for('workers.worker_detail', worker_id=worker.id))


@workers_bp.route('/bonus/edit/<int:bonus_id>', methods=['POST'])
@login_required
def edit_worker_bonus(bonus_id):
    if current_user.role != 'admin' and not current_user.can_manage_workers:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    bonus = WorkerBonus.query.get_or_404(bonus_id)
    bonus.amount = parse_float(request.form.get('amount'))
    bonus.title = request.form.get('title')
    bonus.notes = request.form.get('notes')
    db.session.commit()

    flash('Prime entry updated successfully.', 'success')
    return redirect(url_for('workers.worker_detail', worker_id=bonus.worker_id))


@workers_bp.route('/bonus/delete/<int:bonus_id>', methods=['POST'])
@login_required
def delete_worker_bonus(bonus_id):
    if current_user.role != 'admin' and not current_user.can_manage_workers:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    bonus = WorkerBonus.query.get_or_404(bonus_id)
    worker_id = bonus.worker_id
    db.session.delete(bonus)
    db.session.commit()

    flash('Prime entry removed.', 'info')
    return redirect(url_for('workers.worker_detail', worker_id=worker_id))


@workers_bp.route('/create', methods=['POST'])
@login_required
def worker_create():
    if current_user.role != 'admin' and not current_user.can_manage_workers:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    full_name = request.form.get('full_name')
    role = request.form.get('role')
    phone = request.form.get('phone')
    cin_number = request.form.get('cin_number')
    monthly_rate = parse_float(request.form.get('monthly_rate'))
    salary_pay_day = parse_int(request.form.get('salary_pay_day'), default=28)

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
                    can_manage_clients=bool(request.form.get('can_manage_clients')),
                    can_manage_quotes=bool(request.form.get('can_manage_quotes')),
                    can_manage_stock=bool(request.form.get('can_manage_stock')),
                    can_manage_machines=bool(request.form.get('can_manage_machines')),
                    can_manage_expenses=bool(request.form.get('can_manage_expenses')),
                    can_access_settings=bool(request.form.get('can_access_settings'))
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
        salary_pay_day=salary_pay_day,
        hire_date=date.today()
    )
    db.session.add(new_worker)
    db.session.commit()

    log_notification('Worker Registered', f'Added worker {full_name} ({role})', 'Worker', 'user-check', 'text-green-400')
    flash(f'Worker "{full_name}" registered successfully!', 'success')
    return redirect(url_for('workers.worker_detail', worker_id=new_worker.id))


@workers_bp.route('/<int:worker_id>/edit', methods=['POST'])
@login_required
def worker_update(worker_id):
    if current_user.role != 'admin' and not current_user.can_manage_workers:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    worker = Worker.query.get_or_404(worker_id)
    worker.full_name = request.form.get('full_name')
    worker.role = request.form.get('role')
    worker.phone = request.form.get('phone')
    worker.cin_number = request.form.get('cin_number')
    worker.monthly_rate = parse_float(request.form.get('monthly_rate'))
    worker.salary_pay_day = parse_int(request.form.get('salary_pay_day'), default=28)

    username = request.form.get('username')
    password = request.form.get('password')

    if username:
        if not worker.user:
            existing_user = User.query.filter_by(username=username).first()
            if existing_user:
                flash(f'Username "{username}" is already taken.', 'error')
                return redirect(url_for('workers.worker_detail', worker_id=worker.id))

            user = User(
                username=username,
                email=f"{username}@mecatechatia.tn",
                full_name=worker.full_name,
                role='worker'
            )
            user.set_password(password if password else '123456')
            db.session.add(user)
            db.session.flush()
            worker.user_id = user.id
            worker.user = user
        else:
            worker.user.username = username
            if password:
                worker.user.set_password(password)

    if worker.user:
        worker.user.can_manage_clients = bool(request.form.get('can_manage_clients'))
        worker.user.can_manage_quotes = bool(request.form.get('can_manage_quotes'))
        worker.user.can_manage_stock = bool(request.form.get('can_manage_stock'))
        worker.user.can_manage_machines = bool(request.form.get('can_manage_machines'))
        worker.user.can_manage_expenses = bool(request.form.get('can_manage_expenses'))
        worker.user.can_access_settings = bool(request.form.get('can_access_settings'))

    db.session.commit()
    flash(f'Profile and section permissions for "{worker.full_name}" updated!', 'success')
    return redirect(url_for('workers.worker_detail', worker_id=worker.id))


@workers_bp.route('/advance/add/<int:worker_id>', methods=['POST'])
@login_required
def add_worker_advance(worker_id):
    if current_user.role != 'admin' and not current_user.can_manage_workers:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

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

    return redirect(url_for('workers.worker_detail', worker_id=worker.id))


@workers_bp.route('/advance/delete/<int:advance_id>', methods=['POST'])
@login_required
def delete_worker_advance(advance_id):
    if current_user.role != 'admin' and not current_user.can_manage_workers:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    advance = SalaryAdvance.query.get_or_404(advance_id)
    worker_id = advance.worker_id
    db.session.delete(advance)
    db.session.commit()
    flash('Salary advance entry deleted.', 'info')
    return redirect(url_for('workers.worker_detail', worker_id=worker_id))


@workers_bp.route('/calendar/<int:worker_id>')
@login_required
def worker_calendar(worker_id):
    if current_user.role != 'admin' and not current_user.can_manage_workers:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

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
    if current_user.role != 'admin' and not current_user.can_manage_workers:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

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
    if current_user.role != 'admin' and not current_user.can_manage_workers:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    worker = Worker.query.get_or_404(worker_id)
    db.session.delete(worker)
    db.session.commit()
    flash('Worker removed from roster.', 'info')
    return redirect(url_for('workers.workers_list'))