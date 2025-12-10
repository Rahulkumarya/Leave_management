import json
from datetime import timedelta

from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.shortcuts import render
from django.utils import timezone

from .models import EmployeeProfile, LeaveRequest
from .services import calculate_working_days


def is_ceo(user):
    return user.is_superuser or user.groups.filter(name="CEO").exists()


@user_passes_test(is_ceo)
def ceo_dashboard(request):
    year_param = request.GET.get("year")
    try:
        year = int(year_param) if year_param else timezone.now().year
    except ValueError:
        year = timezone.now().year

    # พนักงานที่ยัง Active
    total_employees = EmployeeProfile.objects.filter(
        user__is_active=True
    ).count()

    # คำขอทุกสถานะในปีนั้น
    qs_year = LeaveRequest.objects.filter(start_date__year=year)

    total_requests = qs_year.count()
    pending_count = qs_year.filter(status=LeaveRequest.STATUS_PENDING).count()
    approved_count = qs_year.filter(status=LeaveRequest.STATUS_APPROVED).count()
    rejected_count = qs_year.filter(status=LeaveRequest.STATUS_REJECTED).count()
    cancelled_count = qs_year.filter(status=LeaveRequest.STATUS_CANCELLED).count()

    # ✅ ใช้เฉพาะใบที่ Approved สำหรับการนับ "วันลา"
    approved_qs_year = (
        qs_year.filter(status=LeaveRequest.STATUS_APPROVED)
        .select_related("employee__user", "employee__department", "leave_type")
    )

    # ---------- KPI: total & avg leave days ----------
    total_leave_days = 0.0

    # สำหรับอันดับแผนก / พนักงาน
    dept_days: dict[str, float] = {}
    emp_days: dict[EmployeeProfile, float] = {}

    for leave in approved_qs_year:
        days = float(
            calculate_working_days(
                leave.start_date,
                leave.end_date,
                leave.half_day,
            )
        )
        total_leave_days += days

        # รวมวันลาเป็นรายแผนก
        dept_name = leave.employee.department.name if leave.employee.department else "No Dept"
        dept_days[dept_name] = dept_days.get(dept_name, 0.0) + days

        # รวมวันลาเป็นรายพนักงาน
        emp = leave.employee
        emp_days[emp] = emp_days.get(emp, 0.0) + days

    avg_leave_days_per_employee = (
        total_leave_days / total_employees if total_employees else 0.0
    )

    # ---------- Top Departments (by leave days) ----------
    top_departments = sorted(
        dept_days.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:5]

    top_departments = [
        {"name": name, "days": days} for name, days in top_departments
    ]

    # ---------- Top Employees (by leave days) ----------
    top_employees_raw = sorted(
        emp_days.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:5]

    top_employees = []
    for emp, days in top_employees_raw:
        user = emp.user
        top_employees.append(
            {
                "employee": emp,
                "code": emp.employee_code,
                "name": user.get_full_name() or user.username,
                "department": emp.department.name if emp.department else "-",
                "days": days,
            }
        )

    # ---------- กราฟจำนวนคำขอลาต่อเดือน ----------
    monthly_qs = (
        qs_year.annotate(month=TruncMonth("start_date"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )

    monthly_labels = [item["month"].strftime("%b") for item in monthly_qs]
    monthly_counts = [item["count"] for item in monthly_qs]

    # ---------- กราฟตามแผนก ----------
    dept_qs = (
        qs_year.values("employee__department__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    department_labels = [
        (item["employee__department__name"] or "No Dept") for item in dept_qs
    ]
    department_counts = [item["count"] for item in dept_qs]

    # ---------- กราฟตามประเภทการลา ----------
    type_qs = (
        qs_year.values("leave_type__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    leave_type_labels = [item["leave_type__name"] for item in type_qs]
    leave_type_counts = [item["count"] for item in type_qs]

    # ✅ ตารางลาช่วงนี้ (วันนี้ + 7 วันถัดไป) เฉพาะ Approved
    today = timezone.now().date()
    next_7 = today + timedelta(days=7)

    upcoming_leaves = (
        LeaveRequest.objects
        .select_related("employee__user", "employee__department", "leave_type")
        .filter(
            status=LeaveRequest.STATUS_APPROVED,
            start_date__lte=next_7,
            end_date__gte=today,
        )
        .order_by("start_date", "employee__department__name")
    )

    context = {
        "year": year,
        "total_employees": total_employees,
        "total_requests": total_requests,
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "cancelled_count": cancelled_count,
        "total_leave_days": total_leave_days,
        "avg_leave_days_per_employee": avg_leave_days_per_employee,
        "top_departments": top_departments,
        "top_employees": top_employees,
        "monthly_labels_json": json.dumps(monthly_labels),
        "monthly_counts_json": json.dumps(monthly_counts),
        "department_labels_json": json.dumps(department_labels),
        "department_counts_json": json.dumps(department_counts),
        "leave_type_labels_json": json.dumps(leave_type_labels),
        "leave_type_counts_json": json.dumps(leave_type_counts),
        "upcoming_leaves": upcoming_leaves,
    }
    return render(request, "leave_app/ceo/ceo_dashboard.html", context)
