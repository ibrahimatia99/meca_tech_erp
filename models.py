# models.py
from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


# ---------------------------------------------------------------------------
# 1. USER AUTHENTICATION & GRANULAR PERMISSIONS
# ---------------------------------------------------------------------------
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(50), default='worker')  # 'admin', 'manager', 'worker'
    
    can_manage_clients = db.Column(db.Boolean, default=True)
    can_manage_quotes = db.Column(db.Boolean, default=True)
    can_manage_stock = db.Column(db.Boolean, default=True)
    can_manage_machines = db.Column(db.Boolean, default=True)
    can_manage_workers = db.Column(db.Boolean, default=True)
    can_manage_expenses = db.Column(db.Boolean, default=True)
    can_access_settings = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ---------------------------------------------------------------------------
# 2. SYSTEM SETTINGS
# ---------------------------------------------------------------------------
class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    
    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), default='general')


# ---------------------------------------------------------------------------
# 3. CLIENTS & SUPPLIERS
# ---------------------------------------------------------------------------
class Client(db.Model):
    __tablename__ = 'clients'
    
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False)
    contact_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    address = db.Column(db.String(255), nullable=True)
    tax_id = db.Column(db.String(100), nullable=True)


class Supplier(db.Model):
    __tablename__ = 'suppliers'
    
    id = db.Column(db.Integer, primary_key=True)
    company_name = db.Column(db.String(150), nullable=False)
    contact_name = db.Column(db.String(100), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(50), nullable=True)


# ---------------------------------------------------------------------------
# 4. QUOTES, INVOICES & PAYMENTS
# ---------------------------------------------------------------------------
class Quote(db.Model):
    __tablename__ = 'quotes'
    
    id = db.Column(db.Integer, primary_key=True)
    quote_number = db.Column(db.String(50), unique=True, nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.now)
    
    subtotal = db.Column(db.Float, default=0.0)
    discount_rate = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    tax_rate = db.Column(db.Float, default=19.0)
    tax_amount = db.Column(db.Float, default=0.0)
    stamp_tax = db.Column(db.Float, default=1.0)
    total_amount = db.Column(db.Float, default=0.0)
    total_in_words = db.Column(db.String(255), nullable=True)
    
    status = db.Column(db.String(50), default='Draft')
    payment_status = db.Column(db.String(50), default='Unpaid')
    amount_paid = db.Column(db.Float, default=0.0)

    remarque = db.Column(db.Text, nullable=True)
    payment_terms = db.Column(db.String(255), nullable=True)
    validite_offre = db.Column(db.String(255), nullable=True)
    delai_livraison = db.Column(db.String(255), nullable=True)
    mode_expedition = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    driver_name = db.Column(db.String(100), nullable=True)
    driver_cin = db.Column(db.String(50), nullable=True)
    vehicle_plate = db.Column(db.String(50), nullable=True)

    client = db.relationship('Client', backref=db.backref('quotes', cascade='all, delete-orphan'))
    items = db.relationship('QuoteItem', backref='quote', cascade='all, delete-orphan')
    payments = db.relationship('PaymentHistory', backref='quote', cascade='all, delete-orphan')

    def recalculate_payment_status(self):
        total_p = sum(p.amount for p in self.payments)
        self.amount_paid = total_p
        if total_p <= 0:
            self.payment_status = 'Unpaid'
        elif total_p >= self.total_amount:
            self.payment_status = 'Paid'
        else:
            self.payment_status = 'Partial'


class QuoteItem(db.Model):
    __tablename__ = 'quote_items'
    
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quotes.id'), nullable=False)
    item_order = db.Column(db.Integer, default=1)
    description = db.Column(db.Text, nullable=False)
    quantity = db.Column(db.Float, default=1.0)
    unit_rate = db.Column(db.Float, default=0.0)
    total_price = db.Column(db.Float, default=0.0)


class PaymentHistory(db.Model):
    __tablename__ = 'payment_history'
    
    id = db.Column(db.Integer, primary_key=True)
    quote_id = db.Column(db.Integer, db.ForeignKey('quotes.id'), nullable=False)
    amount = db.Column(db.Float, default=0.0)
    payment_date = db.Column(db.DateTime, default=datetime.now)
    payment_method = db.Column(db.String(100), default='Espèces / Chèque')
    notes = db.Column(db.String(255), nullable=True)


