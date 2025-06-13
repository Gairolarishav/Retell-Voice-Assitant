from django.apps import AppConfig
import os
import sys


class RetellConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'retells'

    def ready(self):
        if os.environ.get("RUN_MAIN") == "true" or 'runmodwsgi' in sys.argv:
            from . import scheduler
            scheduler.start()
