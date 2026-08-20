# ⚙️ MECA-TECH ATIA ERP — Version 4.0

![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Flask](https://img.shields.io/badge/Framework-Flask%20v3.x-green.svg)
![Database](https://img.shields.io/badge/Database-SQLite%20%2F%20SQLAlchemy-orange.svg)
![TailwindCSS](https://img.shields.io/badge/UI-TailwindCSS%20%2F%20LucideIcons-06B6D4.svg)
![Version](https://img.shields.io/badge/Release-v4.0-purple.svg)

**MECA-TECH ATIA ERP** is a lightweight, high-performance Enterprise Resource Planning system specifically engineered for metal fabrication workshops, custom machine builders, and industrial prototyping labs.

Version 4.0 introduces **Granular Access Control**, an overhauled **2-Column Settings Dashboard**, a complete **Salary Augmentations & Primes (Bonuses) Engine**, and **Lifetime Worked-Months Payroll Archives**.

---

## 📸 Interface Screenshots

| System Settings & Visual Branding (2-Column Layout) | Active System Users Roster & Access Control |
| :---: | :---: |
| ![Settings Dashboard](static/uploads/logo_1787182871_logo_2.png) | *(Granular Checkboxes & Edit Permission Modals)* |

| Worker Profile, Salary Augmentation & Primes | Job Orders & Cutting Lists Management |
| :---: | :---: |
| *(Salary Adjustments, Advances & Primes Hub)* | *(Shop Floor Task Assignments)* |

---

## 🚀 Key Features in Version 4.0

### 🛡️ 1. Granular User Access Control & Security
* **Section-Level Checkboxes**: Assign or revoke access per user for individual ERP modules:
  * 👥 **Clients Directory**
  * 📑 **Documents & Invoicing** (*Devis, Factures, Bon de Livraison*)
  * 📦 **Stock & Raw Materials**
  * 🛠️ **Machinery Maintenance Logs**
  * 👷 **Workers & Payroll**
  * 📂 **Financial Archives & Expenses**
  * ⚙️ **System Settings**
* **Active Users Roster**: Instantly edit permissions, user credentials, or reset passwords via interactive slide-over modals without refreshing the page.

### 💰 2. Advanced Worker Payroll Hub
* **Salary Adjustments & Augmentations**: Support for base salary raises, deductions, or manual rate adjustments with full audit logging.
* **Primes (Performance Bonuses)**: Add, edit, or delete custom performance bonuses (*Primes*) per worker for any given active month.
* **Salary Advances (*Avances*)**: Record and track salary advances against active monthly payroll.
* **Worked-Months Archive**: Historical *Fiche de Paie* generator filtering strictly to months where actual shop work or financial advances/bonuses occurred.
* **Automated Payroll Execution**: Auto-logs salary expenses when a worker's designated payday arrives.

### ⚙️ 3. Redesigned Settings & Visual Branding
* **2-Column Split Layout**:
  * **Left Column**: Business Identity, Matricule Fiscal, contact details, custom color themes, logo & favicon upload parameters, and one-click SQLite DB backup generation.
  * **Right Column**: New User Registration and Active Users Roster table.
* **Custom Printing Header**: Direct branding integration into printable *Devis*, *Facture*, and *Bon de Livraison* documents.

### 📋 4. Job Orders & Workshop Floor Operations
* **Task Assignment**: Assign cutting lists, assembly tasks, and metal fabrication jobs directly to registered workers.
* **Priority Tracking**: Categorize job orders by priority (*Low, Medium, High, Urgent*) and track completion dates.

---

## 🛠️ Tech Stack & Dependencies

* **Backend**: Python 3.10+, Flask, Flask-SQLAlchemy, Flask-Login, Werkzeug
* **Database**: SQLite3 (Production convertible to PostgreSQL)
* **Frontend**: HTML5, TailwindCSS (CDN / JIT), Lucide Icons
* **Document Generation**: HTML/CSS to PDF & Browser Print Engine

---

## 📂 Project Structure

```text
meca_tech_erp/
├── app.py                     # Application Initialization & Flask App Factory
├── extensions.py              # SQLAlchemy & Extension Bindings
├── models.py                  # Database Models (User, Worker, Bonus, Quote, Job, etc.)
├── meca_tech.db               # SQLite Local Database File
├── routes/
│   ├── admin_history.py       # Financial Logs & Expense Archives
│   ├── clients.py             # Client & Supplier Management
│   ├── jobs.py                # Workshop Jobs & Cutting Lists
│   ├── machines.py            # Machinery Maintenance Logs
│   ├── quotes.py              # Invoices, Quotes & Delivery Notes
│   ├── settings.py            # App Branding & User Access Control
│   ├── stock.py               # Raw Materials & Stock Management
│   ├── worker_portal.py       # Worker Self-Service Portal & Fiche de Paie
│   └── workers.py             # Worker Payroll, Salary Augmentations & Primes
├── static/
│   └── uploads/               # Logos, Favicons, and Media Assets
├── templates/
│   ├── base.html              # Core Layout & Dynamic Navigation Sidebar
│   ├── jobs/                  # Job Order Views
│   ├── quotes/                # Print Templates (Invoice, Devis, BL)
│   ├── settings/              # Settings & Access Control Layout
│   └── workers/               # Roster, Calendar & Detail Views
└── utils/
    ├── helpers.py             # Formatters, Parsers & Notifications
    └── settings.py            # System Setting Getters/Setters
