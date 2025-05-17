from django.apps import AppConfig


class TagtrackConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'tagtrack'

    def ready(self):
        from . import signals
