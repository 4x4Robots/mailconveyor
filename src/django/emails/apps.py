from django.apps import AppConfig


class EmailsConfig(AppConfig):
    """Configuration for the emails app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'emails'
    verbose_name = 'Emails'
    
    def ready(self):
        """Perform initialization when app is ready."""
        # Import here to avoid circular imports
        import emails.signals