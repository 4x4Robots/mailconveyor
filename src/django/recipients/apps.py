from django.apps import AppConfig


class RecipientsConfig(AppConfig):
    """Configuration for the recipients app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'recipients'
    verbose_name = 'Email Recipients'
