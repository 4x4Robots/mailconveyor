from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _
from .managers import CustomUserManager


class CustomUser(AbstractUser):
    """
    Custom user model extending Django's AbstractUser with email-only authentication.
    
    Roles:
    - USER: Can edit own profile only, access assigned mailing lists
    - MANAGER: Can view all users, edit own profile, manage mailing lists they have access to
    - ADMIN: Full CRUD on all users and mailing lists
    """
    
    class Role(models.TextChoices):
        USER = 'USER', _('User')
        MANAGER = 'MANAGER', _('Manager')
        ADMIN = 'ADMIN', _('Admin')
    
    # Remove username field and use email as the primary identifier
    username = None
    email = models.EmailField(_('email address'), unique=True)
    
    # Role field for permission management
    role = models.CharField(
        _('role'),
        max_length=10,
        choices=Role.choices,
        default=Role.USER
    )
    
    # Use email as the USERNAME_FIELD for authentication
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    # Use custom user manager
    objects = CustomUserManager()
    
    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"
    
    def get_role(self):
        """Get the user's role."""
        return self.role
    
    def is_admin(self):
        """Check if user is an admin."""
        return self.role == self.Role.ADMIN
    
    def is_manager(self):
        """Check if user is a manager or admin."""
        return self.role in [self.Role.MANAGER, self.Role.ADMIN]
    
    def is_user(self):
        """Check if user is a regular user."""
        return self.role == self.Role.USER
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['email']