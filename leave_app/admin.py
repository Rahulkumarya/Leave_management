# from django.contrib import admin
# from .models import Department, EmployeeProfile, LeaveType, LeaveBalance, Holiday, LeaveRequest


# # Register your models here.
# admin.site.register(Department)
# admin.site.register(EmployeeProfile)
# admin.site.register(LeaveType)
# admin.site.register(LeaveBalance)
# admin.site.register(Holiday)
# admin.site.register(LeaveRequest)


# # Custom admin site titles
# admin.site.site_header = "Leave Management System Admin"
# admin.site.site_title = "Leave Management System Portal"
# admin.site.index_title = "Welcome to Leave Management System"

from django.contrib import admin
from django.core.exceptions import ValidationError

from .models import (
    Department,
    EmployeeProfile,
    LeaveType,
    LeaveBalance,
    Holiday,
    LeaveRequest,
)
from .services import approve_leave_request


admin.site.register(Department)
admin.site.register(EmployeeProfile)
admin.site.register(LeaveType)
admin.site.register(LeaveBalance)
admin.site.register(Holiday)


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "start_date", "end_date", "status")

    def save_model(self, request, obj, form, change):

        if change:
            old_obj = LeaveRequest.objects.get(pk=obj.pk)

            # If status changed from PENDING → APPROVED
            if (
                old_obj.status == LeaveRequest.STATUS_PENDING
                and obj.status == LeaveRequest.STATUS_APPROVED
            ):
                try:
                    approve_leave_request(old_obj, request.user)
                    return
                except ValidationError as e:
                    self.message_user(request, f"Error: {e}", level="error")
                    return

        super().save_model(request, obj, form, change)

# Custom admin titles
admin.site.site_header = "Leave Management System Admin"
admin.site.site_title = "Leave Management System Portal"
admin.site.index_title = "Welcome to Leave Management System"
