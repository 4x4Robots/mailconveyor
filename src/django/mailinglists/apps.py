from django.apps import AppConfig


class MailinglistsConfig(AppConfig):
    """Configuration for the mailinglists app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mailinglists'
    verbose_name = 'Mailing Lists'
    
    def ready(self):
        """Perform initialization when app is ready."""
        # Import here to avoid circular imports
        import mailinglists.signals