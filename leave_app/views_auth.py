from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect

from .models import EmployeeProfile
from .services import create_default_leave_balances


def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()

            employee_code = f"EMP{user.id:04d}"
            profile = EmployeeProfile.objects.create(
                user=user,
                employee_code=employee_code,
                department=None,
            )

            create_default_leave_balances(profile)

            auth_login(request, user)
            messages.success(request, "Registration successful")
            return redirect("leave_app:dashboard")
    else:
        form = UserCreationForm()

    return render(request, "registration/register.html", {"form": form})


def logout_view(request):
    auth_logout(request)
    return redirect("login")
