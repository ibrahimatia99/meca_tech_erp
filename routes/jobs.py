# routes/jobs.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from datetime import datetime
from extensions import db
from models import Job, Worker, Client

jobs_bp = Blueprint('jobs', __name__, url_prefix='/jobs')

@jobs_bp.route('/')
@login_required
def jobs_list():
    """Admin view to manage all shop floor tasks."""
    if current_user.role == 'worker':
        return redirect(url_for('jobs.worker_jobs'))

    jobs = Job.query.order_by(Job.date_created.desc()).all()
    workers = Worker.query.all()
    clients = Client.query.all()
    
    return render_template('jobs/list.html', jobs=jobs, workers=workers, clients=clients)

@jobs_bp.route('/create', methods=['POST'])
@login_required
def job_create():
    """Create a new job task assigned to a worker."""
    title = request.form.get('title')
    description = request.form.get('description')
    cutting_list = request.form.get('cutting_list')
    priority = request.form.get('priority', 'Medium')
    worker_id = request.form.get('worker_id')
    client_id = request.form.get('client_id')
    due_date_str = request.form.get('due_date')

    due_date = datetime.strptime(due_date_str, '%Y-%m-%d') if due_date_str else None

    new_job = Job(
        title=title,
        description=description,
        cutting_list=cutting_list,
        priority=priority,
        worker_id=int(worker_id) if worker_id else None,
        client_id=int(client_id) if client_id else None,
        due_date=due_date
    )
    
    db.session.add(new_job)
    db.session.commit()
    flash('Job assigned to workshop roster successfully!', 'success')
    return redirect(url_for('jobs.jobs_list'))

@jobs_bp.route('/<int:job_id>/status', methods=['POST'])
@login_required
def update_job_status(job_id):
    """Update job status (used by both Admin and Workers)."""
    job = Job.query.get_or_404(job_id)
    new_status = request.form.get('status')
    
    if new_status in ['Pending', 'In Progress', 'Completed', 'On Hold']:
        job.status = new_status
        if new_status == 'Completed':
            job.completed_at = datetime.utcnow()
        db.session.commit()
        flash(f'Job #{job.id} status updated to {new_status}.', 'success')

    if current_user.role == 'worker':
        return redirect(url_for('jobs.worker_jobs'))
    return redirect(url_for('jobs.jobs_list'))

@jobs_bp.route('/<int:job_id>/delete', methods=['POST'])
@login_required
def job_delete(job_id):
    """Delete a job assignment."""
    job = Job.query.get_or_404(job_id)
    db.session.delete(job)
    db.session.commit()
    flash('Job removed from schedule.', 'success')
    return redirect(url_for('jobs.jobs_list'))

@jobs_bp.route('/my-tasks')
@login_required
def worker_jobs():
    """Worker-facing view: showing tasks assigned specifically to the logged-in worker."""
    # Lookup worker profile linked to current_user
    worker = Worker.query.filter_by(user_id=current_user.id).first()
    
    if worker:
        assigned_jobs = Job.query.filter_by(worker_id=worker.id).order_by(Job.date_created.desc()).all()
    else:
        assigned_jobs = []

    return render_template('worker/jobs.html', jobs=assigned_jobs, worker=worker)