from django.apps import AppConfig


class MlmAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mlm_app'
    verbose_name = 'MSK Earning MLM System'
    
    def ready(self):
        import mlm_app.signals
