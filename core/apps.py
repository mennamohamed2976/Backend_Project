from django.apps import AppConfig


class CoreConfig(AppConfig):
    name = 'core'

from django.apps import AppConfig

class OrganMatchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'organ_match'

    def ready(self):
        import organ_match.signals  
