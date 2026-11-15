from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q


class EmailOrUsernameBackend(ModelBackend):
    """Вхід за email (покупці) або за логіном (адміністратори). Регістр email не важливий."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if not username or password is None:
            return None
        username = username.strip()

        user = User._default_manager.filter(username=username).first()
        if user is None:
            # Шукаємо без урахування регістру; якщо збігів не рівно один, входу немає (щоб не помилитись акаунтом).
            matches = list(User._default_manager.filter(
                Q(username__iexact=username) | Q(email__iexact=username))[:2])
            user = matches[0] if len(matches) == 1 else None

        if user is None:
            User().set_password(password)  # вирівнюємо час відповіді, щоб не видавати, чи існує такий акаунт
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
