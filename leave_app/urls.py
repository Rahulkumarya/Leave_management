from django.urls import path, include
from . import views

app_name = "leave_app"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    
    path("my-leaves/", views.leave_request_list, name="leave_request_list"),
    path("my-leaves/new/", views.leave_request_create, name="leave_request_create"),
    path("my-leaves/<int:pk>/cancel/", views.leave_request_cancel, name="leave_request_cancel"),

    # Manager
    path("manager/leaves/", views.manager_leave_list, name="manager_leave_list"),
    path("manager/leaves/<int:pk>/", views.manager_leave_detail, name="manager_leave_detail"),

    # HR - Leaves
    path("hr/leaves/", views.hr_leave_dashboard, name="hr_leave_dashboard"),
    path("hr/leaves/export/csv/", views.hr_export_leaves_csv, name="hr_export_leaves_csv"),
    path("hr/leaves/export/excel/", views.hr_export_leaves_excel, name="hr_export_leaves_excel"),

    # HR - Employees
    path("hr/employees/", views.hr_employee_list, name="hr_employee_list"),
    path("hr/employees/new/", views.hr_employee_create, name="hr_employee_create"),
    path("hr/employees/import/", views.hr_employee_import, name="hr_employee_import"),
    path("hr/employees/<int:pk>/", views.hr_employee_edit, name="hr_employee_edit"),
    path("hr/employees/<int:pk>/toggle-active/", views.hr_employee_toggle_active, name="hr_employee_toggle_active"),

    # HR - Balances
    path("hr/balances/", views.hr_leave_balance_manage, name="hr_leave_balance_manage"),

    # CEO
    path("ceo/dashboard/", views.ceo_dashboard, name="ceo_dashboard"),
    
    # auth
    path("accounts/", include("django.contrib.auth.urls")),
]
