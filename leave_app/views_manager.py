from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from .models import EmployeeProfile, LeaveRequest
from .services import approve_leave_request, reject_leave_request


def is_manager(user):
    return user.is_superuser or user.groups.filter(name="MANAGER").exists()


@user_passes_test(is_manager)
def manager_leave_list(request):
    subordinates = EmployeeProfile.objects.filter(manager=request.user)

    pending_leaves = LeaveRequest.objects.filter(
        employee__in=subordinates,
        status=LeaveRequest.STATUS_PENDING,
    ).select_related("employee", "leave_type")

    history_leaves = (
        LeaveRequest.objects.filter(employee__in=subordinates)
        .exclude(status=LeaveRequest.STATUS_PENDING)
        .select_related("employee", "leave_type", "approver")
        .order_by("-updated_at")
    )

    context = {
        "pending_leaves": pending_leaves,
        "history_leaves": history_leaves,
    }
    return render(request, "leave_app/manager/manager_leave_list.html", context)


@user_passes_test(is_manager)
def manager_leave_detail(request, pk):
    leave_req = get_object_or_404(
        LeaveRequest.objects.select_related("employee", "leave_type"),
        pk=pk,
    )

    if leave_req.employee.manager != request.user and not request.user.is_superuser:
        return HttpResponseForbidden("You do not have permission to view this request")

    if request.method == "POST":
        action = request.POST.get("action")
        comment = request.POST.get("comment", "")

        try:
            if action == "approve":
                approve_leave_request(leave_req, approver=request.user, comment=comment)
                messages.success(request, "Leave request approved successfully")
            elif action == "reject":
                reject_leave_request(leave_req, approver=request.user, comment=comment)
                messages.success(request, "Leave request rejected successfully")
            else:
                messages.error(request, "Invalid action")
        except ValidationError as e:
            messages.error(request, e.message)

        return redirect("leave_app:manager_leave_list")

    context = {"leave": leave_req}
    return render(request, "leave_app/manager/manager_leave_detail.html", context)
