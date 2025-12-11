import os
import uuid
from django.utils import timezone
from django.conf import settings
from django.db import models

class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)

    def __str__(self):
        return f"{self.code} - {self.name}"


class EmployeeProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    employee_code = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subordinates",
    )
    join_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.employee_code} - {self.user.get_full_name() or self.user.username}"


class LeaveType(models.Model):
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    default_allocation = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    allow_half_day = models.BooleanField(default=True)
    require_attachment = models.BooleanField(default=False)
    is_paid = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class LeaveBalance(models.Model):
    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE)
    year = models.PositiveIntegerField()
    allocated = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    used = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        unique_together = ("employee", "leave_type", "year")

    @property
    def remaining(self):
        return self.allocated - self.used

    def __str__(self):
        return f"{self.employee} - {self.leave_type} - {self.year}"


class Holiday(models.Model):
    date = models.DateField(unique=True)
    name = models.CharField(max_length=100)
    is_public = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.date} - {self.name}"

def leave_attachment_upload_to(instance, filename):
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    
    employee_code = "unknown"
    if instance.employee_id and getattr(instance.employee, "employee_code", None):
        employee_code = instance.employee.employee_code

    if instance.start_date:
        date_str = instance.start_date.strftime("%Y%m%d")
    else:
        date_str = timezone.now().strftime("%Y%m%d")
        
    random_suffix = uuid.uuid4().hex[:12]
    
    # รูปแบบ path:leave_attachments/<employee_code>/<YYYYMMDD>_<random>.ext 
    return f"leave_attachments/{employee_code}/{date_str}_{random_suffix}{ext}"

class LeaveRequest(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REJECTED = "REJECTED"
    STATUS_CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_CANCELLED, "Cancelled"),
    ]

    employee = models.ForeignKey(EmployeeProfile, on_delete=models.CASCADE)
    leave_type = models.ForeignKey(LeaveType, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    half_day = models.BooleanField(default=False)
    reason = models.TextField()
    attachment = models.FileField(
        upload_to=leave_attachment_upload_to,
        null=True,
        blank=True,
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_leaves",
    )
    approve_comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.status}] {self.employee} {self.start_date} - {self.end_date}"
