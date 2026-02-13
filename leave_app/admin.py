from django.contrib import admin
from .models import Department, EmployeeProfile, LeaveType, LeaveBalance, Holiday, LeaveRequest


# Register your models here.
admin.site.register(Department)
admin.site.register(EmployeeProfile)
admin.site.register(LeaveType)
admin.site.register(LeaveBalance)
admin.site.register(Holiday)
admin.site.register(LeaveRequest)


# Custom admin site titles
admin.site.site_header = "Leave Management System Admin"
admin.site.site_title = "Leave Management System Portal"
admin.site.index_title = "Welcome to Leave Management System"