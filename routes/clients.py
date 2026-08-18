from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from extensions import db
from models import Client, Quote
from utils.helpers import log_notification

clients_bp = Blueprint('clients', __name__, url_prefix='/clients')

@clients_bp.route('/')
@login_required
def clients_list():
    if current_user.role == 'worker':
        return redirect(url_for('worker_portal.worker_dashboard'))
    all_clients = Client.query.order_by(Client.company_name.asc()).all()
    return render_template('clients/list.html', clients=all_clients)

@clients_bp.route('/view/<int:client_id>')
@login_required
def client_dashboard(client_id):
    client = Client.query.get_or_404(client_id)
    client_quotes = Quote.query.filter_by(client_id=client.id).order_by(Quote.date_created.desc()).all()
    approved_quotes = [q for q in client_quotes if q.status == 'Approved']
    total_billed = sum(q.total_amount for q in approved_quotes)
    total_paid = sum(q.amount_paid for q in client_quotes)
    balance_due = total_billed - total_paid
    return render_template('clients/dashboard.html', client=client, quotes=client_quotes, total_billed=total_billed, total_paid=total_paid, balance_due=balance_due)

@clients_bp.route('/create', methods=['GET', 'POST'])
@login_required
def client_create():
    if request.method == 'POST':
        new_client = Client(
            company_name=request.form.get('company_name'),
            contact_name=request.form.get('contact_name'),
            email=request.form.get('email'),
            phone=request.form.get('phone'),
            address=request.form.get('address'),
            tax_id=request.form.get('tax_id')
        )
        db.session.add(new_client)
        db.session.commit()
        log_notification('Client Registered', f'Created profile for: {new_client.company_name}', 'Client', 'users', 'text-blue-400')
        flash(f'Client {new_client.company_name} added!', 'success')
        return redirect(url_for('clients.clients_list'))
    return render_template('clients/create.html')

@clients_bp.route('/edit/<int:client_id>', methods=['GET', 'POST'])
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
        flash(f'Client {client.company_name} updated!', 'success')
        return redirect(url_for('clients.clients_list'))
    return render_template('clients/edit.html', client=client)

@clients_bp.route('/delete/<int:client_id>', methods=['POST'])
@login_required
def client_delete(client_id):
    client = Client.query.get_or_404(client_id)
    db.session.delete(client)
    db.session.commit()
    flash('Client deleted.', 'info')
    return redirect(url_for('clients.clients_list'))