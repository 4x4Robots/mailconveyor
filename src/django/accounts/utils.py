from django.contrib.auth.models import User, Group

# Role constants
ADMIN_GROUP = 'Admin'
MANAGER_GROUP = 'Manager'
USER_GROUP = 'User'


def get_user_role(user):
    """Get the user's role based on their groups."""
    if user.groups.filter(name=ADMIN_GROUP).exists():
        return ADMIN_GROUP
    elif user.groups.filter(name=MANAGER_GROUP).exists():
        return MANAGER_GROUP
    else:
        return USER_GROUP


def is_admin(user):
    """Check if user is an admin."""
    return user.groups.filter(name=ADMIN_GROUP).exists()


def is_manager(user):
    """Check if user is a manager or admin."""
    return user.groups.filter(name__in=[MANAGER_GROUP, ADMIN_GROUP]).exists()


def create_default_groups():
    """Create default user groups if they don't exist."""
    for role in [ADMIN_GROUP, MANAGER_GROUP, USER_GROUP]:
        Group.objects.get_or_create(name=role)


def assign_role_to_user(user, role):
    """Assign a role to a user by adding them to the appropriate group."""
    user.groups.clear()
    if role in [ADMIN_GROUP, MANAGER_GROUP, USER_GROUP]:
        group, created = Group.objects.get_or_create(name=role)
        user.groups.add(group)