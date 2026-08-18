from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required

from extensions import db
from models import StockItem
from utils.helpers import parse_float

stock_bp = Blueprint('stock', __name__, url_prefix='/stock')

@stock_bp.route('/')
@login_required
def stock_list():
    all_stock = StockItem.query.order_by(StockItem.name.asc()).all()
    return render_template('stock/list.html', stock=all_stock)

@stock_bp.route('/create', methods=['GET', 'POST'])
@login_required
def stock_create():
    if request.method == 'POST':
        new_item = StockItem(
            name=request.form.get('name'),
            quantity=parse_float(request.form.get('quantity')),
            min_stock_alert=parse_float(request.form.get('min_stock_alert'), default=5.0)
        )
        db.session.add(new_item)
        db.session.commit()
        flash(f'Stock item "{new_item.name}" added!', 'success')
        return redirect(url_for('stock.stock_list'))
    return render_template('stock/create.html')

@stock_bp.route('/update-qty/<int:item_id>', methods=['POST'])
@login_required
def stock_update_qty(item_id):
    item = StockItem.query.get_or_404(item_id)
    item.quantity = parse_float(request.form.get('quantity'))
    db.session.commit()
    flash(f'Stock for "{item.name}" updated.', 'success')
    return redirect(url_for('stock.stock_list'))

@stock_bp.route('/delete/<int:item_id>', methods=['POST'])
@login_required
def stock_delete(item_id):
    item = StockItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash('Stock item removed.', 'info')
    return redirect(url_for('stock.stock_list'))