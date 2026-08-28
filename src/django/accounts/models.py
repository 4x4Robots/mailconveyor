# Use Django's built-in User model with groups for roles
# AD-001: Use Django native capabilities

from django.contrib.auth.models import User, Group


# Role constants
class Role:
    """Role constants for user groups."""
    ADMIN = 'Admin'
    MANAGER = 'Manager'
    USER = 'User'


def create_default_groups():
    """Create default user groups if they don't exist."""
    for role in [Role.ADMIN, Role.MANAGER, Role.USER]:
        Group.objects.get_or_create(name=role)