from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from extensions import db
from models import Machine, MaintenanceLog, Expense
from utils.helpers import parse_float

machines_bp = Blueprint('machines', __name__, url_prefix='/machines')

@machines_bp.route('/')
@login_required
def machines_list():
    if current_user.role != 'admin' and not current_user.can_manage_machines:
        flash('Access denied to Machinery module.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    machines = Machine.query.order_by(Machine.name.asc()).all()
    return render_template('machines/list.html', machines=machines)

@machines_bp.route('/create', methods=['GET', 'POST'])
@login_required
def machine_create():
    if current_user.role != 'admin' and not current_user.can_manage_machines:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

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
        return redirect(url_for('machines.machines_list'))
    return render_template('machines/create.html')

@machines_bp.route('/edit/<int:machine_id>', methods=['GET', 'POST'])
@login_required
def machine_edit(machine_id):
    if current_user.role != 'admin' and not current_user.can_manage_machines:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    machine = Machine.query.get_or_404(machine_id)
    if request.method == 'POST':
        machine.name = request.form.get('name')
        machine.model_type = request.form.get('model_type')
        machine.serial_number = request.form.get('serial_number')
        machine.notes = request.form.get('notes')
        db.session.commit()
        flash(f'Machine "{machine.name}" updated!', 'success')
        return redirect(url_for('machines.machine_detail', machine_id=machine.id))
    return render_template('machines/edit.html', machine=machine)

@machines_bp.route('/view/<int:machine_id>')
@login_required
def machine_detail(machine_id):
    if current_user.role != 'admin' and not current_user.can_manage_machines:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    machine = Machine.query.get_or_404(machine_id)
    history_logs = MaintenanceLog.query.filter_by(machine_id=machine.id).order_by(MaintenanceLog.date_logged.desc()).all()
    total_cost = sum(log.cost for log in history_logs)
    return render_template('machines/detail.html', machine=machine, logs=history_logs, total_cost=total_cost)

@machines_bp.route('/log-service/<int:machine_id>', methods=['POST'])
@login_required
def machine_log_service(machine_id):
    if current_user.role != 'admin' and not current_user.can_manage_machines:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

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
    return redirect(url_for('machines.machine_detail', machine_id=machine.id))