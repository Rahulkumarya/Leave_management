from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
from decimal import Decimal


from .models import LeaveRequest, LeaveBalance, Holiday, LeaveType, EmployeeProfile


def calculate_working_days(start_date, end_date, half_day=False):
    """Calculate working days between dates (exclude weekends + holidays)"""
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
    Return dict {year: leave_days_in_that_year}
    - Exclude weekends
    - Exclude holidays
    - If half_day == True must be same start and end date and return 0.5
    """
    if half_day:
        if start_date != end_date:
            raise ValidationError(
                "Half-day leave must have the same start and end date."
            )
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


def validate_leave_request(
    employee_profile,
    leave_type,
    start_date,
    end_date,
    half_day=False,
    instance: LeaveRequest | None = None,
):
    # 1) Check date range
    if end_date < start_date:
        raise ValidationError("End date must be after start date.")

    if start_date < timezone.now().date():
        raise ValidationError("Cannot request leave in the past.")

    # 2) Check if leave type allows half-day
    if half_day and not leave_type.allow_half_day:
        raise ValidationError("This leave type does not allow half-day leave.")

    # 3) Check overlapping leave (pending / approved)
    overlap_qs = LeaveRequest.objects.filter(
        employee=employee_profile,
        status__in=[LeaveRequest.STATUS_PENDING, LeaveRequest.STATUS_APPROVED],
        start_date__lte=end_date,
        end_date__gte=start_date,
    )

    # Exclude current instance (e.g., during approval)
    if instance is not None:
        overlap_qs = overlap_qs.exclude(pk=instance.pk)

    if overlap_qs.exists():
        raise ValidationError("Leave request overlaps with existing leave.")

    # 4) Calculate leave days (by year)
    days_by_year = calculate_working_days_by_year(start_date, end_date, half_day)

    # 5) If unpaid leave, skip quota check
    if not leave_type.is_paid:
        return sum(days_by_year.values())

    # 6) Check yearly quota
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
    Calculate leave days for an existing leave_request (used during approval)
    """
    return calculate_working_days(
        leave_request.start_date,
        leave_request.end_date,
        leave_request.half_day,
    )


def approve_leave_request(leave_request: LeaveRequest, approver, comment: str = ""):
    if leave_request.status != LeaveRequest.STATUS_PENDING:
        raise ValidationError("Only pending requests can be approved.")

    validate_leave_request(
        leave_request.employee,
        leave_request.leave_type,
        leave_request.start_date,
        leave_request.end_date,
        leave_request.half_day,
        instance=leave_request,
    )

    days_by_year = calculate_working_days_by_year(
        leave_request.start_date,
        leave_request.end_date,
        leave_request.half_day,
    )

    if leave_request.leave_type.is_paid:
        for year, days in days_by_year.items():
            try:
                balance = LeaveBalance.objects.get(
                    employee=leave_request.employee,
                    leave_type=leave_request.leave_type,
                    year=year,
                )
            except LeaveBalance.DoesNotExist:
                raise ValidationError("Leave balance not found for this request.")

            if days > balance.remaining:
                raise ValidationError("Insufficient leave balance.")

            balance.used += days
            balance.save()

    leave_request.status = LeaveRequest.STATUS_APPROVED
    leave_request.approver = approver
    leave_request.approve_comment = comment
    leave_request.updated_at = timezone.now()
    leave_request.save()
    print("Leave:", leave_request.leave_type.name)
    print("Dates:", leave_request.start_date, "-", leave_request.end_date)
    print("Half day?", leave_request.half_day)
    print("Days by year:", days_by_year)

    notify_leave_status_changed(leave_request)


def reject_leave_request(leave_request: LeaveRequest, approver, comment: str = ""):
    """
    Reject leave request (does not affect balance)
    """
    if leave_request.status != LeaveRequest.STATUS_PENDING:
        raise ValidationError("Only pending requests can be rejected.")

    leave_request.status = LeaveRequest.STATUS_REJECTED
    leave_request.approver = approver
    leave_request.approve_comment = comment
    leave_request.updated_at = timezone.now()
    leave_request.save()

    notify_leave_status_changed(leave_request)





def create_default_leave_balances(
    employee_profile: EmployeeProfile, year: int | None = None
):
    if year is None:
        year = timezone.now().year

    leave_types = LeaveType.objects.all()
    for lt in leave_types:
        balance, created = LeaveBalance.objects.get_or_create(
            employee=employee_profile,
            leave_type=lt,
            year=year,
            defaults={
                "allocated": Decimal(lt.default_allocation),
                "used": Decimal("0"),
            },
        )
        if created:
            print(
                f"✅ Leave balance created for {employee_profile.user.username} - {lt.name} ({year})"
            )
        else:
            print(
                f"ℹ️ Leave balance already exists for {employee_profile.user.username} - {lt.name} ({year})"
            )


def _send_leave_email(subject: str, message: str, to_emails: list[str]):
    if not to_emails:
        return
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        to_emails,
        fail_silently=True,  # prevent errors in production
    )


def notify_leave_submitted(leave_request: LeaveRequest):
    emp = leave_request.employee
    user = emp.user
    manager = emp.manager

    if user.email:
        subject = (
            f"Your leave request has been submitted ({leave_request.leave_type.name})"
        )
        message = (
            f"You have submitted a leave request\n"
            f"Type: {leave_request.leave_type.name}\n"
            f"Period: {leave_request.start_date} - {leave_request.end_date}\n"
            f"Current status: {leave_request.get_status_display()}\n"
        )
        _send_leave_email(subject, message, [user.email])

    if manager and manager.email:
        subject = (
            f"[Pending] New leave request from {user.get_full_name() or user.username}"
        )
        message = (
            f"A new leave request is awaiting approval\n"
            f"Employee: {emp.employee_code} - {user.get_full_name() or user.username}\n"
            f"Type: {leave_request.leave_type.name}\n"
            f"Period: {leave_request.start_date} - {leave_request.end_date}\n"
            f"Reason: {leave_request.reason}\n"
        )
        _send_leave_email(subject, message, [manager.email])


def notify_leave_status_changed(leave_request: LeaveRequest):
    emp = leave_request.employee
    user = emp.user

    if not user.email:
        return

    subject = (
        f"Your leave request has been updated to {leave_request.get_status_display()}"
    )
    message = (
        f"Your leave request has been updated\n"
        f"Type: {leave_request.leave_type.name}\n"
        f"Period: {leave_request.start_date} - {leave_request.end_date}\n"
        f"New status: {leave_request.get_status_display()}\n"
        f"Manager comment: {leave_request.approve_comment or '-'}\n"
    )
    _send_leave_email(subject, message, [user.email])


def get_employee_leave_balances(employee_profile, year=None):
    if year is None:
        year = timezone.now().year

    balances = LeaveBalance.objects.select_related("leave_type").filter(
        employee=employee_profile, year=year
    )

    return balances
