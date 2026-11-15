from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import password_validators_help_text_html, validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q

from .models import get_profile

User = get_user_model()


def email_taken(email, exclude_pk=None):
    """Чи зайнятий email (як логін або як адреса іншого акаунта), без урахування регістру."""
    qs = User.objects.filter(Q(username__iexact=email) | Q(email__iexact=email))
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.exists()


class RegisterForm(forms.Form):
    first_name = forms.CharField(
        label="Ім'я", max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Ваше ім'я", "autocomplete": "given-name"}),
    )
    email = forms.EmailField(
        label="Email", max_length=150,
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com", "autocomplete": "email"}),
    )
    phone = forms.CharField(
        label="Телефон", max_length=32, required=False,
        widget=forms.TextInput(attrs={"placeholder": "+380… (необов'язково)", "autocomplete": "tel", "inputmode": "tel"}),
    )
    password1 = forms.CharField(
        label="Пароль", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
        help_text=password_validators_help_text_html(),
    )
    password2 = forms.CharField(
        label="Повторіть пароль", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    # Приманка для ботів: людина це поле не бачить і не заповнює.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"tabindex": "-1", "autocomplete": "off"}))

    def clean_first_name(self):
        return self.cleaned_data["first_name"].strip()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if email_taken(email):
            raise ValidationError("Акаунт з таким email уже існує. Спробуйте увійти.")
        return email

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2:
            if p1 != p2:
                self.add_error("password2", "Паролі не збігаються.")
            else:
                email = data.get("email", "")
                candidate = User(username=email, email=email, first_name=data.get("first_name", ""))
                try:
                    validate_password(p1, candidate)
                except ValidationError as e:
                    self.add_error("password1", e)
        return data

    def save(self):
        """Створює користувача (логін = email). Повертає None, якщо email встигли зайняти."""
        d = self.cleaned_data
        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    username=d["email"], email=d["email"], password=d["password1"], first_name=d["first_name"])
        except IntegrityError:
            self.add_error("email", "Акаунт з таким email уже існує. Спробуйте увійти.")
            return None
        if d["phone"]:
            profile = get_profile(user)
            profile.phone = d["phone"]
            profile.save(update_fields=["phone"])
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Email", max_length=254,
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username", "placeholder": "you@example.com"}),
    )
    password = forms.CharField(
        label="Пароль", strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    error_messages = {
        "invalid_login": "Невірний email або пароль.",
        "inactive": "Цей акаунт вимкнено.",
    }


class ProfileForm(forms.Form):
    first_name = forms.CharField(label="Ім'я", max_length=150)
    last_name = forms.CharField(label="Прізвище", max_length=150, required=False)
    email = forms.EmailField(label="Email", max_length=150)
    phone = forms.CharField(
        label="Телефон", max_length=32, required=False,
        widget=forms.TextInput(attrs={"placeholder": "+380…", "autocomplete": "tel", "inputmode": "tel"}),
    )
    city = forms.CharField(label="Місто", max_length=120, required=False)
    address = forms.CharField(
        label="Адреса / відділення Нової пошти", max_length=255, required=False,
        help_text="Підставляється при оформленні замовлення.",
    )

    def __init__(self, *args, user, **kwargs):
        self.user = user
        profile = get_profile(user)
        initial = {
            "first_name": user.first_name, "last_name": user.last_name, "email": user.email,
            "phone": profile.phone, "city": profile.city, "address": profile.address,
        }
        initial.update(kwargs.pop("initial", None) or {})
        super().__init__(*args, initial=initial, **kwargs)

    def clean_first_name(self):
        return self.cleaned_data["first_name"].strip()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if email_taken(email, exclude_pk=self.user.pk):
            raise ValidationError("Цей email уже використовується іншим акаунтом.")
        return email

    def save(self):
        user, d = self.user, self.cleaned_data
        # Якщо логін збігався з email (так створює реєстрація), тримаємо їх синхронними.
        sync_username = user.username.lower() == (user.email or "").lower()
        user.first_name, user.last_name, user.email = d["first_name"], d["last_name"].strip(), d["email"]
        if sync_username:
            user.username = d["email"]
        profile = get_profile(user)
        profile.phone, profile.city, profile.address = d["phone"], d["city"], d["address"]
        with transaction.atomic():
            user.save()
            profile.save()
        return user
