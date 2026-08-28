from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class CustomUser(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    
    Roles:
    - USER: Can edit own profile only, access assigned mailing lists
    - MANAGER: Can view all users, edit own profile, manage mailing lists they have access to
    - ADMIN: Full CRUD on all users and mailing lists
    """
    
    class Role(models.TextChoices):
        USER = 'USER', _('User')
        MANAGER = 'MANAGER', _('Manager')
        ADMIN = 'ADMIN', _('Admin')
    
    # Use email as the primary identifier but keep username for Django compatibility
    username = models.CharField(_('username'), max_length=150, unique=True, help_text=_('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'), default='')
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
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
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
    
    @classmethod
    def create_superuser(cls, email, first_name, last_name, password=None, **extra_fields):
        """
        Create and save a superuser with the given email, first name, last name and password.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', cls.Role.ADMIN)
        
        if not email:
            raise ValueError('The Email must be set')
        email = cls.normalize_email(email)
        user = cls(email=email, first_name=first_name, last_name=last_name, **extra_fields)
        user.set_password(password)
        user.save(using=cls._default_manager.db)
        return user
    
    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        ordering = ['email']