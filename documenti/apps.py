from django.apps import AppConfig


class DocumentiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'documenti'

    def ready(self):
        import documenti.signals