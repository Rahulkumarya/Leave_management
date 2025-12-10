from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import LeaveRequestForm
from .models import EmployeeProfile, LeaveBalance, LeaveRequest
from .services import notify_leave_submitted, get_employee_leave_balances


@login_required
def dashboard(request):
    profile = get_object_or_404(EmployeeProfile, user=request.user)

    recent_leaves = LeaveRequest.objects.filter(employee=profile)[:5]

    current_year = timezone.now().year
    balances = LeaveBalance.objects.filter(
        employee=profile, year=current_year
    ).select_related("leave_type")

    context = {
        "profile": profile,
        "recent_leaves": recent_leaves,
        "balances": balances,
        "current_year": current_year,
    }
    return render(request, "leave_app/dashboard.html", context)


@login_required
def leave_request_list(request):
    profile = get_object_or_404(EmployeeProfile, user=request.user)
    leaves = LeaveRequest.objects.filter(employee=profile)
    return render(request, "leave_app/leave_request_list.html", {"leaves": leaves})


@login_required
def leave_request_create(request):
    employee = request.user.employeeprofile
    balances = get_employee_leave_balances(employee)

    if request.method == "POST":
        form = LeaveRequestForm(
            request.POST,
            request.FILES,
            employee_profile=employee,
        )
        if form.is_valid():
            leave = form.save(commit=False)
            leave.employee = employee
            leave.save()
            messages.success(request, "ส่งคำขอลาเรียบร้อยแล้ว")
            return redirect("leave_app:my_leaves")
    else:
        form = LeaveRequestForm(employee_profile=employee)

    return render(
        request,
        "leave_app/leave_request_form.html",
        {
            "form": form,
            "balances": balances,
        },
    )


@login_required
def leave_request_cancel(request, pk):
    profile = get_object_or_404(EmployeeProfile, user=request.user)
    leave_req = get_object_or_404(LeaveRequest, pk=pk, employee=profile)

    if leave_req.status != LeaveRequest.STATUS_PENDING:
        messages.error(request, "ยกเลิกได้เฉพาะคำขอที่ยัง Pending เท่านั้น")
        return redirect("leave_app:leave_request_list")

    leave_req.status = LeaveRequest.STATUS_CANCELLED
    leave_req.cancelled_at = timezone.now()
    leave_req.save()
    messages.success(request, "ยกเลิกคำขอลาเรียบร้อยแล้ว")
    return redirect("leave_app:leave_request_list")

@login_required
def my_leaves(request):
    employee = request.user.employeeprofile
    current_year = timezone.now().year

    balances = get_employee_leave_balances(employee, year=current_year)

    return render(
        request,
        "leave_app/my_leaves.html",
        {
            "employee": employee,
            "balances": balances,
            "current_year": current_year,
        },
    )