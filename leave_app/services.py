from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from decimal import Decimal


from .models import LeaveRequest, LeaveBalance, Holiday, LeaveType, EmployeeProfile

def calculate_working_days(start_date, end_date, half_day=False):
    """คำนวณวันทำงานระหว่างช่วงวันที่ (ตัดเสาร์อาทิตย์ + Holiday)"""
    if half_day:
        return Decimal("0.5")

    days = Decimal("0")
    current = start_date
    while current <= end_date:
        if current.weekday() < 5 and not Holiday.objects.filter(date=current).exists():
            days += Decimal("1")
        current += timedelta(days=1)
    return days

def calculate_working_days_by_year(start_date, end_date, half_day=False):
    """
    คืน dict {year: จำนวนวันลาในปีนั้น} โดย
    - ตัดเสาร์-อาทิตย์
    - ตัด Holiday
    - ถ้า half_day == True ต้องเป็นวันเดียวกัน และให้ 0.5 วัน
    """
    if half_day:
        if start_date != end_date:
            raise ValidationError("ถ้าลาครึ่งวันต้องเป็นวันเดียวกันทั้งวันเริ่มและสิ้นสุด")
        return {start_date.year: Decimal("0.5")}

    days_by_year: dict[int, Decimal] = {}
    current = start_date
    while current <= end_date:
        if current.weekday() < 5 and not Holiday.objects.filter(date=current).exists():
            year = current.year
            if year not in days_by_year:
                days_by_year[year] = Decimal("0")
            days_by_year[year] += Decimal("1")
        current += timedelta(days=1)
    return days_by_year


def validate_leave_request(employee_profile, leave_type, start_date, end_date, half_day=False, instance: LeaveRequest | None = None):
    # 1) เช็กช่วงวันที่
    if end_date < start_date:
        raise ValidationError("End date must be after start date.")

    if start_date < timezone.now().date():
        raise ValidationError("Cannot request leave in the past.")

    # 2) ประเภทนี้รองรับครึ่งวันไหม
    if half_day and not leave_type.allow_half_day:
        raise ValidationError("ประเภทการลานี้ไม่สามารถลาครึ่งวันได้")

    # 3) เช็กซ้อนช่วงลาเดิม (pending / approved)
    overlap_qs = LeaveRequest.objects.filter(
        employee=employee_profile,
        status__in=[LeaveRequest.STATUS_PENDING, LeaveRequest.STATUS_APPROVED],
        start_date__lte=end_date,
        end_date__gte=start_date,
    )

    # 👇 ถ้ามี instance (เช่น ตอน approve ใบนี้เอง) ให้ตัดตัวมันออกจาก query
    if instance is not None:
        overlap_qs = overlap_qs.exclude(pk=instance.pk)

    if overlap_qs.exists():
        raise ValidationError("Leave request overlaps with existing leave.")

    # 4) คำนวณจำนวนวันลา (แยกตามปี)
    days_by_year = calculate_working_days_by_year(start_date, end_date, half_day)

    # 5) ถ้าเป็นลาแบบไม่จ่ายเงิน (UNPAID) ไม่ต้องเช็กโควต้า
    if not leave_type.is_paid:
        return sum(days_by_year.values())

    # 6) เช็กโควต้าต่อปี
    for year, days in days_by_year.items():
        try:
            balance = LeaveBalance.objects.get(
                employee=employee_profile,
                leave_type=leave_type,
                year=year,
            )
        except LeaveBalance.DoesNotExist:
            raise ValidationError(
                f"No leave balance for {leave_type.name} in year {year}."
            )

        if days > balance.remaining:
            raise ValidationError(
                f"Not enough leave balance for {leave_type.name} in {year}. "
                f"(remaining {balance.remaining}, requested {days})"
            )

    return sum(days_by_year.values())


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

    # validate อีกครั้ง กันกรณีโควต้า/ข้อมูลมีการเปลี่ยนระหว่างรออนุมัติ
    validate_leave_request(
        leave_request.employee,
        leave_request.leave_type,
        leave_request.start_date,
        leave_request.end_date,
        leave_request.half_day,
        instance=leave_request,
    )

    # คำนวณวันลาต่อปี (ใช้ฟังก์ชันใหม่)
    days_by_year = calculate_working_days_by_year(
        leave_request.start_date,
        leave_request.end_date,
        leave_request.half_day,
    )

    # ลาแบบไม่จ่ายเงิน → ไม่ยุ่งกับ LeaveBalance
    if leave_request.leave_type.is_paid:
        for year, days in days_by_year.items():
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
    
def get_employee_leave_balances(employee_profile, year=None):
    if year is None:
        year = timezone.now().year

    balances = (
        LeaveBalance.objects
        .select_related("leave_type")
        .filter(employee=employee_profile, year=year)
    )

    return balances