# ---------------------------------------------------------------------------
# 5. STOCK & MACHINERY
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
    model_type = db.Column(db.String(100), nullable=True)
    serial_number = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(50), default='Operational')
    notes = db.Column(db.Text, nullable=True)


class MaintenanceLog(db.Model):
    __tablename__ = 'maintenance_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey('machines.id'), nullable=False)
    date_logged = db.Column(db.DateTime, default=datetime.now)
    status_logged = db.Column(db.String(50), nullable=False)
    service_description = db.Column(db.Text, nullable=True)
    cost = db.Column(db.Float, default=0.0)
    performed_by = db.Column(db.String(100), nullable=True)

    machine = db.relationship('Machine', backref=db.backref('logs', cascade='all, delete-orphan'))


# ---------------------------------------------------------------------------
# 6. WORKERS, SALARY ADVANCES & PRIMES (BONUSES)
# ---------------------------------------------------------------------------
class Worker(db.Model):
    __tablename__ = 'workers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(50), nullable=True)
    cin_number = db.Column(db.String(50), nullable=True)
    monthly_rate = db.Column(db.Float, default=0.0)
    salary_pay_day = db.Column(db.Integer, default=28)
    last_payroll_processed = db.Column(db.String(7), nullable=True) # Format: "YYYY-MM"
    hire_date = db.Column(db.Date, default=date.today)

    user = db.relationship('User', backref=db.backref('worker_profile', uselist=False))
    advances = db.relationship('SalaryAdvance', backref='worker', lazy=True, cascade='all, delete-orphan')
    bonuses = db.relationship('WorkerBonus', backref='worker', lazy=True, cascade='all, delete-orphan')


class SalaryAdvance(db.Model):
    __tablename__ = 'salary_advances'
    
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('workers.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    date_given = db.Column(db.DateTime, default=datetime.now)
    notes = db.Column(db.String(255), nullable=True)


class WorkerBonus(db.Model):
    __tablename__ = 'worker_bonuses'
    
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('workers.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    title = db.Column(db.String(150), nullable=False, default="Performance Prime")
    date_given = db.Column(db.DateTime, default=datetime.now)
    notes = db.Column(db.String(255), nullable=True)


class WorkerAttendance(db.Model):
    __tablename__ = 'worker_attendance'
    
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('workers.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), nullable=False)

    worker = db.relationship('Worker', backref=db.backref('attendances', cascade='all, delete-orphan'))


# ---------------------------------------------------------------------------
# 7. DIRECT CASH INCOME & EXPENSES
# ---------------------------------------------------------------------------
class DirectCashIncome(db.Model):
    __tablename__ = 'direct_cash_incomes'
    
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    source_client = db.Column(db.String(150), nullable=True)
    date_received = db.Column(db.DateTime, default=datetime.now)
    received_by = db.Column(db.String(100), nullable=True)


class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, default=0.0)
    date_logged = db.Column(db.DateTime, default=datetime.now)


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    event_title = db.Column(db.String(150), nullable=False)
    event_desc = db.Column(db.Text, nullable=True)
    category = db.Column(db.String(50), default='General')
    icon = db.Column(db.String(50), default='bell')
    color = db.Column(db.String(50), default='text-brand')
    date_created = db.Column(db.DateTime, default=datetime.now)


class Job(db.Model):
    __tablename__ = 'jobs'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)  
    description = db.Column(db.Text, nullable=True)     
    cutting_list = db.Column(db.Text, nullable=True)    
    
    priority = db.Column(db.String(20), default='Medium') 
    status = db.Column(db.String(30), default='Pending')  
    
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    due_date = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)

    worker_id = db.Column(db.Integer, db.ForeignKey('workers.id'), nullable=True)
    worker = db.relationship('Worker', backref=db.backref('jobs', lazy=True))

    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=True)
    client = db.relationship('Client', backref=db.backref('jobs', lazy=True))