from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings

from .models import LeaveRequest, LeaveBalance, Holiday, LeaveType, EmployeeProfile

def calculate_working_days(start_date, end_date, half_day=False):
    """คำนวณวันทำงานระหว่างช่วงวันที่ (ตัดเสาร์อาทิตย์ + Holiday)"""
    if half_day:
        return 0.5

    days = 0
    current = start_date
    while current <= end_date:
        # weekday 0-4 = จันทร์-ศุกร์
        if current.weekday() < 5 and not Holiday.objects.filter(date=current).exists():
            days += 1
        current += timedelta(days=1)
    return days


def validate_leave_request(employee_profile, leave_type, start_date, end_date, half_day=False):
    if end_date < start_date:
        raise ValidationError("End date must be after start date.")

    if start_date < timezone.now().date():
        raise ValidationError("Cannot request leave in the past.")

    # ✅ เช็คว่าประเภทนี้อนุญาตให้ลาครึ่งวันไหม
    if half_day and not leave_type.allow_half_day:
        raise ValidationError("ประเภทการลานี้ไม่สามารถลาครึ่งวันได้")

    # เช็คซ้อนช่วง
    overlap = LeaveRequest.objects.filter(
        employee=employee_profile,
        status__in=[LeaveRequest.STATUS_PENDING, LeaveRequest.STATUS_APPROVED],
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).exists()
    if overlap:
        raise ValidationError("Leave request overlaps with existing leave.")

    days = calculate_working_days(start_date, end_date, half_day)
    current_year = start_date.year

    # ✅ ถ้าเป็นประเภทลาแบบไม่จ่ายเงิน (UNPAID) จะไม่เช็กโควตา
    if not leave_type.is_paid:
        return days  # ไม่ต้องมี LeaveBalance ก็ได้

    try:
        balance = LeaveBalance.objects.get(
            employee=employee_profile,
            leave_type=leave_type,
            year=current_year,
        )
    except LeaveBalance.DoesNotExist:
        raise ValidationError("No leave balance for this type/year.")

    if days > balance.remaining:
        raise ValidationError("Not enough leave balance.")

    return days

def get_leave_days_for_request(leave_request: LeaveRequest) -> float:
    """
    คำนวณจำนวนวันลาสำหรับ leave_request ที่มีอยู่ (ใช้ตอน approve)
    """
    return calculate_working_days(
        leave_request.start_date,
        leave_request.end_date,
        leave_request.half_day,
    )


def approve_leave_request(leave_request: LeaveRequest, approver, comment: str = ""):
    if leave_request.status != LeaveRequest.STATUS_PENDING:
        raise ValidationError("อนุมัติได้เฉพาะคำขอที่อยู่ในสถานะ Pending เท่านั้น")

    days = get_leave_days_for_request(leave_request)
    year = leave_request.start_date.year

    # ✅ ถ้าไม่จ่ายเงิน (UNPAID) ไม่ต้องยุ่งกับ LeaveBalance
    if leave_request.leave_type.is_paid:
        try:
            balance = LeaveBalance.objects.get(
                employee=leave_request.employee,
                leave_type=leave_request.leave_type,
                year=year,
            )
        except LeaveBalance.DoesNotExist:
            raise ValidationError("ไม่พบ LeaveBalance สำหรับคำขอนี้")

        if days > balance.remaining:
            raise ValidationError("โควต้าวันลาไม่เพียงพอ")

        balance.used += days
        balance.save()

    # อัปเดตสถานะคำขอ
    leave_request.status = LeaveRequest.STATUS_APPROVED
    leave_request.approver = approver
    leave_request.approve_comment = comment
    leave_request.updated_at = timezone.now()
    leave_request.save()

    notify_leave_status_changed(leave_request)


def reject_leave_request(leave_request: LeaveRequest, approver, comment: str = ""):
    """
    ใช้ปฏิเสธคำขอลา (ไม่ยุ่งกับ balance)
    """
    if leave_request.status != LeaveRequest.STATUS_PENDING:
        raise ValidationError("ปฏิเสธได้เฉพาะคำขอที่อยู่ในสถานะ Pending เท่านั้น")

    leave_request.status = LeaveRequest.STATUS_REJECTED
    leave_request.approver = approver
    leave_request.approve_comment = comment
    leave_request.updated_at = timezone.now()
    leave_request.save()

    notify_leave_status_changed(leave_request)
    
def create_default_leave_balances(employee_profile: EmployeeProfile, year: int | None = None):
    if year is None:
        year = timezone.now().year

    leave_types = LeaveType.objects.all()
    for lt in leave_types:
        LeaveBalance.objects.get_or_create(
            employee=employee_profile,
            leave_type=lt,
            year=year,
            defaults={
                "allocated": lt.default_allocation,
                "used": 0,
            },
        )
        
def _send_leave_email(subject: str, message: str, to_emails: list[str]):
    if not to_emails:
        return
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        to_emails,
        fail_silently=True,  # กัน error ใน production
    )


def notify_leave_submitted(leave_request: LeaveRequest):
    emp = leave_request.employee
    user = emp.user
    manager = emp.manager

    # แจ้งพนักงาน
    if user.email:
        subject = f"ยืนยันคำขอลางานของคุณ ({leave_request.leave_type.name})"
        message = (
            f"คุณได้ส่งคำขอลางานแล้ว\n"
            f"ประเภท: {leave_request.leave_type.name}\n"
            f"ช่วงเวลา: {leave_request.start_date} - {leave_request.end_date}\n"
            f"สถานะปัจจุบัน: {leave_request.get_status_display()}\n"
        )
        _send_leave_email(subject, message, [user.email])

    # แจ้งหัวหน้า (ถ้ามี email)
    if manager and manager.email:
        subject = f"[Pending] คำขอลางานใหม่จาก {user.get_full_name() or user.username}"
        message = (
            f"มีคำขอลางานใหม่รออนุมัติ\n"
            f"พนักงาน: {emp.employee_code} - {user.get_full_name() or user.username}\n"
            f"ประเภท: {leave_request.leave_type.name}\n"
            f"ช่วงเวลา: {leave_request.start_date} - {leave_request.end_date}\n"
            f"เหตุผล: {leave_request.reason}\n"
        )
        _send_leave_email(subject, message, [manager.email])


def notify_leave_status_changed(leave_request: LeaveRequest):
    emp = leave_request.employee
    user = emp.user

    if not user.email:
        return

    subject = f"คำขอลางานของคุณถูกอัปเดตเป็น {leave_request.get_status_display()}"
    message = (
        f"คำขอลางานของคุณถูกอัปเดตแล้ว\n"
        f"ประเภท: {leave_request.leave_type.name}\n"
        f"ช่วงเวลา: {leave_request.start_date} - {leave_request.end_date}\n"
        f"สถานะใหม่: {leave_request.get_status_display()}\n"
        f"หมายเหตุหัวหน้า: {leave_request.approve_comment or '-'}\n"
    )
    _send_leave_email(subject, message, [user.email])