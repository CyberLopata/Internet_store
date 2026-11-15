from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView, PasswordChangeView, PasswordResetCompleteView, PasswordResetConfirmView,
    PasswordResetDoneView, PasswordResetView,
)
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .account_forms import LoginForm, ProfileForm, RegisterForm
from .models import Order

AUTH_BACKEND = "internet_store.backends.EmailOrUsernameBackend"


def _safe_next(request):
    """Адреса повернення після входу, лише на цей самий сайт (захист від open redirect)."""
    nxt = request.POST.get("next") or request.GET.get("next") or ""
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return ""


def register(request):
    if request.user.is_authenticated:
        return redirect("account")
    form = RegisterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["website"]:  # спрацювала приманка: вдаємо успіх, але нічого не створюємо
            return redirect("index")
        user = form.save()
        if user is not None:
            login(request, user, backend=AUTH_BACKEND)
            messages.success(request, "Акаунт створено. Ласкаво просимо!")
            return redirect(_safe_next(request) or "account")
    return render(request, "account/register.html", {"form": form, "next": _safe_next(request)})


login_view = LoginView.as_view(
    template_name="account/login.html", authentication_form=LoginForm, redirect_authenticated_user=True)


@login_required
def account(request):
    form = ProfileForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Дані збережено.")
        return redirect("account")
    return render(request, "account/profile.html", {"form": form, "section": "profile"})


@login_required
def orders(request):
    return render(request, "account/orders.html", {
        "orders": request.user.orders.prefetch_related("items"), "section": "orders"})


@login_required
def order_detail(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=pk, user=request.user)  # лише власні
    return render(request, "account/order_detail.html", {"order": order, "section": "orders"})


class PasswordChange(SuccessMessageMixin, PasswordChangeView):
    template_name = "account/password_change.html"
    success_url = reverse_lazy("account")
    success_message = "Пароль змінено."

    def get_context_data(self, **kwargs):
        return super().get_context_data(section="password", **kwargs)


class PasswordReset(PasswordResetView):
    template_name = "account/password_reset.html"
    email_template_name = "account/password_reset_email.txt"
    subject_template_name = "account/password_reset_subject.txt"
    success_url = reverse_lazy("password_reset_done")


class PasswordResetDone(PasswordResetDoneView):
    template_name = "account/password_reset_done.html"


class PasswordResetConfirm(PasswordResetConfirmView):
    template_name = "account/password_reset_confirm.html"
    success_url = reverse_lazy("password_reset_complete")


class PasswordResetComplete(PasswordResetCompleteView):
    template_name = "account/password_reset_complete.html"
