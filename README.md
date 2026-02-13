# Leave Management System (Django)

A complete **Leave Management System** built with **Django** and **Tailwind CSS**, designed to handle employee leave workflows in a real-world organization.

This project supports multiple roles (**Employee, Manager, HR, CEO**), leave validation, quota management, approval workflows, email notifications, and reporting.

---

## ✨ Features Overview

### 👤 Employee

* Submit leave requests (full day / half day)
* Upload supporting documents (medical certificate, etc.)
* Automatic validation:

  * Cannot select past dates
  * Cannot select invalid date ranges
  * Cannot overlap existing leave
  * Cannot exceed leave quota
* View personal leave history
* Cancel pending leave requests
* Reset password via email

---

### 👔 Manager

* View pending leave requests from direct subordinates
* Approve / reject leave requests
* Add approval comments
* Automatic quota deduction upon approval
* View approval history

---

### 🧑‍💼 HR

* View and filter all leave requests
* Export leave data (CSV / Excel)
* Create employees manually
* Bulk import employees from Excel (.xlsx)
* Enable / disable user accounts
* Manage leave quotas per employee and year
* Manage departments and leave types

---

### 🧑‍💻 CEO

* Company-wide dashboard
* Yearly statistics:

  * Total employees
  * Total leave requests
  * Approved / Pending / Rejected / Cancelled
* Charts:

  * Monthly leave count
  * Leave by department
  * Leave by type

---

## 🧠 Core Business Logic (`services.py`)

### Leave Validation

* Validates date order and prevents past dates
* Prevents overlapping leave requests
* Supports half-day leave (only if allowed by leave type)
* Skips quota check for unpaid leave
* Uses working-day calculation (excluding weekends and holidays)

### Leave Approval

* Deducts quota **only when approved**
* Handles half-day leave correctly
* Ensures quota is sufficient before approval
* Records approver and comment

### Leave Balance

* Automatically creates leave balances per year
* Handles multiple leave types
* Supports cross-year initialization

### Email Notifications

* Employee receives confirmation after submitting leave
* Manager receives notification for pending approval
* Employee receives status update after approval/rejection
* Password reset handled via Django auth system

---

## 🏗 Project Structure

```
Leave-Management-System/
│
├── config/                 # Django project settings
├── leave_app/              # Main application
│   ├── models.py
│   ├── views.py
│   ├── services.py
│   ├── forms.py
│   ├── fixtures/
│   │   └── initial_data.json
│   ├── templates/
│   │   └── leave_app/
│   └── static/
├── static/                 # Tailwind / assets
├── .env
├── manage.py
└── README.md
```

---

## ⚙️ Tech Stack

* **Backend:** Django 5
* **Frontend:** Django Templates + Tailwind CSS (CDN)
* **Database:** PostgreSQL
* **Auth:** Django Authentication
* **Email:** SMTP (Gmail App Password)
* **Charts:** Chart.js

---

#Setup Environment
python -m venv venv
>> venv\Scripts\activate


#Balances initated 
python manage.py init_leave_balances

#initial data.json load for easy to setup flows 
python manage.py loaddata leave_app/fixtures/initial_data.json




#for runing server 
 python manage.py runserver 0.0.0.0:8000      


 #for live project via cloudflare tunnel
 cloudflared tunnel --url http://localhost:8000/


---

## 🔐 Authentication & Roles

Roles are managed using **Django Groups**:

* Employee (default)
* Manager → `MANAGER`
* HR → `HR` or `is_staff=True`
* CEO → `CEO`

Access control is enforced using:

* `@login_required`
* `@user_passes_test`

---

## ✉️ Email & Password Reset

* Password reset uses Django authentication URLs
* Emails are sent via SMTP
* Development option (console output):

```python
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
```

---

## 🧪 Usage Flow

1. HR creates or imports employees
2. System initializes leave balances
3. Employee submits leave request
4. Manager reviews and approves/rejects
5. System deducts quota and sends notification
6. HR and CEO review reports and dashboards

---

## 🔮 Future Improvements

* Holiday management UI
* Multi-level approval
* Carry-over leave rules
* REST API + React frontend
* Docker deployment

---

## ✅ Project Status

✅ Core leave workflow complete
✅ Role-based access control
✅ Email notification system
✅ Ready for real-world use and extension

---

