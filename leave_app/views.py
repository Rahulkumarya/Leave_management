# รวม view ฝั่ง employee
from .views_employee import (
    dashboard,
    leave_request_list,
    leave_request_create,
    leave_request_cancel,
    my_leaves,
)

# รวม view ฝั่ง manager
from .views_manager import (
    manager_leave_list,
    manager_leave_detail,
)

# รวม view ฝั่ง HR
from .views_hr import (
    hr_leave_dashboard,
    hr_employee_list,
    hr_employee_create,
    hr_employee_edit,
    hr_employee_toggle_active,
    hr_employee_import,
    hr_leave_balance_manage,
    hr_export_leaves_csv,
    hr_export_leaves_excel,
)

# รวม view ฝั่ง CEO
from .views_ceo import ceo_dashboard

# auth
from .views_auth import register, logout_view
