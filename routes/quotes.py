import re
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import extract

from extensions import db
from models import Quote, Client, QuoteItem, PaymentHistory
from utils.helpers import parse_float, parse_int, format_amount_in_words, generate_document_ref, clean_doc_number
from utils.settings import get_setting

quotes_bp = Blueprint('quotes', __name__, url_prefix='/quotes')

@quotes_bp.route('/')
@login_required
def quotes_list():
    if current_user.role != 'admin' and not current_user.can_manage_quotes:
        flash('Access denied to Commercial Documents.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    selected_year = request.args.get('year', type=int)
    selected_month = request.args.get('month', type=int)
    
    query = Quote.query
    if selected_year:
        query = query.filter(extract('year', Quote.date_created) == selected_year)
    if selected_month:
        query = query.filter(extract('month', Quote.date_created) == selected_month)
        
    filtered_quotes = query.order_by(Quote.date_created.desc()).all()
    period_total = sum(q.total_amount for q in filtered_quotes if q.status == 'Approved')
    period_paid = sum(q.amount_paid for q in filtered_quotes)
    
    years_db = db.session.query(extract('year', Quote.date_created)).distinct().all()
    available_years = sorted([int(y[0]) for y in years_db if y[0] is not None], reverse=True)
    if not available_years:
        available_years = [datetime.now().year]
        
    return render_template(
        'quotes/list.html', 
        quotes=filtered_quotes,
        selected_year=selected_year,
        selected_month=selected_month,
        available_years=available_years,
        period_total=period_total,
        period_paid=period_paid
    )

@quotes_bp.route('/create', methods=['GET', 'POST'])
@login_required
def quote_create():
    if current_user.role != 'admin' and not current_user.can_manage_quotes:
        flash('Access denied to Commercial Documents.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    clients = Client.query.all()
    
    if request.method == 'POST':
        doc_type = request.form.get('doc_type', 'devis')
        auto_ref = generate_document_ref(doc_type)
        
        quote_num = request.form.get('quote_number').strip() if request.form.get('quote_number') else auto_ref
        
        if doc_type == 'facture' and not quote_num.startswith('FAC-'):
            quote_num = f"FAC-{quote_num}" if not quote_num.startswith('FAC') else quote_num.replace('FAC', 'FAC-', 1)
        elif doc_type == 'bl' and not quote_num.startswith('BL-'):
            quote_num = f"BL-{quote_num}" if not quote_num.startswith('BL') else quote_num.replace('BL', 'BL-', 1)
        elif doc_type == 'devis' and not quote_num.startswith('DEV-'):
            quote_num = f"DEV-{quote_num}" if not quote_num.startswith('DEV') else quote_num.replace('DEV', 'DEV-', 1)
            
        client_id = parse_int(request.form.get('client_id'))
        apply_tva = True if request.form.get('apply_tva') == 'on' else False
        
        remarque = request.form.get('remarque', '')
        payment_terms = request.form.get('payment_terms', 'Paiement à la livraison / Chèque')
        validite_offre = request.form.get('validite_offre', '30 Jours')
        delai_livraison = request.form.get('delai_livraison', 'Selon disponibilité du stock / Planning atelier')
        mode_expedition = request.form.get('mode_expedition', 'Par nos soins / Transport client')
        
        notes = request.form.get('notes', '')
        discount_rate = parse_float(request.form.get('discount_rate'))
        
        driver_name = request.form.get('driver_name', '')
        driver_cin = request.form.get('driver_cin', '')
        vehicle_plate = request.form.get('vehicle_plate', '')
        
        descriptions = request.form.getlist('item_description[]')
        quantities = request.form.getlist('item_quantity[]')
        unit_rates = request.form.getlist('item_rate[]')
        
        subtotal = 0.0
        items_to_add = []
        for idx, desc in enumerate(descriptions):
            if desc.strip():
                qty = parse_float(quantities[idx] if idx < len(quantities) else 1.0, default=1.0)
                rate = parse_float(unit_rates[idx] if idx < len(unit_rates) else 0.0)
                total = qty * rate
                subtotal += total
                items_to_add.append(QuoteItem(
                    item_order=idx + 1,
                    description=desc,
                    quantity=qty,
                    unit_rate=rate,
                    total_price=total
                ))
                
        discount_amt = subtotal * (discount_rate / 100.0)
        after_discount = subtotal - discount_amt
        
        if apply_tva:
            tax_amt = after_discount * 0.19
            stamp_tax = 1.000
        else:
            tax_amt = 0.0
            stamp_tax = 0.0
            
        total_amt = after_discount + tax_amt + stamp_tax
        words_text = f"Arrêté le présent document à la somme de : {format_amount_in_words(total_amt)}."
        
        new_quote = Quote(
            quote_number=quote_num,
            client_id=client_id,
            subtotal=subtotal,
            discount_rate=discount_rate,
            discount_amount=discount_amt,
            tax_rate=19.0 if apply_tva else 0.0,
            tax_amount=tax_amt,
            stamp_tax=stamp_tax,
            total_amount=total_amt,
            total_in_words=words_text,
            remarque=remarque,
            payment_terms=payment_terms,
            validite_offre=validite_offre,
            delai_livraison=delai_livraison,
            mode_expedition=mode_expedition,
            notes=notes,
            driver_name=driver_name,
            driver_cin=driver_cin,
            vehicle_plate=vehicle_plate,
            status='Draft',
            amount_paid=0.0,
            payment_status='Unpaid'
        )
        new_quote.items.extend(items_to_add)
        db.session.add(new_quote)
        db.session.commit()
        
        flash(f'Document {quote_num} created successfully!', 'success')
        return redirect(url_for('quotes.quotes_list'))
        
    return render_template('quotes/create.html', clients=clients)

@quotes_bp.route('/edit/<int:quote_id>', methods=['GET', 'POST'])
@login_required
def quote_edit(quote_id):
    if current_user.role != 'admin' and not current_user.can_manage_quotes:
        flash('Access denied to Commercial Documents.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    quote = Quote.query.get_or_404(quote_id)
    clients = Client.query.all()
    
    if request.method == 'POST':
        quote.client_id = parse_int(request.form.get('client_id'))
        quote.quote_number = request.form.get('quote_number') or quote.quote_number
        apply_tva = True if request.form.get('apply_tva') == 'on' else False
        
        quote.remarque = request.form.get('remarque', '')
        quote.payment_terms = request.form.get('payment_terms', '')
        quote.validite_offre = request.form.get('validite_offre', '')
        quote.delai_livraison = request.form.get('delai_livraison', '')
        quote.mode_expedition = request.form.get('mode_expedition', '')
        quote.notes = request.form.get('notes', '')
        quote.discount_rate = parse_float(request.form.get('discount_rate'))
        
        quote.driver_name = request.form.get('driver_name', '')
        quote.driver_cin = request.form.get('driver_cin', '')
        quote.vehicle_plate = request.form.get('vehicle_plate', '')
        
        QuoteItem.query.filter_by(quote_id=quote.id).delete()
        
        descriptions = request.form.getlist('item_description[]')
        quantities = request.form.getlist('item_quantity[]')
        unit_rates = request.form.getlist('item_rate[]')
        
        subtotal = 0.0
        items_to_add = []
        for idx, desc in enumerate(descriptions):
            if desc.strip():
                qty = parse_float(quantities[idx] if idx < len(quantities) else 1.0, default=1.0)
                rate = parse_float(unit_rates[idx] if idx < len(unit_rates) else 0.0)
                total = qty * rate
                subtotal += total
                items_to_add.append(QuoteItem(
                    quote_id=quote.id,
                    item_order=idx + 1,
                    description=desc,
                    quantity=qty,
                    unit_rate=rate,
                    total_price=total
                ))
                
        discount_amt = subtotal * (quote.discount_rate / 100.0)
        after_discount = subtotal - discount_amt
        
        if apply_tva:
            tax_amt = after_discount * 0.19
            stamp_tax = 1.000
            quote.tax_rate = 19.0
        else:
            tax_amt = 0.0
            stamp_tax = 0.0
            quote.tax_rate = 0.0
            
        total_amt = after_discount + tax_amt + stamp_tax
        
        quote.subtotal = subtotal
        quote.discount_amount = discount_amt
        quote.tax_amount = tax_amt
        quote.stamp_tax = stamp_tax
        quote.total_amount = total_amt
        quote.total_in_words = f"Arrêté le présent document à la somme de : {format_amount_in_words(total_amt)}."
        
        quote.items = items_to_add
        db.session.commit()
        
        flash(f'Document {quote.quote_number} updated successfully!', 'success')
        return redirect(url_for('quotes.quotes_list'))
        
    return render_template('quotes/edit.html', quote=quote, clients=clients)

@quotes_bp.route('/update-status/<int:quote_id>', methods=['POST'])
@login_required
def update_quote_status(quote_id):
    if current_user.role != 'admin' and not current_user.can_manage_quotes:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    quote = Quote.query.get_or_404(quote_id)
    new_status = request.form.get('status')
    if new_status:
        old_status = quote.status
        quote.status = new_status
        
        if new_status == 'Approved' and old_status != 'Approved':
            if quote.quote_number.startswith('DEV-'):
                quote.quote_number = quote.quote_number.replace('DEV-', 'FAC-', 1)
            elif not quote.quote_number.startswith(('FAC-', 'BL-')):
                now = datetime.now()
                month_str = now.strftime('%m')
                match = re.search(r'(\d+)$', quote.quote_number)
                seq = match.group(1) if match else '150'
                quote.quote_number = f"FAC-MTA-{month_str}-{seq}"
            
        db.session.commit()
        flash(f'Status for #{quote.quote_number} updated to {new_status}.', 'success')
    return redirect(request.referrer or url_for('quotes.quotes_list'))

@quotes_bp.route('/add-payment/<int:quote_id>', methods=['POST'])
@login_required
def add_quote_payment(quote_id):
    if current_user.role != 'admin' and not current_user.can_manage_quotes:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    quote = Quote.query.get_or_404(quote_id)
    added_amount = parse_float(request.form.get('add_amount'))

    if added_amount > 0:
        db.session.add(PaymentHistory(
            quote_id=quote.id,
            amount=added_amount,
            payment_date=datetime.now(),
            payment_method=request.form.get('payment_method', 'Espèces / Chèque'),
            notes=request.form.get('notes', '')
        ))
        db.session.flush()
        quote.recalculate_payment_status()
        db.session.commit()
        flash(f'Payment of {added_amount:,.3f} TND recorded for #{quote.quote_number}.', 'success')

    return redirect(request.referrer or url_for('quotes.quotes_list'))

@quotes_bp.route('/edit-payment/<int:payment_id>', methods=['POST'])
@login_required
def edit_quote_payment(payment_id):
    if current_user.role != 'admin' and not current_user.can_manage_quotes:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    payment = PaymentHistory.query.get_or_404(payment_id)
    quote = payment.quote
    
    new_amount = parse_float(request.form.get('amount'))
    if new_amount > 0:
        payment.amount = new_amount
        payment.payment_method = request.form.get('payment_method', payment.payment_method)
        payment.notes = request.form.get('notes', payment.notes)
        
        db.session.flush()
        quote.recalculate_payment_status()
        db.session.commit()
        
        flash('Payment entry updated successfully!', 'success')
    
    return redirect(request.referrer or url_for('quotes.quotes_list'))

@quotes_bp.route('/delete-payment/<int:payment_id>', methods=['POST'])
@login_required
def delete_quote_payment(payment_id):
    if current_user.role != 'admin' and not current_user.can_manage_quotes:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    payment = PaymentHistory.query.get_or_404(payment_id)
    quote = payment.quote
    
    db.session.delete(payment)
    db.session.flush()
    
    quote.recalculate_payment_status()
    db.session.commit()
    
    flash('Payment entry removed.', 'info')
    return redirect(request.referrer or url_for('quotes.quotes_list'))

@quotes_bp.route('/delete/<int:quote_id>', methods=['POST'])
@login_required
def quote_delete(quote_id):
    if current_user.role != 'admin' and not current_user.can_manage_quotes:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    quote = Quote.query.get_or_404(quote_id)
    db.session.delete(quote)
    db.session.commit()
    flash('Quote deleted.', 'info')
    return redirect(url_for('quotes.quotes_list'))

@quotes_bp.route('/print/<int:quote_id>')
@login_required
def quote_print(quote_id):
    if current_user.role != 'admin' and not current_user.can_manage_quotes:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    quote = Quote.query.get_or_404(quote_id)
    display_num = clean_doc_number(quote.quote_number, 'devis')
    return render_template('quotes/print.html', quote=quote, display_num=display_num, pdf_font_size=get_setting('pdf_font_size', '11'), pdf_margin=get_setting('pdf_margin', '5'))

@quotes_bp.route('/invoice/<int:quote_id>')
@login_required
def invoice_print(quote_id):
    if current_user.role != 'admin' and not current_user.can_manage_quotes:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    quote = Quote.query.get_or_404(quote_id)
    display_num = clean_doc_number(quote.quote_number, 'facture')
    return render_template('quotes/invoice.html', quote=quote, display_num=display_num, pdf_font_size=get_setting('pdf_font_size', '11'), pdf_margin=get_setting('pdf_margin', '5'))

@quotes_bp.route('/bon-livraison/<int:quote_id>')
@login_required
def bon_livraison_print(quote_id):
    if current_user.role != 'admin' and not current_user.can_manage_quotes:
        flash('Access denied.', 'error')
        return redirect(url_for('worker_portal.worker_dashboard'))

    quote = Quote.query.get_or_404(quote_id)
    display_num = clean_doc_number(quote.quote_number, 'bl')
    return render_template('quotes/bon_livraison.html', quote=quote, display_num=display_num, pdf_font_size=get_setting('pdf_font_size', '11'), pdf_margin=get_setting('pdf_margin', '5'))