from django.core.management.base import BaseCommand
from django.utils import timezone
from leave_app.models import EmployeeProfile
from leave_app.services import create_default_leave_balances


class Command(BaseCommand):
    help = "Initialize leave balances for all employees for the current year"

    def handle(self, *args, **options):
        year = timezone.now().year
        employees = EmployeeProfile.objects.all()
        if not employees.exists():
            self.stdout.write(self.style.WARNING("No employees found."))
            return

        for employee in employees:
            create_default_leave_balances(employee, year)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Leave balances created for {employee.user.username} ({year})"
                )
            )

        self.stdout.write(
            self.style.SUCCESS("✅ Leave balances initialized for all employees")
        )
