from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ---------------------------------------------------------------------------
# 1. USER AUTHENTICATION
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='worker')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ---------------------------------------------------------------------------
# 2. CLIENTS & SUPPLIERS
# ---------------------------------------------------------------------------
class Client(db.Model):
    __tablename__ = 'clients'

    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False)
    contact_name = db.Column(db.String(100))
    email = db.Column(db.String(120))
    phone = db.Column(db.String(50))
    address = db.Column(db.Text)
    tax_id = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    quotes = db.relationship('Quote', backref='client', lazy=True)


class Supplier(db.Model):
    __tablename__ = 'suppliers'

    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False)
    contact_person = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    email = db.Column(db.String(120))
    address = db.Column(db.Text)
    material_types = db.Column(db.String(200))


# ---------------------------------------------------------------------------
# 3. QUOTES, INVOICES & PAYMENT HISTORY
# ---------------------------------------------------------------------------
class Quote(db.Model):
    __tablename__ = 'quotes'

    id = db.Column(db.Integer, primary_key=True)
    quote_number = db.Column(db.String(50), nullable=False)
    revision_code = db.Column(db.String(10), default='REV-A')
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    date_expiration = db.Column(db.DateTime)
    
    subtotal = db.Column(db.Float, default=0.0)
    discount_rate = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    tax_rate = db.Column(db.Float, default=19.0)
    tax_amount = db.Column(db.Float, default=0.0)
    stamp_tax = db.Column(db.Float, default=1.000)
    total_amount = db.Column(db.Float, default=0.0)
    total_in_words = db.Column(db.Text)
    
    status = db.Column(db.String(30), default='Draft') # Draft, Sent, Approved, Rejected
    amount_paid = db.Column(db.Float, default=0.0)
    payment_status = db.Column(db.String(30), default='Unpaid') # Unpaid, Partial, Paid
    
    remarque = db.Column(db.Text)
    payment_terms = db.Column(db.Text)
    validite_offre = db.Column(db.String(100), default='30 Jours')
    delai_livraison = db.Column(db.String(100), default='Selon disponibilité du stock / Planning atelier')
    mode_expedition = db.Column(db.String(100), default='Par nos soins / Transport client')

    driver_name = db.Column(db.String(100))
    driver_cin = db.Column(db.String(50))
    vehicle_plate = db.Column(db.String(50))

    notes = db.Column(db.Text)

    items = db.relationship('QuoteItem', backref='quote', cascade="all, delete-orphan", lazy=True)
    payments = db.relationship('PaymentHistory', backref='quote', cascade="all, delete-orphan", lazy=True)

    def recalculate_payment_status(self):
        self.amount_paid = sum(p.amount for p in self.payments)
        if self.amount_paid >= self.total_amount and self.total_amount > 0:
            self.amount_paid = self.total_amount
            self.payment_status = 'Paid'
        elif self.amount_paid > 0:
            self.payment_status = 'Partial'
        else:
            self.payment_status = 'Unpaid'


class QuoteItem(db.Model):
    __tablename__ = 'quote_items'

    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quotes.id'), nullable=False)
    item_order = db.Column(db.Integer, default=1)
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=1.0)
    unit_rate = db.Column(db.Float, nullable=False, default=0.0)
    total_price = db.Column(db.Float, nullable=False, default=0.0)


class PaymentHistory(db.Model):
    __tablename__ = 'payment_history'

    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quotes.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50), default='Espèces / Chèque')
    notes = db.Column(db.Text)


# ---------------------------------------------------------------------------
# 4. STOCK & MACHINERY
# ---------------------------------------------------------------------------
class StockItem(db.Model):
    __tablename__ = 'stock_items'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    quantity = db.Column(db.Float, default=0.0)
    min_stock_alert = db.Column(db.Float, default=5.0)


class Machine(db.Model):
    __tablename__ = 'machines'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    model_type = db.Column(db.String(100))
    serial_number = db.Column(db.String(100))
    status = db.Column(db.String(30), default='Operational')
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    logs = db.relationship('MaintenanceLog', backref='machine', cascade="all, delete-orphan", lazy=True)


class MaintenanceLog(db.Model):
    __tablename__ = 'maintenance_logs'
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'), nullable=False)
    status_logged = db.Column(db.String(30), nullable=False)
    service_description = db.Column(db.Text, nullable=False)
    cost = db.Column(db.Float, default=0.0)
    performed_by = db.Column(db.String(100))
    date_logged = db.Column(db.DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# 5. WORKERS & ATTENDANCE
# ---------------------------------------------------------------------------
class Worker(db.Model):
    __tablename__ = 'workers'
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(80), nullable=False)
    phone = db.Column(db.String(50))
    cin_number = db.Column(db.String(50))
    monthly_rate = db.Column(db.Float, default=0.0)
    hire_date = db.Column(db.Date, default=datetime.utcnow)
    
    attendance = db.relationship('WorkerAttendance', backref='worker', cascade="all, delete-orphan", lazy=True)


class WorkerAttendance(db.Model):
    __tablename__ = 'worker_attendance'
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('workers.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)


# ---------------------------------------------------------------------------
# 6. EXPENSES & SYSTEM AUDIT LOGS
# ---------------------------------------------------------------------------
class Expense(db.Model):
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date_logged = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    event_title = db.Column(db.String(150), nullable=False)
    event_desc = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), default='General')
    icon = db.Column(db.String(50), default='bell')
    color = db.Column(db.String(50), default='text-brand')
    date_created = db.Column(db.DateTime, default=datetime.utcnow)