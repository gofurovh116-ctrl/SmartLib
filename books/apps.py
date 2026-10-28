from django.apps import AppConfig


class BooksConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'books'
    verbose_name = "Kitoblar va Fond"

    def ready(self):
        try:
            from . import keep_alive
            keep_alive.start_keep_alive_thread()
        except Exception:
            pass

