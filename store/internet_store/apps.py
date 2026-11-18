from django.apps import AppConfig


class InternetStoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'internet_store'

    def ready(self):
        from . import favorites  # noqa: F401  (підключає сигнал злиття обраного після входу)
