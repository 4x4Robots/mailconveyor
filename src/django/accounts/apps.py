from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Configuration for the accounts app."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'accounts'
    verbose_name = 'User Accounts'
    
    def ready(self):
        """Add role methods to User model when app is ready."""
        # Import here to avoid circular imports
        from django.contrib.auth.models import User
        from .utils import is_admin, is_manager, get_user_role
        
        # Add role-related methods to User model
        User.add_to_class('is_admin', property(lambda self: is_admin(self)))
        User.add_to_class('is_manager', property(lambda self: is_manager(self)))
        User.add_to_class('get_role', lambda self: get_user_role(self))
        User.add_to_class('role', property(lambda self: get_user_role(self)))